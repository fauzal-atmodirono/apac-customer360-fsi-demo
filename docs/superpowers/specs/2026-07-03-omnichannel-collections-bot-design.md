# Omnichannel AI Collections Bot — Design

**Date:** 2026-07-03
**Author:** Yuda (with Claude Code)
**Status:** Approved design — ready for implementation planning
**Target:** Bank Muamalat Collections Demo, presentation Tuesday 2026-07-07
**Source docs:** `docs/Bank Muamalat Demo Summary.pdf` (sync 2026-07-03), existing collections layer in this repo.

## 1. Goal

Add a **bot-initiated (outbound), multi-channel, AI collections bot** to the existing
Customer 360 demo. The bot reaches delinquent debtors over Twilio, opens the conversation
with a tone set by how late they are (Days Past Due / DPD), and **adapts dynamically** to
the debtor's reply — turning sterner on refusal, or empathetic and offering restructuring
("Rekonstruksi") on financial hardship.

This is a **demo**, not production. Decisions optimise for a convincing, low-risk live
demonstration on Tuesday, not for scale or production hardening.

## 2. Scope & key decisions

| Decision | Choice | Rationale |
|---|---|---|
| Interactivity | **Full two-way on a real device** | Highest-impact demo; shows dynamic adaptation live |
| Runtime | **Local + ngrok tunnel** | Matches PDF "test locally"; fast iteration this week |
| Bot brain | **New standalone Gemini service** | Keeps stateful outbound bot separate from the read-only Q&A agent |
| Channels | **WhatsApp two-way; SMS + Email send-only** | Two-way focused on PDF's primary channel; omnichannel story still shown |
| WhatsApp delivery | **Twilio WhatsApp Sandbox** | Meta sender registration won't clear by Tuesday (see Risks) |
| Contacts | **`demo-contacts.json`** (SMS dummy numbers, WhatsApp real team numbers) | Keeps real numbers out of BigQuery; preserves the PII-masking governance story |
| Trigger + UI | **Dashboard button + live transcript** | Full product experience on stage |
| Language | **Bilingual BM + English** (detect from reply, default BM outbound) | Authentic to a Malaysian Islamic-bank audience |
| Architecture | **Approach A**: dedicated `collections-bot` FastAPI service + polling webapp | Mirrors existing `agent/` + chat-proxy pattern; clean isolation |
| State store | **SQLite** | Survives dev restarts; dashboard reads history |
| Transcript delivery | **~1.5s SWR polling** | Matches existing `useApi` pattern; no SSE complexity |

**Explicitly out of scope (YAGNI):** SMS/Email inbound reply parsing (send-only), writing
back to BigQuery, production WhatsApp sender registration, auth on the bot service beyond
Twilio signature verification, multi-tenant / scale concerns, persisting real PII in BQ.

## 3. Architecture

Four units, each with one responsibility:

### 3.1 `collections-bot/` — new FastAPI service (Python)
The only new backend, sibling to `agent/`. Endpoints:

- `POST /outreach/start` — body `{customer_id, channel}`. Looks up the debtor's case facts
  in BigQuery (`stage`, `current_dpd`, `outstanding`, `loan_id`), resolves display name +
  destination from `demo-contacts.json`, composes the DPD-stage-toned opening message
  (bilingual, default BM), sends via the Twilio adapter, and opens a conversation record.
  Returns the conversation id.
- `POST /twilio/inbound` — Twilio WhatsApp webhook. Verifies `X-Twilio-Signature`, loads the
  conversation by sender, runs the conversation engine (intent + language classification and
  reply generation in one Gemini call), sends the reply, appends both turns, updates outcome.
  Returns TwiML/`200`.
- `GET /conversations` and `GET /conversations/{id}` — read model for the dashboard.
- `GET /healthz`.

### 3.2 Conversation store — SQLite
Two tables:
- `conversations(id, customer_id, channel, dpd, stage, tone, language, detected_intent,
  outcome, dest, started_at, updated_at)`
- `messages(id, conversation_id, direction, channel, body, twilio_sid, status, ts)`

`direction` ∈ {`out`, `in`}. `status` ∈ {`sent`, `delivered`, `failed`, `degraded`}.

### 3.3 Twilio adapter — module inside the bot
Thin wrapper isolating all channel-specific concerns:
- `send_whatsapp(to, body)` — `to` prefixed `whatsapp:`
- `send_sms(to, body)`
- `send_email(to, subject, body)` — via SendGrid
- `verify_inbound_signature(request)` — HMAC over `TWILIO_AUTH_TOKEN` + public URL + params

### 3.4 Webapp additions — Next.js
- New **"Outreach"** page under `app/(dashboard)/outreach/` — debtor picker (by DPD stage),
  channel selector, send button, live transcript panel, detected-intent badge, outcome chip.
- Proxy route `app/api/outreach/[...path]/route.ts` forwarding to `BOT_URL` (same pattern as
  `app/api/chat/route.ts` → `AGENT_URL`), so the browser never talks to the bot directly.
- SWR polling (~1.5s) against the proxy to render the live transcript.
- Sidebar entry in `components/shell/app-sidebar.tsx`.

### 3.5 Data touchpoints
The bot **reads** `mart_collection_recovery` + `mart_financing_health` to ground each message
in the debtor's real case. It **does not write** to BigQuery. Conversation state lives only in
SQLite. Display names + destinations come from `demo-contacts.json`, never from BQ (masked).

## 4. Conversation flow & tone state machine

### 4.1 Opening message — tone fixed by DPD stage

| Stage (mart) | DPD | Tone | Message thrust |
|---|---|---|---|
| `SOFT_REMINDER` | ≤30 | Friendly, polite ("bot manis") | Gentle reminder, payment due, how to pay |
| `INTENSIVE` | 31–60 | Neutral, firm, persistent | Accumulating arrears + credit-score consequence |
| `FIELD_VISIT` | 61–90 | Assertive, authoritative | Serious warning, urge immediate action |
| `RECOVERY_LEGAL` | >90 | Direct, legal ("agak keras") | Legal-warning / field-visit escalation notice |

Every opening message is grounded in real case facts: outstanding amount (RM), DPD, loan id.

### 4.2 Inbound reply — intent branch

On each reply, one Gemini call classifies **language** (BM/English) and **intent**, then
generates a reply:

```
                        [Inbound reply]
                              │
       ┌──────────────┬───────┴────────┬───────────────┐
   [AGREE]        [HOSTILE]        [HARDSHIP]        [OTHER]
   acknowledge    refusal/         "struggling       unclear
   + pay guidance aggressive       financially"
       │              │                │                │
   PTP_OBTAINED   shift sterner,   empathetic +      clarify, hold
                  official/legal   offer Rekonstruksi current tone
                  → HOSTILE_       (waive/reduce
                    ESCALATED      charges, payment
                                   plan, extension)
                                   → RESTRUCTURE_OFFERED
```

**Tone-floor rule:** the bot never de-escalates below the DPD floor. At DPD 90 an "agree"
stays firm-polite, not "manis". Stage sets the floor; intent only moves it *sterner*
(hostile) or *adds an offer* (hardship).

### 4.3 State recorded
- `tone` — current tone (may move sterner from the stage floor)
- `language` — BM or English, tracked from the debtor's replies (default BM outbound)
- `detected_intent` — last classified intent
- `outcome` ∈ {`OPENED`, `PTP_OBTAINED`, `RESTRUCTURE_OFFERED`, `HOSTILE_ESCALATED`,
  `NO_RESPONSE`} — deliberately echoes the mart's `case_status` vocabulary for narrative
  tie-back (not written to BQ).

### 4.4 Restructuring content (hardship branch)
Shariah-consistent with the repo's existing model: waive/reduce charges (no penalty interest
anywhere), payment-plan adjustment, installment extension — matching the existing
`recovery_type = 'RESTRUCTURE'` ("Rekonstruksi").

## 5. Configuration

`collections-bot/.env` (gitignored; `.env.example` committed with placeholders):

```bash
# Twilio core
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
# Senders (one purchased number)
TWILIO_SMS_FROM=+1XXXXXXXXXX
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886   # sandbox number
# Email via SendGrid
SENDGRID_API_KEY=
EMAIL_FROM=collections@yourverifieddomain.com
EMAIL_FROM_NAME=Bank Muamalat Collections
# Gemini
GOOGLE_API_KEY=                              # or Vertex ADC via GOOGLE_CLOUD_PROJECT
GEMINI_MODEL=gemini-2.5-flash
# BigQuery lookup (reuse repo defaults)
GCP_PROJECT=nbs-playground-data-analytics
BQ_LOCATION=asia-southeast2
GOLD_DATASET=demo_gold_analytics
# Service
BOT_PORT=8100
CONVERSATION_DB_PATH=./collections-bot/conversations.sqlite
PUBLIC_BASE_URL=                             # ngrok https URL
VERIFY_TWILIO_SIGNATURE=true                 # false only for first local wiring
```

`collections-bot/demo-contacts.json` (gitignored; `.example` committed):
```json
{
  "0010000042": { "name": "Encik Ahmad", "dpd_stage": "SOFT_REMINDER",
                  "whatsapp": "whatsapp:+60XXXXXXXXX", "sms": "+1500XXXXXXX",
                  "email": "ahmad@example.com" }
}
```
Maps ~3 hand-picked debtor CIFs (one each at DPD ~30/60/90, chosen from the mart by stage)
to destinations. WhatsApp → real team numbers; SMS → dummy; Email → team/dummy.

**Twilio/SendGrid console prep (operator):**
1. Confirm purchased number is SMS-capable → `TWILIO_SMS_FROM`.
2. Activate WhatsApp Sandbox; note sandbox number (`TWILIO_WHATSAPP_FROM`) + join code; each
   team WhatsApp number sends `join <code>` once.
3. Point the sandbox inbound webhook ("When a message comes in", POST) at
   `https://<ngrok>/twilio/inbound`.
4. SendGrid: create API key + verify a single sender email.

## 6. Error handling & demo resilience

- **Twilio send failure** — recorded as `failed` with the Twilio error code, shown red in the
  transcript. WhatsApp "recipient not joined" (`63015`/`63016`) → explicit sandbox-join hint.
- **Inbound signature** — `/twilio/inbound` verifies `X-Twilio-Signature`; invalid → `403`.
  `VERIFY_TWILIO_SIGNATURE=false` bypass for first local wiring only.
- **Gemini failure/timeout (~10s)** — fall back to a stage-appropriate canned reply so the
  debtor still gets a coherent response; logged as `degraded`.
- **Unmapped debtor** — `/outreach/start` returns `422`; dashboard disables send with reason.
- **Idempotency** — send button locks while in flight; inbound webhook dedupes on Twilio
  `MessageSid`.
- **Tunnel restart** — README runbook: re-paste new ngrok URL into Twilio sandbox webhook +
  `PUBLIC_BASE_URL` (30-second fix).

## 7. Testing

- **Conversation-engine unit tests** (most coverage): representative BM + English inbound
  texts → assert intent, tone, language, outcome transition, and the no-de-escalation rule.
- **Twilio adapter tests**: mock Twilio/SendGrid; assert correct `from`/`to`/body per channel,
  `whatsapp:` prefix; signature verify with good/bad signatures.
- **Webhook integration test**: FastAPI TestClient POST of a simulated Twilio inbound payload
  → reply generated, persisted, send attempted (mocked).
- **Opening-message snapshot per stage**: right tone markers + real case facts (RM, DPD).
- **Manual live checklist** (README runbook, Monday dry-run): join sandbox → trigger each
  stage → reply hostile / hardship / agree → confirm tone shift + outcome in dashboard.

## 8. Risks

1. **WhatsApp sender (highest).** The purchased Twilio number is not WhatsApp-enabled without
   Meta sender registration, which won't clear by Tuesday. Mitigation: use the WhatsApp
   Sandbox (team numbers join once). Verify Friday. If the number is already WA-approved, swap
   `TWILIO_WHATSAPP_FROM`.
2. **Tunnel stability during the demo.** ngrok URL must stay live; runbook covers re-pasting.
3. **Sandbox join friction.** Every WhatsApp recipient must send the join code once before the
   demo — include in the Monday dry-run.
4. **Gemini latency on stage.** Mitigated by the timeout + canned-reply fallback.
5. **SendGrid sender verification.** Email won't send until a sender/domain is verified — do
   this Friday.

## 9. Out-of-repo dependencies to add
- Python: `fastapi`, `uvicorn`, `twilio`, `sendgrid`, `google-genai` (or `google-adk`),
  `google-cloud-bigquery`, `python-dotenv` in `collections-bot/requirements.txt`.
- No new webapp npm deps (reuses SWR, existing components).

## 10. Non-goals reminder
Demo-grade. No BQ writes, no production WhatsApp, no auth beyond Twilio signature, no scale
concerns. Keep the conversation engine and Twilio adapter small and independently testable.
