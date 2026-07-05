# Collections Bot — Deploy Runbook

One page to stand up the omnichannel collections bot + dashboard on Cloud Run.
All scripts live in `collections-bot/` and `webapp/`. Work stays on `dev-yuda`.

## Topology (why three projects)

| Concern | Project | Notes |
|---|---|---|
| Bot Cloud Run + **Vertex/Gemini** + **Firestore** + BQ **job** billing | `lv-playground-genai` | where you have full IAM |
| BigQuery **tables** (gold marts) | `nbs-playground-data-analytics` | read-only, dataset-level grant |
| Firestore DB `customer360-db` (Native, `asia-southeast2`) | `lv-playground-genai` | conversation store |

The split is driven by env vars in `collections-bot/.env`:
`VERTEX_PROJECT=lv-…` (Gemini), `BQ_JOB_PROJECT=lv-…` (BQ job), `GCP_PROJECT=nbs-…`
(table qualification), `FIRESTORE_PROJECT=lv-…`, `STORE_BACKEND=firestore`.

## Live demo values

- Bot URL: `https://c360-collections-bot-swgjfxtwwq-et.a.run.app`
- Runtime SA: `c360-collections-bot@lv-playground-genai.iam.gserviceaccount.com`
- Region: `asia-southeast2` · Service: `c360-collections-bot`

---

## 1. IAM (once)

```bash
cd collections-bot
./grant-iam.sh                 # runtime SA: Vertex + Firestore + BQ jobUser (on lv),
                               # dataset READER on the nbs gold dataset
```
Run it as a principal with IAM-admin + serviceAccountAdmin on `lv` and `bigquery.admin`
on `nbs`. The dataset READER step (reading real RM amounts) can also be done manually:

```bash
SA=c360-collections-bot@lv-playground-genai.iam.gserviceaccount.com
DS=nbs-playground-data-analytics:demo_gold_analytics
bq show --format=prettyjson "$DS" > /tmp/ds.json
python3 - <<PY
import json
d=json.load(open('/tmp/ds.json'))
d.setdefault('access',[]).append({'role':'READER','userByEmail':'$SA'})
json.dump(d,open('/tmp/ds.json','w'))
PY
bq update --source /tmp/ds.json "$DS"
```
Without it the bot still runs, but `outstanding`/`dpd` fall back to `0` (messages use each
contact's configured stage). It's runtime IAM — takes effect immediately, no redeploy.

## 2. Deploy the bot

```bash
cd collections-bot
PROJECT=lv-playground-genai \
RUNTIME_SA=c360-collections-bot@lv-playground-genai.iam.gserviceaccount.com \
./deploy.sh
```
Builds from the `Dockerfile`, deploys `--allow-unauthenticated` (Twilio needs the webhook),
scales **0→4** (Firestore state), and sets `PUBLIC_BASE_URL` to the deployed URL.

## 3. Verify

```bash
U=https://c360-collections-bot-swgjfxtwwq-et.a.run.app
curl -s "$U/health"                                   # {"ok":true}
SMOKE_BASE=$U ./smoke.sh 0019286954 sms               # simulated SMS: exercises Vertex+BQ+Firestore, no real send
```
The transcript should show a Malay Gemini opener with `sms/simulated`. Use `whatsapp` for a
real two-way test (recipient must have joined the Twilio sandbox first).

## 4. Twilio webhook

In the Twilio WhatsApp Sandbox, set **"When a message comes in"** to:
```
https://c360-collections-bot-swgjfxtwwq-et.a.run.app/twilio/inbound   (HTTP POST)
```
Must match `PUBLIC_BASE_URL` exactly (signature verification). deploy.sh already set it.

## 5. Dashboard (the trigger button)

**Option A — run locally against the cloud bot (recommended for the demo).** Keeps the other
dashboards working via your ADC; the Outreach page hits the deployed bot:
```bash
# webapp/.env.local
BOT_URL=https://c360-collections-bot-swgjfxtwwq-et.a.run.app
BOT_API_KEY=<same 64-char key as collections-bot/.env>
cd webapp && npm run dev      # http://localhost:3000/outreach → pick a debtor
```

**Option B — deploy the dashboard too** (Outreach page works; other pages need `nbs` BQ +
governance IAM the webapp SA doesn't yet have):
```bash
cd webapp
BOT_URL=https://c360-collections-bot-swgjfxtwwq-et.a.run.app ./deploy.sh   # private service
gcloud run services proxy c360-webapp --region asia-southeast2            # open it
```

---

## Gotchas (already handled, noted for future)

- **`/healthz` is intercepted by Cloud Run's frontend** (returns a Google 404) — the liveness
  route is **`/health`**.
- **SMS to +62 can't route** from the US Twilio number → `SIMULATE_CHANNELS=sms` (composed +
  shown `simulated`, not sent). WhatsApp + Email are real.
- **Secrets are plain env vars** for the demo (`deploy.sh` prints the Secret Manager upgrade).
- **macOS Python SSL**: `smoke.sh` uses certifi so it can hit the HTTPS URL.

## Redeploy / rollback

```bash
# redeploy after a code change (same command as step 2)
# roll back to a previous revision:
gcloud run services update-traffic c360-collections-bot --region asia-southeast2 \
  --to-revisions <REVISION>=100 --project lv-playground-genai
```
