#!/usr/bin/env bash
# Grant the IAM the deployed bot (+ dashboard) needs. Idempotent — safe to re-run.
# You must run this as a principal with IAM-admin rights on BOTH projects
# (roles/resourcemanager.projectIamAdmin or Owner).
#
#   ./grant-iam.sh                              # grants to the bot's runtime SA
#   INVOKER=user:me@devoteam.com ./grant-iam.sh # + let that user open the private webapp
#   RUNTIME_SA=sa@proj.iam.gserviceaccount.com ./grant-iam.sh   # non-default runtime SA
#   ASSUME_YES=1 ./grant-iam.sh                 # skip the confirmation prompt
set -eu
cd "$(dirname "$0")"

getenv() { [ -f .env ] && grep -E "^$1=" .env | head -1 | cut -d= -f2- || true; }

# Bot runs + reads BigQuery + runs Vertex here (deploy.sh's default PROJECT == GCP_PROJECT).
PROJECT="${PROJECT:-$(getenv GCP_PROJECT)}";                 PROJECT="${PROJECT:-nbs-playground-data-analytics}"
# Firestore conversation store lives in a DIFFERENT project.
FIRESTORE_PROJECT="${FIRESTORE_PROJECT:-$(getenv FIRESTORE_PROJECT)}"; FIRESTORE_PROJECT="${FIRESTORE_PROJECT:-lv-playground-genai}"
REGION="${REGION:-$(getenv BQ_LOCATION)}";                   REGION="${REGION:-asia-southeast2}"
WEBAPP_SERVICE="${WEBAPP_SERVICE:-c360-webapp}"
INVOKER="${INVOKER:-}"   # optional: user:foo@bar.com or group:… to grant webapp access

# Runtime SA the bot runs as (default compute SA unless overridden — must match deploy.sh).
RUNTIME_SA="${RUNTIME_SA:-}"
if [ -z "$RUNTIME_SA" ]; then
  NUM="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
  RUNTIME_SA="${NUM}-compute@developer.gserviceaccount.com"
fi
MEMBER="serviceAccount:${RUNTIME_SA}"

cat <<EOF
About to grant (idempotent):
  runtime SA : ${RUNTIME_SA}
  on ${PROJECT}          : roles/aiplatform.user  (Gemini via Vertex ADC)
                           roles/bigquery.jobUser + roles/bigquery.dataViewer (case lookup)
  on ${FIRESTORE_PROJECT}: roles/datastore.user   (Firestore conversation store)
EOF
[ -n "$INVOKER" ] && echo "  ${WEBAPP_SERVICE} (${REGION}): roles/run.invoker -> ${INVOKER}"
echo
if [ "${ASSUME_YES:-}" != "1" ]; then
  printf "Apply? [y/N] "; read -r ok; [ "$ok" = "y" ] || { echo "aborted"; exit 1; }
fi

echo "→ enabling Vertex AI API on ${PROJECT}…"
gcloud services enable aiplatform.googleapis.com --project "$PROJECT"

bind() {  # bind <project> <role>
  echo "→ ${2} on ${1}"
  gcloud projects add-iam-policy-binding "$1" \
    --member="$MEMBER" --role="$2" --condition=None >/dev/null
}
bind "$PROJECT"           "roles/aiplatform.user"
bind "$PROJECT"           "roles/bigquery.jobUser"
# Project-level for simplicity; tighten to the gold dataset only if you prefer.
bind "$PROJECT"           "roles/bigquery.dataViewer"
bind "$FIRESTORE_PROJECT" "roles/datastore.user"

if [ -n "$INVOKER" ]; then
  echo "→ roles/run.invoker on ${WEBAPP_SERVICE} for ${INVOKER}"
  gcloud run services add-iam-policy-binding "$WEBAPP_SERVICE" \
    --project "$PROJECT" --region "$REGION" \
    --member="$INVOKER" --role="roles/run.invoker" >/dev/null
fi

echo "✓ done"
