# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An end-to-end GCP data & analytics demo for a Malaysian Islamic bank (Bank Muamalat).
Mock legacy AS400 (DB2) core-banking CSVs flow through a **Medallion architecture**
(Bronze → Silver → Gold) in BigQuery, are modeled into a unified Customer 360 mart with
Dataform, and are protected by **column-level security + dynamic PII masking**. A Next.js
PWA dashboard and an ADK chat agent sit on top of the Gold layer. Built from the BRD/PRD
in `docs/` (PDFs).

The build is **dry-run-first**: nothing is created in GCP until `terraform apply`. The
whole pipeline can be validated locally with no project (see below).

## Commands

Top-level orchestration is via the `Makefile` (override defaults inline, e.g.
`make load PROJECT=my-proj`). Full live run order: `gen-data → tf-init → tf-plan →
tf-apply → upload → load → df-run`.

```bash
make gen-data                         # Python+Faker → 5 AS400 CSV extracts + corrupt fixtures
make tf-plan / tf-apply / tf-destroy  # provision / tear down all infra (terraform/envs/dev.tfvars)
make upload PROJECT=<p>               # gsutil CSVs → landing bucket
make load   PROJECT=<p>               # ingestion/load_bronze.py: GCS → Bronze
make df-run PROJECT=<p>               # run Silver+Gold+assertions via Cloud Workflows
make dataform-deploy PROJECT=<p>      # push SQLX to managed Dataform repo, run as runner SA
```

**Local validation (no GCP project needed) — use this to check changes:**

```bash
make gen-data                                       # emits valid CSVs
cd terraform && terraform init && terraform validate
cd dataform  && npx -y @dataform/cli@latest compile # must produce a clean Bronze→Silver→Gold graph
```

**Web app** (`webapp/`, uses your ADC for BigQuery):

```bash
cd webapp && npm install
npm run dev            # http://localhost:3000
npm run build && npm start   # production + PWA service worker
npm run lint           # next lint
```

**Agent** (`agent/`, ADK "Ask the data"): FastAPI on `:8000`, `POST /chat`. The webapp's
`AGENT_URL` env var points at it.

There is **no automated test suite**. "Tests" are the PRD verification cases (TC-1.1,
TC-2.x, TC-3.1) run manually against BigQuery as different identities — see the
Verification table in `README.md` and `analytics/customer_360_queries.sql`.

## Architecture

### Data pipeline (the core)
- `data_generator/generate_mock_as400.py` — deterministic generator (~1,000 customers via
  weighted archetypes) producing AS400 CSV extracts + **corrupt fixtures** (in
  `out/corrupt/`) used to prove pipeline failure modes. Includes 3 named personas.
- `ingestion/load_bronze.py` — portable GCS→Bronze loader (`bq load`, raw).
- `dataform/` — SQLX project (Dataform core 3.x). `definitions/sources/` declares Bronze,
  `definitions/silver/` conforms it (dims + facts; e.g. legacy `TXNTYP` D/C →
  `DEBIT`/`CREDIT`), `definitions/gold/` builds the marts (`mart_customer_360` + ~10
  others), `definitions/assertions/` gate Gold writes (e.g. `assert_balanced_accounts`).
  Silver `ref()`s Bronze for real lineage.
- Orchestration has two paths, toggled by `create_orchestration`:
  `orchestration/workflows/medallion_load.yaml` (**Cloud Workflows, default, ~free at
  idle**) and `orchestration/composer/` (reference Composer 3 Airflow DAG, off by default,
  the only material recurring cost).

### Governance model — the differentiator
A `Banking_Customer_Data_Classification` taxonomy with four policy tags drives dynamic
masking. Two masking formats (`XXXX-XXXX-####` phone, `XXXXXXXXXXXX####` PAN) are **custom
SQL UDF routines** (not built-ins), created in `terraform/modules/governance`. Access
tiers: fine-grained reader → cleartext, masked reader → masked, neither → query denied.

**Three non-obvious rules that the source BRD/PRD get wrong** (see README "corrections"):
1. The SQLX column key is `bigqueryPolicyTags`, **not** `policyTags`.
2. **BigQuery does NOT propagate policy tags to derived tables** — Gold models must
   re-apply tags on inherited PII columns (`full_name`, `phone_number`). Both Silver and
   Gold call `constants.piiColumn(desc, tagKey)` from `dataform/includes/constants.js`.
3. Policy-tag URNs are created by Terraform and **injected as Dataform compilation vars**
   at run time (`terraform output -json policy_tag_vars` → orchestrator `--vars`). When the
   vars are empty (bare local checkout), `piiColumn` emits no tag so `compile` stays clean.

`dataform/includes/constants.js` is the single source of truth for scoring logic too —
Investment Propensity Score (IPS), churn-risk weights, and personalization signals are all
defined there as SQL-generating JS helpers. Change scoring here, not in individual SQLX.

### Web app (`webapp/`) — Next.js App Router PWA
A browser can't reach BigQuery, so each dashboard page has a paired API route handler
(`app/api/<page>/route.ts`) that queries server-side. All SQL lives in **`lib/queries.ts`**;
`lib/bigquery.ts` runs it. `bigquery.ts` exposes two identities via `runQuery(sql, {masked})`:
the default ADC client (fine-grained reader → cleartext) and a **`google-auth` Impersonated
client** for the masked-reader SA — this is how the governance page shows cleartext-vs-masked
side by side. Results are cached in-memory 60s. Table-name constants are centralized at the
top of `bigquery.ts`. Auth is Auth.js v5 + Google (`auth.ts`, `middleware.ts`), currently
**bypassed via `DISABLE_AUTH=true`** because the service runs private on Cloud Run.

### Agent (`agent/`) — ADK "Ask the data"
`agent.py` defines an ADK `LlmAgent` (Gemini) with a `BigQueryToolset`. It is **read-only
(`WriteMode.BLOCKED`)**, **scoped to two Gold marts only** (Collections & Recovery subject),
and queried under a masked identity so PII stays masked in chat. The agent's instruction
prompt tells it to append a single fenced ` ```chart ` JSON block; `server.py` (FastAPI
`/chat`) parses that block + the SQL/rows out of the ADK event stream and returns
`{answer, sql, chart, rows, session_id}` to the webapp's `app/api/chat/route.ts`.

### Terraform (`terraform/`)
`main.tf` wires modules: `storage`, `bigquery` (datasets), `governance` (taxonomy, tags,
masking routines, IAM), `dataform` (managed repo + runner SA), `orchestration` (Workflows +
Scheduler), and `webapp.tf` (Cloud Run runtime SA). Key feature toggles in `envs/*.tfvars`:
`create_orchestration`, `create_dataform_repo`, `create_masked_demo_sa`, `enable_apis`.

## Conventions & gotchas
- Default deployment target is project `nbs-playground-data-analytics`, location
  `asia-southeast2`; datasets are `demo_bronze_as400` / `demo_silver_banking` /
  `demo_gold_analytics`. These are defaults baked into `bigquery.ts`, `agent.py`, and
  `dataform/workflow_settings.yaml` — override via env/vars, don't hardcode elsewhere.
- After changing any Silver PII column, verify the corresponding Gold model re-applies the
  policy tag (tags do not inherit).
- Always run `npx @dataform/cli compile` after editing SQLX — it's the fastest way to catch
  a broken ref/graph, and requires no live resources.
- Amounts throughout are Malaysian Ringgit (RM).
