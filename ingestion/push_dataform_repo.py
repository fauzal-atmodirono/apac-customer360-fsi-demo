#!/usr/bin/env python3
"""Push the local Dataform project into the managed Dataform repository and run it.

Commits everything under `dataform/` to the repository's `main` branch via the
Dataform API (`commitRepositoryChanges` — works only on repos with NO git remote),
then compiles (injecting the column-level-security policy-tag vars) and triggers a
workflow invocation that builds Silver + Gold + assertions. The managed run executes
as the Dataform service agent.

Usage:
    python ingestion/push_dataform_repo.py \
        --project nbs-playground-data-analytics --location asia-southeast2 \
        --repo c360-medallion --dataform-dir dataform \
        --vars-json "$(cd terraform && terraform output -json policy_tag_vars)"

Requires: pip install google-cloud-dataform
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

SKIP_NAMES = {".df-credentials.json", ".DS_Store"}
SKIP_DIRS = {"__pycache__", ".git", "node_modules"}


def collect_files(root: str) -> dict[str, bytes]:
    """Map of repo-relative path -> file bytes for everything under `root`."""
    files: dict[str, bytes] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if name in SKIP_NAMES or name.startswith("."):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            with open(full, "rb") as fh:
                files[rel] = fh.read()
    return files


def main() -> int:
    p = argparse.ArgumentParser(description="Push + run the Dataform project in managed Dataform.")
    p.add_argument("--project", required=True)
    p.add_argument("--location", default="asia-southeast2")
    p.add_argument("--repo", default="c360-medallion")
    p.add_argument("--dataform-dir", default="dataform")
    p.add_argument("--vars-json", default="{}",
                   help="JSON map of Dataform compilation vars (the policy-tag URNs).")
    p.add_argument("--poll-seconds", type=int, default=10)
    args = p.parse_args()

    from google.cloud import dataform_v1beta1 as dataform

    client = dataform.DataformClient()
    repo = f"projects/{args.project}/locations/{args.location}/repositories/{args.repo}"
    compile_vars = json.loads(args.vars_json)

    # 1. Commit every local file to the repo's default branch.
    files = collect_files(args.dataform_dir)
    if "workflow_settings.yaml" not in files and "dataform.json" not in files:
        print(f"ERROR: no Dataform project file found under {args.dataform_dir}/", file=sys.stderr)
        return 1
    file_ops = {
        path: dataform.CommitRepositoryChangesRequest.FileOperation(
            write_file=dataform.CommitRepositoryChangesRequest.FileOperation.WriteFile(contents=data)
        )
        for path, data in files.items()
    }
    client.commit_repository_changes(
        request=dataform.CommitRepositoryChangesRequest(
            name=repo,
            commit_metadata=dataform.CommitMetadata(
                author=dataform.CommitAuthor(name="c360-deploy", email_address="c360-deploy@example.com"),
                commit_message="Sync Customer 360 medallion project",
            ),
            file_operations=file_ops,
        )
    )
    print(f"Committed {len(files)} files to {args.repo}@main")

    # 2. Compile main, injecting the policy-tag vars (column-level security).
    compilation = client.create_compilation_result(
        parent=repo,
        compilation_result=dataform.CompilationResult(
            git_commitish="main",
            code_compilation_config=dataform.CodeCompilationConfig(
                default_database=args.project,
                default_location=args.location,
                vars=compile_vars,
            ),
        ),
    )
    print(f"Compiled: {compilation.name}")

    # 3. Invoke the workflow (Silver + Gold + assertions, transitive deps).
    invocation = client.create_workflow_invocation(
        parent=repo,
        workflow_invocation=dataform.WorkflowInvocation(
            compilation_result=compilation.name,
            invocation_config=dataform.InvocationConfig(transitive_dependencies_included=True),
        ),
    )
    print(f"Invoked: {invocation.name}\nPolling...")

    # 4. Poll to completion.
    State = dataform.WorkflowInvocation.State
    terminal = {State.SUCCEEDED, State.FAILED, State.CANCELLED}
    while True:
        time.sleep(args.poll_seconds)
        state = client.get_workflow_invocation(name=invocation.name).state
        print(f"  state={state.name}")
        if state in terminal:
            break

    if state != State.SUCCEEDED:
        print(f"FAILED: workflow invocation ended in {state.name}", file=sys.stderr)
        return 1
    print("SUCCEEDED: managed Dataform built Silver + Gold with policy tags.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
