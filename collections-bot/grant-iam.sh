#!/usr/bin/env bash
# Grant the IAM the deployed bot needs. Idempotent — safe to re-run.
# Supports a cross-project topology: the bot runs (+ Vertex, Firestore, BQ jobs) in
# RUN_PROJECT, while the BigQuery TABLES live in TABLE_PROJECT (GCP_PROJECT). For the
# demo: RUN_PROJECT=lv-playground-genai, TABLE_PROJECT=nbs-playground-data-analytics.
#
# Run as a principal with:
#   - IAM-admin on RUN_PROJECT           (roles/resourcemanager.projectIamAdmin)
#   - serviceAccountAdmin on RUN_PROJECT (to create the runtime SA)
#   - bigquery.admin on TABLE_PROJECT    (to add a dataset-level reader)
#
#   ./grant-iam.sh
#   INVOKER=user:me@devoteam.com ./grant-iam.sh   # + open the private webapp
#   ASSUME_YES=1 ./grant-iam.sh                    # skip the confirmation prompt
set -eu
cd "$(dirname "$0")"

getenv() { [ -f .env ] && grep -E "^$1=" .env | head -1 | cut -d= -f2- || true; }

# Where the bot runs: Vertex + Firestore + BQ jobs are billed here.
RUN_PROJECT="${RUN_PROJECT:-$(getenv BQ_JOB_PROJECT)}"
[ -n "$RUN_PROJECT" ] || RUN_PROJECT="$(getenv FIRESTORE_PROJECT)"
[ -n "$RUN_PROJECT" ] || RUN_PROJECT="$(getenv GCP_PROJECT)"
[ -n "$RUN_PROJECT" ] || RUN_PROJECT="nbs-playground-data-analytics"

TABLE_PROJECT="${TABLE_PROJECT:-$(getenv GCP_PROJECT)}";        TABLE_PROJECT="${TABLE_PROJECT:-nbs-playground-data-analytics}"
GOLD_DATASET="${GOLD_DATASET:-$(getenv GOLD_DATASET)}";         GOLD_DATASET="${GOLD_DATASET:-demo_gold_analytics}"
FIRESTORE_PROJECT="${FIRESTORE_PROJECT:-$(getenv FIRESTORE_PROJECT)}"; FIRESTORE_PROJECT="${FIRESTORE_PROJECT:-$RUN_PROJECT}"
REGION="${REGION:-$(getenv BQ_LOCATION)}";                      REGION="${REGION:-asia-southeast2}"
WEBAPP_SERVICE="${WEBAPP_SERVICE:-c360-webapp}"
INVOKER="${INVOKER:-}"

SA_NAME="${SA_NAME:-c360-collections-bot}"
RUNTIME_SA="${RUNTIME_SA:-${SA_NAME}@${RUN_PROJECT}.iam.gserviceaccount.com}"
MEMBER="serviceAccount:${RUNTIME_SA}"

cat <<EOF
About to grant (idempotent):
  runtime SA : ${RUNTIME_SA}   (created in ${RUN_PROJECT} if missing)
  on ${RUN_PROJECT}:
      roles/aiplatform.user   (Gemini via Vertex ADC)
      roles/datastore.user    (Firestore conversation store: ${FIRESTORE_PROJECT})
      roles/bigquery.jobUser  (run the case-lookup query job here)
  on ${TABLE_PROJECT} dataset ${GOLD_DATASET}:
      READER                  (dataset-level dataViewer, to read the marts)
EOF
[ -n "$INVOKER" ] && echo "  ${WEBAPP_SERVICE} (${REGION}): roles/run.invoker -> ${INVOKER}"
echo
if [ "${ASSUME_YES:-}" != "1" ]; then
  printf "Apply? [y/N] "; read -r ok; [ "$ok" = "y" ] || { echo "aborted"; exit 1; }
fi

echo "→ ensuring runtime SA exists…"
gcloud iam service-accounts describe "$RUNTIME_SA" --project "$RUN_PROJECT" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SA_NAME" --project "$RUN_PROJECT" \
    --display-name "Collections bot (Cloud Run) runtime"

echo "→ enabling Vertex AI API on ${RUN_PROJECT}…"
gcloud services enable aiplatform.googleapis.com --project "$RUN_PROJECT"

bind() {  # bind <project> <role>
  echo "→ ${2} on ${1}"
  gcloud projects add-iam-policy-binding "$1" --member="$MEMBER" --role="$2" --condition=None >/dev/null
}
bind "$RUN_PROJECT"       "roles/aiplatform.user"
bind "$RUN_PROJECT"       "roles/datastore.user"
bind "$RUN_PROJECT"       "roles/bigquery.jobUser"
[ "$FIRESTORE_PROJECT" != "$RUN_PROJECT" ] && bind "$FIRESTORE_PROJECT" "roles/datastore.user"

echo "→ dataset READER on ${TABLE_PROJECT}:${GOLD_DATASET} (needs bigquery.admin there)…"
TMP="$(mktemp)"
bq show --format=prettyjson "${TABLE_PROJECT}:${GOLD_DATASET}" > "$TMP"
python3 - "$TMP" "$RUNTIME_SA" <<'PY'
import json, sys
path, sa = sys.argv[1], sys.argv[2]
d = json.load(open(path))
acc = d.setdefault("access", [])
if any(e.get("userByEmail") == sa and e.get("role") in ("READER", "roles/bigquery.dataViewer") for e in acc):
    print("   already a reader"); sys.exit(0)
acc.append({"role": "READER", "userByEmail": sa})
json.dump(d, open(path, "w"))
print("   appending READER")
PY
bq update --source "$TMP" "${TABLE_PROJECT}:${GOLD_DATASET}" >/dev/null && echo "   ok"
rm -f "$TMP"

if [ -n "$INVOKER" ]; then
  echo "→ roles/run.invoker on ${WEBAPP_SERVICE} for ${INVOKER}"
  gcloud run services add-iam-policy-binding "$WEBAPP_SERVICE" \
    --project "$RUN_PROJECT" --region "$REGION" \
    --member="$INVOKER" --role="roles/run.invoker" >/dev/null
fi

echo "✓ done"
