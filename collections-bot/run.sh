#!/usr/bin/env bash
# collections-bot local runner: ensures the venv, sanity-checks .env, prints the
# ngrok + Twilio sandbox wiring steps, then starts the bot.
#   Usage:  ./run.sh
set -eu

cd "$(dirname "$0")"

# Read a single key from .env without sourcing it (values may contain spaces).
getenv() { [ -f .env ] && grep -E "^$1=" .env | head -1 | cut -d= -f2- || true; }
warn()   { printf '  \033[33m⚠\033[0m %s\n' "$1"; }

# --- venv ---------------------------------------------------------------------
if [ ! -x .venv/bin/python ]; then
  echo "→ creating virtualenv + installing deps…"
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi

# --- .env ---------------------------------------------------------------------
if [ ! -f .env ]; then
  echo "✗ .env not found — copy the template first:  cp .env.example .env"
  exit 1
fi

# demo-contacts.json is required — the bot cannot boot without it.
if [ ! -f demo-contacts.json ]; then
  echo "✗ demo-contacts.json missing — the bot can't start without it:"
  echo "    cp demo-contacts.example.json demo-contacts.json   # then edit real WhatsApp numbers"
  exit 1
fi

PORT="$(getenv BOT_PORT)"; PORT="${PORT:-8100}"

# --- free the port: kill any stale bot so we don't keep serving old code/.env
STALE="$(lsof -nP -ti tcp:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
if [ -n "$STALE" ]; then
  echo "→ stopping stale bot on :$PORT (pid $STALE)…"
  kill $STALE 2>/dev/null || true
  sleep 1
fi

# --- config sanity (warn, don't block) ---------------------------------------
echo "→ config check:"
[ -n "$(getenv TWILIO_AUTH_TOKEN)" ]    || warn "TWILIO_AUTH_TOKEN empty (needed to verify inbound signatures)"
[ -n "$(getenv TWILIO_WHATSAPP_FROM)" ] || warn "TWILIO_WHATSAPP_FROM empty"
[ -n "$(getenv BOT_API_KEY)" ]          || warn "BOT_API_KEY empty — /start & /conversations are UNAUTHENTICATED on the tunnel"
[ -n "$(getenv PUBLIC_BASE_URL)" ]      || warn "PUBLIC_BASE_URL empty — set it to your ngrok URL (or VERIFY_TWILIO_SIGNATURE=false while first wiring)"
if [ -z "$(getenv GOOGLE_API_KEY)" ]; then
  ./.venv/bin/python -c "import google.auth; google.auth.default()" >/dev/null 2>&1 \
    || warn "Gemini uses ADC but no Application Default Credentials — run: gcloud auth application-default login"
fi
echo "  ok"

cat <<EOF

────────────────────────────────────────────────────────────
 Collections bot → http://localhost:${PORT}

 2nd terminal — expose the inbound webhook (Cloudflare Tunnel):
     cloudflared tunnel --url http://localhost:${PORT}

 With the https URL it prints (…trycloudflare.com):
   1. .env →  PUBLIC_BASE_URL=<url>          (then restart this script)
   2. Twilio Console → Messaging → Try it out → WhatsApp sandbox →
      "When a message comes in":  <url>/twilio/inbound   (HTTP POST)
   3. Each tester WhatsApps  join <sandbox-code>  to the sandbox number once.

 Dashboard:  cd ../webapp && npm run dev   →  http://localhost:3000/outreach
────────────────────────────────────────────────────────────

EOF

exec ./.venv/bin/uvicorn server:get_app --factory --host 0.0.0.0 --port "${PORT}"
