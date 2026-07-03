"""ADK 'Ask the data' agent — chats over the BigQuery Gold layer.

Read-only (WriteMode.BLOCKED), scoped to the Gold dataset, and queried under a masked
identity so BigQuery policy tags mask PII (hashed names, redacted phones) even in chat.
"""
import os

import google.auth
from google.auth import impersonated_credentials
from google.adk.agents import LlmAgent
from google.adk.integrations.bigquery import BigQueryCredentialsConfig, BigQueryToolset
from google.adk.integrations.bigquery.config import BigQueryToolConfig, WriteMode

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "nbs-playground-data-analytics")
GOLD = os.environ.get("GOLD_DATASET", "demo_gold_analytics")
BQ_LOCATION = os.environ.get("BQ_LOCATION", "asia-southeast2")
MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash")

_SCOPES = ["https://www.googleapis.com/auth/bigquery", "https://www.googleapis.com/auth/cloud-platform"]


def _credentials():
    """ADC by default; optionally impersonate a masked-reader SA (local PII-masking demo).
    On Cloud Run the runtime SA has no fine-grained reader, so PII is masked without impersonation."""
    creds, _ = google.auth.default(scopes=_SCOPES)
    sa = os.environ.get("BQ_IMPERSONATE_SA")
    if sa:
        creds = impersonated_credentials.Credentials(
            source_credentials=creds, target_principal=sa, target_scopes=_SCOPES,
        )
    return creds


DATA_DICTIONARY = f"""
Available tables (all in `{PROJECT}.{GOLD}`). Query these only.

- mart_customer_360 (1 row/customer): customer_id, full_name*, phone_number*, age, customer_segment
  (MASS/AFFLUENT/HNW), region, tenure_years, income_band, annual_income, total_savings_balance,
  total_deposit_balance, cc_spend_last_30_days, debit_spend_last_30_days, total_card_spend_last_30_days,
  top_spending_category, atm_withdrawals_last_30_days, has_active_mortgage, total_loan_outstanding,
  debt_to_deposit_ratio, investment_propensity_score, propensity_score_segment
  (HNW_INVESTOR/DIGITAL_SHOPPER/LEVERAGED_BORROWER/STANDARD_RETAIL), churn_risk_score,
  churn_risk_segment (HIGH/MEDIUM/LOW).  (* = PII, always returned masked.)
- mart_personalization_signals (1/customer): rfm_segment, recency_days, frequency_90d, monetary_90d,
  spend_velocity_pct, share_of_wallet, discretionary_ratio, digital_share, liquidity_buffer_months,
  debt_service_ratio, financial_health_score, financial_health_band, life_stage, preferred_time_of_day,
  p_mortgage, p_term_deposit, p_card_upgrade, p_investment, p_consolidation, nbp_top, nbp_top_score.
- mart_cashflow (1/customer): monthly_inflow, monthly_outflow, net_surplus, salary_amount, has_salary,
  savings_rate, surplus_margin, wellness_score, wellness_band.
- mart_financing_health (1/customer w/ financing): loans, on_time_rate, current_dpd,
  arrears_bucket (Current/1-30/31-60/61-90/90+), total_arrears, is_npf.
- mart_collection_recovery (1/collection case): case_id, customer_id, loan_id,
  stage (SOFT_REMINDER/INTENSIVE/FIELD_VISIT/RECOVERY_LEGAL), case_status, collector, open_date,
  outstanding, actions_count, contact_rate, ptp_made, ptp_kept, recovered_amount, recovery_rate,
  is_restructured, is_written_off.
- mart_transfer_behaviour (1/customer): transfer_count, transfer_value, total_fees, intl_count, top_corridor.
- mart_profit_distribution (1/customer): total_profit_paid, effective_yield.
- mart_channel_usage (1/customer): branch_count, atm_count, cdm_count, cash_in, cash_out,
  primary_channel, digital_ratio.
- mart_campaign_performance (1/campaign): campaign_name, product_name, channel, sent, opened, clicked,
  converted, open_rate, conversion_rate, roi.
- mart_kpi_history (1/month): month, customers, total_savings, total_deposits, total_card_spend.

Amounts are in Malaysian Ringgit (RM). Ignore any table not listed above.
"""

INSTRUCTION = f"""You are the "Ask the data" analytics assistant for the Devoteam Customer 360 demo
(Bank Muamalat Malaysia, an Islamic bank). You answer business questions by querying BigQuery.

Rules:
- ONLY query dataset `{PROJECT}.{GOLD}`. Never reference bronze/silver, other datasets, or other projects.
- READ-ONLY: SELECT / aggregations only. Never attempt INSERT/UPDATE/DELETE/MERGE/DDL.
- Prefer aggregate answers; if you must list rows, keep it to 25 or fewer.
- Customer names and phone numbers are PII and are returned MASKED by policy tags. Do not try to
  unmask them; if asked, explain they are masked for privacy/governance.
- Use get_table_info if unsure of a column; otherwise rely on the dictionary below.
- After querying, reply with a concise, executive answer stating the key numbers (RM where money),
  and briefly name the table(s) used. If a question can't be answered from these tables, say so briefly.
- VISUALIZATION: When the result is chartable, append EXACTLY ONE fenced code block AFTER your text
  answer, tagged `chart`, containing a single JSON object (no comments, valid JSON):
  ```chart
  {{"type": "bar", "title": "Customers by churn risk segment", "x": "churn_risk_segment", "y": ["customer_count"]}}
  ```
  Field rules:
  - "type": "bar" = compare categories (segments, stages, bands, corridors); "line" or "area" =
    a time series (e.g. `month` from mart_kpi_history); "pie" = share/composition of a whole;
    "kpi" = a single headline number.
  - "x": the category or time column (omit for "kpi"). "y": array of the numeric measure column(s).
  - "kpi" only: set "y" to the one numeric column and add "label" (a short metric name); omit "x".
  - Use the EXACT column names your SELECT returns. Keep the result small (<= ~25 grouped rows).
  - Do NOT emit the block for PII/write refusals, errors, or free-form answers with no table.

{DATA_DICTIONARY}
"""

_tool_config = BigQueryToolConfig(
    write_mode=WriteMode.BLOCKED,
    max_query_result_rows=50,
    maximum_bytes_billed=1_000_000_000,  # 1 GB safety cap
    compute_project_id=PROJECT,
    location=BQ_LOCATION,
)

_bq_toolset = BigQueryToolset(
    credentials_config=BigQueryCredentialsConfig(credentials=_credentials()),
    bigquery_tool_config=_tool_config,
)

root_agent = LlmAgent(
    model=MODEL,
    name="ask_the_data",
    description="Answers questions about the Customer 360 Gold-layer marts in BigQuery.",
    instruction=INSTRUCTION,
    tools=[_bq_toolset],
)
