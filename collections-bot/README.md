# Collections Bot — Bank Muamalat demo

Bot-initiated omnichannel collections outreach (WhatsApp two-way, SMS + Email send-only)
over Twilio, with a DPD-driven tone that adapts to hostile / hardship replies. Driven by
Gemini; reads case facts from BigQuery (read-only). See the design spec in
`docs/superpowers/specs/2026-07-03-omnichannel-collections-bot-design.md`.

## Setup

```bash
cd collections-bot
python -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env                     # fill in Twilio + SMTP creds (Gemini uses ADC)
cp demo-contacts.example.json demo-contacts.json   # set real WhatsApp numbers
gcloud auth application-default login    # Gemini runs on Vertex AI ADC — no API key
```

**Gemini** uses Vertex AI via Application Default Credentials — leave `GOOGLE_API_KEY` empty
in `.env` and set `GOOGLE_CLOUD_LOCATION` (default `global`). **Email** sends over plain SMTP
(`SMTP_HOST/PORT/USER/PASSWORD`, e.g. Gmail SMTP + an app password) — send-only, no inbox needed.

## Run (local)

```bash
./run.sh        # sets up the venv, sanity-checks .env, prints the ngrok/Twilio steps, starts the bot
```

Or start it directly:

```bash
./.venv/bin/uvicorn server:get_app --factory --host 0.0.0.0 --port 8100
```

Expose the inbound webhook with a tunnel and point Twilio at it (Cloudflare Tunnel;
`ngrok http 8100` works the same way):

```bash
cloudflared tunnel --url http://localhost:8100
# copy the printed https URL (…trycloudflare.com) into .env as PUBLIC_BASE_URL, then in the
# Twilio WhatsApp Sandbox set "When a message comes in" -> https://<url>/twilio/inbound  (HTTP POST)
```

## Twilio WhatsApp Sandbox

The purchased number sends SMS immediately, but WhatsApp requires the **Sandbox** until the
number is registered with Meta (won't clear for the demo). Each team WhatsApp number must send
`join <sandbox-code>` to the sandbox number once before it can receive messages.

## Smoke test (real send)

With the bot running, fire one real outbound message and watch the transcript:

```bash
./smoke.sh                       # list demo debtors (CIF / stage / channels)
./smoke.sh 0010000042 whatsapp   # send the DPD-toned opener, then poll ~10s
```

It calls `/start` directly (with the `X-Bot-Key` header), reports the send status, and
surfaces common failures (401 = key mismatch, 422 = unknown CIF/channel, WhatsApp
63015/63016 = recipient hasn't joined the sandbox). Reply on the handset during the poll
window to see the tone adapt. For the full back-and-forth, use the dashboard.

## Tests

```bash
cd collections-bot && python -m pytest -v
```

## Monday dry-run checklist (mirrors PDF §5)

1. Every WhatsApp recipient has sent `join <code>` to the sandbox number.
2. `PUBLIC_BASE_URL` + the Twilio sandbox webhook both point at the current ngrok URL.
3. From the webapp Outreach page, trigger a **SOFT_REMINDER** debtor → confirm friendly opener arrives.
4. Reply **"saya susah / I'm struggling"** → confirm empathetic restructuring offer + `RESTRUCTURE_OFFERED` in the dashboard.
5. Reply **"I won't pay"** → confirm sterner tone + `HOSTILE_ESCALATED`.
6. Trigger a **RECOVERY_LEGAL** debtor → confirm the legal-notice tone.
7. Fire SMS + Email sends → confirm they appear as sent (dummy SMS number is fine).

## Deploy to Cloud Run

Cloud Run gives a stable public HTTPS URL — no tunnel needed. The service is public so
Twilio can reach `/twilio/inbound`, but `/start` & `/conversations` stay gated by
`BOT_API_KEY` and the webhook by the Twilio signature.

```bash
./deploy.sh            # reads config from .env; PROJECT/REGION overridable via env
```

The script deploys from source (uses the `Dockerfile`), runs a **single warm instance**
(`--min/--max-instances 1`), sets the env vars from `.env`, then sets `PUBLIC_BASE_URL`
to the deployed URL and prints the Twilio + smoke-test steps.

**Test the deployed bot** (same script, remote base):

```bash
SMOKE_BASE=https://<service-url> ./smoke.sh 0019286954 whatsapp
```

**Prerequisites / IAM**
- Deployer roles: Cloud Run Admin, Cloud Build Admin, Artifact Registry Admin,
  **Service Account User** (to run-as the SA), and permission to enable the
  `run`, `cloudbuild`, `artifactregistry`, `aiplatform` APIs.
- Runtime service account (default compute SA unless `RUNTIME_SA=` is set) needs
  **Vertex AI User** (`roles/aiplatform.user`, Gemini ADC) and **BigQuery Job User +
  Data Viewer** on the gold dataset.

### Conversation store: SQLite vs Firestore

The bot keeps conversations + messages in a pluggable store, chosen by `STORE_BACKEND`:

- **`sqlite`** (default) — a single file in the container. Simple, zero setup, but ephemeral
  and single-writer, so the Cloud Run deploy must pin **one warm instance** (`min=max=1`) or
  `/start` and the inbound webhook could land on different instances with different state.
- **`firestore`** — serverless and concurrency-safe, so `deploy.sh` lets the service **scale
  0→4** instead of pinning one. The database may live in a **different GCP project** than the
  bot; the client is pointed explicitly via env vars.

For this demo the Firestore DB is `customer360-db` (Native mode, `asia-southeast2`) in project
**`lv-playground-genai`** — separate from where BigQuery/gold data lives (`nbs-…`). Enable it:

```bash
# .env
STORE_BACKEND=firestore
FIRESTORE_PROJECT=lv-playground-genai
FIRESTORE_DATABASE=customer360-db

# grant the bot's RUNTIME service account Firestore access ON the DB's project:
gcloud projects add-iam-policy-binding lv-playground-genai \
  --member="serviceAccount:<runtime-sa>@<bot-project>.iam.gserviceaccount.com" \
  --role="roles/datastore.user"
```

No composite indexes are needed — the store uses equality filters only and sorts in memory
(fine at demo volumes). Collections created: `conversations`, `messages`.

**Caveats**
- **SQLite is ephemeral + single-instance.** With `STORE_BACKEND=sqlite`, state lives in the
  container filesystem, so the deploy pins one warm instance (`min=max=1`). Switch to
  `STORE_BACKEND=firestore` (above) to scale past one instance.
- `demo-contacts.json` is baked into the image (it's excluded from git but kept for the
  build). For production, mount it from Secret Manager / GCS instead.
- Secrets go in as plain env vars for the demo; move to Secret Manager for real use
  (see the note printed by `deploy.sh`).

## Troubleshooting

- **WhatsApp not delivered (Twilio 63015/63016):** recipient hasn't joined the sandbox.
- **Inbound 403:** `PUBLIC_BASE_URL` doesn't match the Twilio webhook URL. Set
  `VERIFY_TWILIO_SIGNATURE=false` temporarily to unblock local wiring, then fix the URL.
- **tunnel restarted (new URL):** a quick Cloudflare/ngrok tunnel mints a fresh URL each run —
  re-paste it into both `.env` (`PUBLIC_BASE_URL`) and the Twilio sandbox webhook (30-second fix).
  A named `cloudflared` tunnel keeps a stable hostname if you want to avoid this.
