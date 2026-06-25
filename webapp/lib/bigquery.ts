import "server-only";
import { BigQuery } from "@google-cloud/bigquery";
import { GoogleAuth, Impersonated } from "google-auth-library";

export const PROJECT = process.env.GCP_PROJECT ?? "nbs-playground-data-analytics";
export const LOCATION = process.env.BQ_LOCATION ?? "asia-southeast2";
export const GOLD = process.env.GOLD_DATASET ?? "demo_gold_analytics";
export const SILVER = process.env.SILVER_DATASET ?? "demo_silver_banking";
export const MASKED_SA =
  process.env.MASKED_SA ?? "c360-masked-reader@nbs-playground-data-analytics.iam.gserviceaccount.com";

export const MART = `\`${PROJECT}.${GOLD}.mart_customer_360\``;
export const PERS = `\`${PROJECT}.${GOLD}.mart_personalization_signals\``;
export const DIM_CUSTOMERS = `\`${PROJECT}.${SILVER}.dim_customers\``;
export const FCT_CC = `\`${PROJECT}.${SILVER}.fct_credit_card_transactions\``;
export const FCT_DC = `\`${PROJECT}.${SILVER}.fct_debit_card_transactions\``;
export const DIM_PRODUCTS = `\`${PROJECT}.${SILVER}.dim_products\``;
export const FCT_HOLDINGS = `\`${PROJECT}.${SILVER}.fct_product_holdings\``;
export const FCT_ACCT_TXN = `\`${PROJECT}.${SILVER}.fct_account_transactions\``;
export const MART_CASHFLOW = `\`${PROJECT}.${GOLD}.mart_cashflow\``;
export const MART_CAMPAIGNS = `\`${PROJECT}.${GOLD}.mart_campaign_performance\``;
export const MART_KPI_HISTORY = `\`${PROJECT}.${GOLD}.mart_kpi_history\``;
export const FCT_FINREPAY = `\`${PROJECT}.${SILVER}.fct_financing_repayments\``;
export const FCT_TRANSFERS = `\`${PROJECT}.${SILVER}.fct_transfers\``;
export const FCT_TELLER = `\`${PROJECT}.${SILVER}.fct_teller_transactions\``;
export const MART_FINANCING = `\`${PROJECT}.${GOLD}.mart_financing_health\``;
export const MART_TRANSFERS = `\`${PROJECT}.${GOLD}.mart_transfer_behaviour\``;
export const MART_PROFIT = `\`${PROJECT}.${GOLD}.mart_profit_distribution\``;
export const MART_CHANNEL = `\`${PROJECT}.${GOLD}.mart_channel_usage\``;

const SCOPES = ["https://www.googleapis.com/auth/cloud-platform"];

// Default client uses ADC (the deployer) -> fine-grained reader -> cleartext PII.
let _default: BigQuery | null = null;
function defaultClient(): BigQuery {
  if (!_default) _default = new BigQuery({ projectId: PROJECT, location: LOCATION });
  return _default;
}

// Masked client impersonates the masked-reader SA -> masked PII. Server-side
// google-auth impersonation (no shell; avoids the Streamlit in-thread slowness).
let _maskedPromise: Promise<BigQuery> | null = null;
function maskedClient(): Promise<BigQuery> {
  if (!_maskedPromise) {
    _maskedPromise = (async () => {
      const sourceClient = await new GoogleAuth({ scopes: SCOPES }).getClient();
      const authClient = new Impersonated({
        sourceClient,
        targetPrincipal: MASKED_SA,
        targetScopes: SCOPES,
      });
      return new BigQuery({ projectId: PROJECT, location: LOCATION, authClient });
    })();
  }
  return _maskedPromise;
}

// 60s in-memory cache keyed by sql + mode.
const cache = new Map<string, { at: number; rows: unknown[] }>();
const TTL = 60_000;

export async function runQuery<T = Record<string, unknown>>(
  sql: string,
  opts: { masked?: boolean; params?: Record<string, unknown> } = {},
): Promise<T[]> {
  const key = `${opts.masked ? "m" : "d"}:${sql}:${opts.params ? JSON.stringify(opts.params) : ""}`;
  const hit = cache.get(key);
  if (hit && Date.now() - hit.at < TTL) return hit.rows as T[];
  const client = opts.masked ? await maskedClient() : defaultClient();
  const [rows] = await client.query({ query: sql, location: LOCATION, params: opts.params });
  cache.set(key, { at: Date.now(), rows });
  return rows as T[];
}
