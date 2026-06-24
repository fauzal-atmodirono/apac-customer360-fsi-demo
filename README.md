# Core Banking Customer 360 & Hyper-Personalization Demo

An end-to-end **data & analytics** demo on Google Cloud that liberates legacy
AS400 (DB2) core-banking data into a **Medallion architecture** (Bronze → Silver
→ Gold) in BigQuery, models a unified **Customer 360** mart with Dataform, and
enforces **column-level security + dynamic PII masking** — orchestrated as a
daily pipeline.

Built from the BRD (`docs/BRD C360.pdf`) and PRD (`docs/PRD C360.pdf`).

```
                       ┌───────────────── orchestration ─────────────────┐
                       │  Cloud Scheduler ─► Cloud Workflows (default)    │
                       │  (reference: Cloud Composer 3 Airflow DAG)       │
                       └───────────────────────┬──────────────────────────┘
                                                ▼
  mock AS400 CSVs ─► GCS landing ─► Bronze (raw)  ─►  Silver (conformed)  ─►  Gold
   (data_generator)  (as400-drop)   demo_bronze       demo_silver            demo_gold
                                     [bq load]         [Dataform SQLX]        mart_customer_360
                                                            │                      │
                                                  policy tags + assertions   re-applied tags
                                                            └────── BigQuery CLS + dynamic masking ──────┘
```

## Repository layout

| Path | What it is |
|------|------------|
| `data_generator/` | Python+Faker generator → 5 AS400 CSV extracts (~1,000 customers via weighted archetypes so all segments + churn bands populate; region / tenure / income + 5 loan types) + corrupt fixtures, 3 personas |
| `terraform/` | All infrastructure: GCS, BigQuery datasets, taxonomy/policy tags, masking routines, data policies, IAM, Dataform repo, Workflows + Scheduler |
| `dataform/` | SQLX project: source declarations, Silver dims/fact, Gold `mart_customer_360`, assertions |
| `orchestration/workflows/` | Cloud Workflows definition (default, low-cost path) |
| `orchestration/composer/` | Reference Cloud Composer 3 Airflow DAG (BRD-faithful) |
| `ingestion/` | `load_bronze.py` portable GCS→Bronze loader |
| `analytics/` | Customer 360 demo queries (NBA, churn, life-stage, governance checks) |

## Prerequisites

- A GCP project with billing (for a live run). The build is **dry-run-first** —
  nothing is created until you `terraform apply`.
- `terraform` ≥ 1.5, `gcloud`/`gsutil`, `python3`, `node`/`npx` (for Dataform CLI).
- For full column-level security: real Cloud Identity groups (see `terraform/envs/dev.tfvars`).

## Run order

```bash
# 1. Generate mock AS400 extracts (deterministic; includes 3 personas + corrupt fixtures)
make gen-data

# 2. Review then provision infra (edit terraform/envs/dev.tfvars first: project_id, groups)
make tf-init
make tf-plan        # dry-run: review the full resource graph
make tf-apply

# 3. Land the data and load Bronze
make upload PROJECT=<proj>
make load   PROJECT=<proj>        # or let the orchestrator do it (step 4)

# 4. Run Silver + Gold + assertions (injects policy-tag URNs from TF output)
make df-run PROJECT=<proj>

# 5. Verify (see Governance + Verification below)
```

No project handy? You can still validate everything locally:

```bash
make gen-data                                   # emits valid CSVs
cd terraform && terraform init && terraform validate
cd dataform  && npx -y @dataform/cli@latest compile   # clean Bronze→Silver→Gold graph
```

## Governance model (PRD §5.3)

The differentiator. A `Banking_Customer_Data_Classification` taxonomy with four
policy tags drives **dynamic data masking**. Dataform applies the tags to Silver
columns and re-applies them on Gold (BigQuery does **not** auto-inherit tags).

| Policy tag | Columns | Masking | Cleartext for |
|------------|---------|---------|---------------|
| `PII_Name` | `full_name` | SHA-256 (built-in) | marketing, compliance |
| `PII_Phone` | `phone_number` | `XXXX-XXXX-####` (**custom routine**) | marketing, compliance |
| `PII_Address` | `address` | NULL (built-in) | compliance |
| `Card_PAN` | `card_number` (credit + debit) | `XXXXXXXXXXXX####` (**custom routine**) | compliance |

Access: **fine-grained reader** → cleartext; **masked reader** → masked value;
neither → query denied. The Dataform service agent gets fine-grained reader on
all tags so it can write/preserve tags during deployment.

## Verification (mirrors PRD §8 test cases)

| Test | How | Expected |
|------|-----|----------|
| Personas | Query 0 in `analytics/customer_360_queries.sql` | 3 personas land in `HNW_INVESTOR` / `LEVERAGED_BORROWER` / `DIGITAL_SHOPPER` |
| **TC-1.1** | `load_bronze.py … --local-dir data_generator/out/corrupt` (missing column file) | Bronze load fails with schema error |
| **TC-3.1** | Load `corrupt/AS400_SVDP_MAST.csv` (negative SV balance), run pipeline | `assert_balanced_accounts` fails → Gold write blocked |
| **TC-2.1** | Query 5 as a masked-reader identity | name=hash, phone=`XXXX-XXXX-####`, address=NULL |
| **TC-2.2** | Query 5 as marketing (fine-grained) | name + phone in cleartext |

## Managed Dataform (run transforms in the Dataform service)

Beyond the local CLI, the transformations can run in the **managed Dataform service** so
they're visible/runnable in the Console and execute under a dedicated service account
(`c360-dataform-runner`) — matching the BRD's "service account executing the Dataform
workflow." Enable with `create_dataform_repo = true` (already set), then:

```bash
make dataform-deploy PROJECT=nbs-playground-data-analytics
```

This (`ingestion/push_dataform_repo.py`) commits `dataform/` to the repo's `main` branch via
`commitRepositoryChanges` (no Git remote needed), compiles with the policy-tag URNs injected,
and runs a workflow invocation. The runner SA needs `bigquery.dataOwner` (to apply policy
tags via `setCategory`) + `datacatalog.viewer` + per-tag fine-grained reader + a
`dataform_assertions` dataset — all provisioned by Terraform.

## Web app (PWA) — primary dashboard

`webapp/` is a **Next.js (App Router, TypeScript) Progressive Web App** — the polished,
installable dashboard. Light-corporate theme via Tailwind + shadcn/ui, charts via Recharts,
the Malaysia map via MapLibre (token-free). A browser can't reach BigQuery, so Next.js API
route handlers (`app/api/<page>`) query it server-side using `lib/queries.ts` and
`lib/bigquery.ts` (ADC for cleartext; a `google-auth` **Impersonated** client for the
masked-reader SA). Serwist provides the service worker + `app/manifest.ts` for installability.

```bash
cd webapp
npm install
npm run dev          # http://localhost:3000  (uses your ADC for BigQuery)
# production / PWA service worker:
npm run build && npm start
```

Six pages (Executive, Demographics + map, Churn, Marketing/NBA, Spend & trends, Governance),
KPI cards, per-chart insight callouts, and the cleartext-vs-masked governance view (two
server-side identities).

### Deployed to Cloud Run (private)
Live (authenticated): `https://c360-webapp-159298782837.asia-southeast2.run.app`. The runtime
SA `c360-webapp` (provisioned in `terraform/webapp.tf`) has BigQuery reader + fine-grained
reader + token-creator on the masked SA. Deployed from source:

```bash
gcloud run deploy c360-webapp --source webapp --region asia-southeast2 \
  --service-account c360-webapp@<project>.iam.gserviceaccount.com \
  --no-allow-unauthenticated --memory 1Gi
```

It is **private** (no public access) because the governance page serves cleartext PII. To view
it, open an authenticated tunnel (needs `roles/run.invoker`):

```bash
gcloud run services proxy c360-webapp --region asia-southeast2   # → http://localhost:8080
```

**Current state:** deployed **private** with `DISABLE_AUTH=true`, so proxy users (who already
pass Cloud Run IAM) reach the dashboard directly — no second login. Access it with the
`gcloud run services proxy` command above. Org Domain-Restricted-Sharing blocks `allUsers`,
so a public URL needs either an org-policy exception or a load balancer + IAP.

### Public with Google sign-in (Auth.js) — ready to enable
App-level auth (`auth.ts`, Auth.js v5 + Google) gates the dashboard so the Cloud Run service
can be public. It's wired and deployed (secrets + OAuth client set) but **bypassed via
`DISABLE_AUTH=true`** while private. To go public: get an `allUsers` org-policy exception, then
redeploy **without** `DISABLE_AUTH` and **with** `--allow-unauthenticated` — the Google sign-in
(restricted to `ALLOWED_DOMAIN`) then becomes the gate. Sign-in is **domain-restricted** (`ALLOWED_DOMAIN`, e.g. `devoteam.com`);
middleware redirects unauthenticated users to a branded `/signin`. Secrets live in Secret
Manager (`c360-auth-secret`, `c360-google-client-id`, `c360-google-client-secret`).

One-time setup (only you can create the OAuth client):
1. Cloud Console → **APIs & Services → OAuth consent screen** (Internal), then **Credentials →
   Create OAuth client ID → Web application**. Authorized redirect URIs:
   `https://c360-webapp-159298782837.asia-southeast2.run.app/api/auth/callback/google` and
   `http://localhost:3000/api/auth/callback/google`.
2. Store the values (kept out of source):
   ```bash
   printf '<CLIENT_ID>'     | gcloud secrets versions add c360-google-client-id     --data-file=-
   printf '<CLIENT_SECRET>' | gcloud secrets versions add c360-google-client-secret --data-file=-
   ```
3. Redeploy public (now safe — the app enforces sign-in):
   ```bash
   gcloud run deploy c360-webapp --source webapp --region asia-southeast2 \
     --service-account c360-webapp@<project>.iam.gserviceaccount.com \
     --allow-unauthenticated --memory 1Gi \
     --set-env-vars ALLOWED_DOMAIN=devoteam.com,AUTH_URL=https://c360-webapp-159298782837.asia-southeast2.run.app \
     --set-secrets AUTH_SECRET=c360-auth-secret:latest,AUTH_GOOGLE_ID=c360-google-client-id:latest,AUTH_GOOGLE_SECRET=c360-google-client-secret:latest
   ```
Local dev: put `AUTH_SECRET`, `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`, `ALLOWED_DOMAIN` in
`webapp/.env.local`. For real per-viewer BigQuery masking (vs the demo's service-account
identity), exchange the Google token for per-user BigQuery access in `lib/bigquery.ts`.

## Best-practice notes & corrections to the source docs

1. **`bigqueryPolicyTags`, not `policyTags`** — the SQLX column key in current
   Dataform is `bigqueryPolicyTags`. Handled via `includes/constants.js#piiColumn`.
2. **Custom masking needs routines** — the `XXXX-XXXX-####` / `XXXXXXXXXXXX####`
   formats aren't built-ins; they're SQL UDFs created with
   `data_governance_type = "DATA_MASKING"` (see `modules/governance`).
3. **Policy tags don't auto-inherit** — Gold re-declares tags on `full_name` /
   `phone_number` (the PRD's "automatically inherits" comment is incorrect).
4. **Composer 3** is the current recommendation; the demo defaults to Cloud
   Workflows to avoid the ~$300+/mo Composer floor (toggle `create_orchestration`).
5. **Proper lineage** — Silver `ref()`s Bronze; legacy `TXNTYP` D/C is conformed
   to `DEBIT`/`CREDIT` in Silver so Gold aggregations read cleanly.
6. **Cost** (NFR-3) — Silver/Bronze partition on `_ingested_at`, the fact on
   `transaction_date`. Tear down with `make tf-destroy`.

## Cost note

With `create_orchestration = true`, Cloud Workflows + Scheduler cost effectively
nothing at idle (pay-per-execution). BigQuery/GCS for this data volume is pennies.
The optional Composer 3 path (reference DAG) is the only material recurring cost
and is **off by default**.
