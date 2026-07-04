#!/usr/bin/env bash
# Deploy the Next.js dashboard to Cloud Run and wire it to the collections bot.
# Reads config from .env.local; runs PRIVATE (--no-allow-unauthenticated) because
# auth is bypassed via DISABLE_AUTH=true — never expose it publicly with PII visible.
#
#   ./deploy.sh                                  # config from .env.local; defaults below
#   PROJECT=x REGION=y BOT_URL=https://… ./deploy.sh
set -eu
cd "$(dirname "$0")"

getenv() { [ -f .env.local ] && grep -E "^$1=" .env.local | head -1 | cut -d= -f2- || true; }

SERVICE="${SERVICE:-c360-webapp}"
PROJECT="${PROJECT:-$(getenv GCP_PROJECT)}"; PROJECT="${PROJECT:-nbs-playground-data-analytics}"
REGION="${REGION:-$(getenv BQ_LOCATION)}";   REGION="${REGION:-asia-southeast2}"
# The runtime SA Terraform creates (BigQuery + fine-grained PII reader). Override if renamed.
RUNTIME_SA="${RUNTIME_SA:-c360-webapp@${PROJECT}.iam.gserviceaccount.com}"

BOT_URL="${BOT_URL:-$(getenv BOT_URL)}"
BOT_API_KEY="${BOT_API_KEY:-$(getenv BOT_API_KEY)}"

case "$BOT_URL" in
  ""|*localhost*|*127.0.0.1*)
    echo "✗ BOT_URL is empty or points at localhost ($BOT_URL)."
    echo "  Deploy the bot first (collections-bot/deploy.sh), then re-run with its https URL:"
    echo "    BOT_URL=https://c360-collections-bot-xxxx.a.run.app ./deploy.sh"
    exit 1 ;;
esac
[ -n "$BOT_API_KEY" ] || { echo "✗ BOT_API_KEY empty — must match the bot's BOT_API_KEY."; exit 1; }

# Data + agent + auth defaults (override in .env.local). '@@' delimiter so values may hold commas.
KEYS_DEFAULTS="GCP_PROJECT=${PROJECT}@@BQ_LOCATION=${REGION}@@GOLD_DATASET=$(getenv GOLD_DATASET)@@SILVER_DATASET=$(getenv SILVER_DATASET)@@MASKED_SA=$(getenv MASKED_SA)@@AGENT_URL=$(getenv AGENT_URL)@@DISABLE_AUTH=$(getenv DISABLE_AUTH)"
ENVSTR="BOT_URL=${BOT_URL}@@BOT_API_KEY=${BOT_API_KEY}@@${KEYS_DEFAULTS}"

echo "→ deploying ${SERVICE} → ${PROJECT}/${REGION} (private) — bot at ${BOT_URL}…"
gcloud run deploy "$SERVICE" \
  --source . \
  --project "$PROJECT" \
  --region "$REGION" \
  --no-allow-unauthenticated \
  --service-account "$RUNTIME_SA" \
  --memory 1Gi \
  --set-env-vars "^@@^${ENVSTR}"

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(status.url)')"

cat <<EOF

────────────────────────────────────────────────────────────
 Deployed (private):  ${URL}

 The service is private (DISABLE_AUTH=true relies on that). Reach it without
 making it public via an authenticated local proxy:
     gcloud run services proxy ${SERVICE} --project ${PROJECT} --region ${REGION}
     # then open http://localhost:8080  → Outreach page → click a debtor

 To grant a teammate access instead:
     gcloud run services add-iam-policy-binding ${SERVICE} --project ${PROJECT} \\
       --region ${REGION} --member=user:THEM@devoteam.com --role=roles/run.invoker
────────────────────────────────────────────────────────────
EOF
