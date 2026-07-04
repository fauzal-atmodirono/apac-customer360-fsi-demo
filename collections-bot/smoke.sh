#!/usr/bin/env bash
# collections-bot smoke test: fire ONE real outbound /start at a demo debtor and
# show the send status + transcript. The bot must already be running (./run.sh).
#   ./smoke.sh                        # list demo debtors
#   ./smoke.sh <customer_id> [chan]   # chan = whatsapp (default) | sms | email
set -eu
cd "$(dirname "$0")"

getenv() { [ -f .env ] && grep -E "^$1=" .env | head -1 | cut -d= -f2- || true; }
PORT="$(getenv BOT_PORT)"; export SMOKE_PORT="${PORT:-8100}"
export SMOKE_KEY="$(getenv BOT_API_KEY)"
PY="$([ -x .venv/bin/python ] && echo ./.venv/bin/python || echo python3)"

exec "$PY" - "$@" <<'PYEOF'
import json, os, sys, time, urllib.request, urllib.error

BASE = f"http://localhost:{os.environ.get('SMOKE_PORT', '8100')}"
KEY  = os.environ.get("SMOKE_KEY", "")
HEAD = {"X-Bot-Key": KEY} if KEY else {}

def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(HEAD)
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or "null")
        except Exception:
            return e.code, None
    except urllib.error.URLError as e:
        print(f"✗ bot not reachable at {BASE} — start it first: ./run.sh  ({e.reason})")
        sys.exit(1)

st, _ = call("GET", "/healthz")
if st != 200:
    print(f"✗ /healthz returned {st}"); sys.exit(1)

cid_arg = sys.argv[1] if len(sys.argv) > 1 else ""
chan    = sys.argv[2] if len(sys.argv) > 2 else "whatsapp"

if not cid_arg:
    st, contacts = call("GET", "/contacts")
    if st == 401:
        print("✗ 401 from /contacts — BOT_API_KEY in .env doesn't match the request key."); sys.exit(1)
    print("Demo debtors (demo-contacts.json):")
    for c in contacts or []:
        print(f"  {c['customer_id']:>12}  {c['dpd_stage']:<15} {c['name']:<20} channels={','.join(c['channels'])}")
    print("\nUsage:  ./smoke.sh <customer_id> [whatsapp|sms|email]")
    sys.exit(0)

print(f"→ POST /start  customer_id={cid_arg}  channel={chan}")
st, resp = call("POST", "/start", {"customer_id": cid_arg, "channel": chan})
print(f"  HTTP {st}: {json.dumps(resp)}")
if st == 401:
    print("✗ 401 — BOT_API_KEY mismatch between .env and the request."); sys.exit(1)
if st == 422:
    print("✗ 422 — unknown debtor CIF, or that channel isn't set for this contact."); sys.exit(1)
cid = (resp or {}).get("conversation_id")
if not cid:
    print("✗ no conversation_id returned."); sys.exit(1)
if (resp or {}).get("send_error"):
    print(f"  ⚠ send_error: {resp['send_error']}")
    print("    (WhatsApp 63015/63016 = recipient hasn't sent 'join <code>' to the sandbox yet.)")

print(f"→ conversation {cid} — polling ~10s (reply on the handset to watch the bot adapt)…")
for _ in range(5):
    time.sleep(2)
    st, c = call("GET", f"/conversations/{cid}")
    if st != 200 or not c:
        continue
    print(f"\n[{c['stage']} · DPD {c['dpd']} · tone {c['tone']} · intent {c.get('detected_intent')} · outcome {c['outcome']}]")
    for m in c["messages"]:
        arrow = "OUT →" if m["direction"] == "out" else "← IN "
        print(f"  {arrow} [{m['channel']}/{m['status']}] {m['body']}")

print("\nFull live back-and-forth: use the dashboard → http://localhost:3000/outreach")
PYEOF
