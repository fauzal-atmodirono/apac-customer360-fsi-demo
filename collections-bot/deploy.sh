#!/usr/bin/env bash
# Deploy the collections bot to Cloud Run.
# Demo-grade: ONE warm instance holds the SQLite state (min=max=1); the service is
# public so Twilio can reach /twilio/inbound, but /start & /conversations are gated
# by BOT_API_KEY and the webhook by the Twilio signature.
#
#   ./deploy.sh                 # config read from .env; PROJECT/REGION overridable
#   PROJECT=x REGION=y RUNTIME_SA=sa@x.iam.gserviceaccount.com ./deploy.sh
set -eu
cd "$(dirname "$0")"

getenv() { [ -f .env ] && grep -E "^$1=" .env | head -1 | cut -d= -f2- || true; }

SERVICE="${SERVICE:-c360-collections-bot}"
PROJECT="${PROJECT:-$(getenv GCP_PROJECT)}";  PROJECT="${PROJECT:-nbs-playground-data-analytics}"
REGION="${REGION:-$(getenv BQ_LOCATION)}";    REGION="${REGION:-asia-southeast2}"
RUNTIME_SA="${RUNTIME_SA:-}"    # empty = default compute service account

[ -f .env ]              || { echo "✗ .env not found — cp .env.example .env and fill it";        exit 1; }
[ -f demo-contacts.json ] || { echo "✗ demo-contacts.json not found (it is baked into the image)"; exit 1; }

# Build the env-var string from .env with a custom '@@' delimiter so values may
# contain spaces (EMAIL_FROM_NAME) or commas (SIMULATE_CHANNELS). GOOGLE_API_KEY is
# deliberately omitted so the bot uses Vertex ADC via the runtime service account.
KEYS="TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_SMS_FROM TWILIO_WHATSAPP_FROM
SMTP_HOST SMTP_PORT SMTP_USER SMTP_PASSWORD SMTP_STARTTLS EMAIL_FROM EMAIL_FROM_NAME
GEMINI_MODEL GOOGLE_CLOUD_LOCATION VERTEX_PROJECT GCP_PROJECT BQ_JOB_PROJECT BQ_LOCATION GOLD_DATASET
VERIFY_TWILIO_SIGNATURE BOT_API_KEY SIMULATE_CHANNELS
STORE_BACKEND FIRESTORE_PROJECT FIRESTORE_DATABASE"
ENVSTR=""
for k in $KEYS; do
  ENVSTR="${ENVSTR}${ENVSTR:+@@}${k}=$(getenv "$k")"
done

SA_FLAG=""; [ -n "$RUNTIME_SA" ] && SA_FLAG="--service-account=${RUNTIME_SA}"

# SQLite state lives in the container, so it MUST pin one warm instance. Firestore
# is external + concurrency-safe, so let the service scale (and cost nothing idle).
if [ "$(getenv STORE_BACKEND)" = "firestore" ]; then
  INSTANCES="--min-instances 0 --max-instances 4"; STATE_NOTE="firestore state — scales 0→4"
else
  INSTANCES="--min-instances 1 --max-instances 1"; STATE_NOTE="sqlite state — single warm instance"
fi

echo "→ deploying ${SERVICE} → ${PROJECT}/${REGION} (${STATE_NOTE})…"
gcloud run deploy "$SERVICE" \
  --source . \
  --project "$PROJECT" \
  --region "$REGION" \
  --allow-unauthenticated \
  ${INSTANCES} \
  --memory 512Mi \
  --set-env-vars "^@@^${ENVSTR}" \
  ${SA_FLAG}

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(status.url)')"

# PUBLIC_BASE_URL must equal the deployed URL for inbound signature verification.
gcloud run services update "$SERVICE" --project "$PROJECT" --region "$REGION" \
  --update-env-vars "PUBLIC_BASE_URL=${URL}" >/dev/null
echo "→ set PUBLIC_BASE_URL=${URL}"

cat <<EOF

────────────────────────────────────────────────────────────
 Deployed:  ${URL}

 1. Twilio sandbox "when a message comes in":  ${URL}/twilio/inbound  (HTTP POST)
 2. Smoke test the deployed bot:
      SMOKE_BASE=${URL} ./smoke.sh 0019286954 whatsapp
    (uses BOT_API_KEY from .env for the X-Bot-Key header)
 3. Dashboard: set the webapp's  BOT_URL=${URL}  and  BOT_API_KEY=<same>  then rerun it.

 ⚠ Secrets (TWILIO_AUTH_TOKEN, BOT_API_KEY, SMTP_PASSWORD) are set as plain env vars,
   visible to anyone with run.viewer. For production move them to Secret Manager:
     gcloud secrets create c360-bot-twilio-token --data-file=- <<<"\$TOKEN"
     gcloud run services update ${SERVICE} --update-secrets TWILIO_AUTH_TOKEN=c360-bot-twilio-token:latest
   (needs Secret Manager Admin + the runtime SA granted roles/secretmanager.secretAccessor)
────────────────────────────────────────────────────────────
EOF
