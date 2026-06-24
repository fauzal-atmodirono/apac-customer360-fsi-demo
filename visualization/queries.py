"""BigQuery query layer for the Customer 360 dashboard.

Kept separate from the Streamlit UI so the queries can be smoke-tested directly.
Two clients are used:
  * the default ADC identity (the deployer) -> fine-grained reader -> CLEARTEXT PII
  * an impersonated `c360-masked-reader` SA  -> masked-reader     -> MASKED PII
which lets the Governance page show column-level security side by side.
"""
from __future__ import annotations

import functools
import os
import subprocess

import pandas as pd
from google.cloud import bigquery
from google.oauth2.credentials import Credentials as OAuthToken

PROJECT = os.environ.get("PROJECT", "nbs-playground-data-analytics")
BQ_LOCATION = os.environ.get("BQ_LOCATION", "asia-southeast2")
GOLD_DATASET = os.environ.get("GOLD_DATASET", "demo_gold_analytics")
SILVER_DATASET = os.environ.get("SILVER_DATASET", "demo_silver_banking")
MASKED_SA = os.environ.get(
    "MASKED_SA", "c360-masked-reader@nbs-playground-data-analytics.iam.gserviceaccount.com"
)

MART = f"`{PROJECT}.{GOLD_DATASET}.mart_customer_360`"
DIM_CUSTOMERS = f"`{PROJECT}.{SILVER_DATASET}.dim_customers`"
FCT_CC = f"`{PROJECT}.{SILVER_DATASET}.fct_credit_card_transactions`"
FCT_DC = f"`{PROJECT}.{SILVER_DATASET}.fct_debit_card_transactions`"

# Age-band CASE reused across several queries.
AGE_BAND_SQL = """CASE
    WHEN age < 30 THEN '18-29'
    WHEN age < 45 THEN '30-44'
    WHEN age < 60 THEN '45-59'
    ELSE '60+'
  END"""


@functools.lru_cache(maxsize=1)
def _default_client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT, location=BQ_LOCATION)


def _mint_masked_token() -> str:
    """Mint an access token for the masked-reader SA via gcloud impersonation."""
    return subprocess.run(
        ["gcloud", "auth", "print-access-token", "--impersonate-service-account", MASKED_SA],
        capture_output=True, text=True, check=True, timeout=60, stdin=subprocess.DEVNULL,
    ).stdout.strip()


@functools.lru_cache(maxsize=1)
def _masked_client() -> bigquery.Client:
    """Client authenticated as the masked-reader SA (sees masked PII).

    Prefers a pre-minted token in $MASKED_TOKEN (the `make dashboard` target mints
    it in the shell — fast). Minting in-process under Streamlit's request thread is
    pathologically slow, so that path is a fallback only. Tokens last ~1h.
    """
    token = os.environ.get("MASKED_TOKEN") or _mint_masked_token()
    return bigquery.Client(project=PROJECT, location=BQ_LOCATION, credentials=OAuthToken(token=token))


def _run(sql: str, client: bigquery.Client | None = None) -> pd.DataFrame:
    return (client or _default_client()).query(sql).result().to_dataframe()


# --- Executive overview ------------------------------------------------------
def kpis() -> dict:
    df = _run(f"""
        SELECT
          COUNT(*) AS customers,
          SUM(total_savings_balance) AS total_savings,
          SUM(total_deposit_balance) AS total_deposit_balance,
          SUM(total_loan_outstanding) AS total_loans,
          AVG(investment_propensity_score) AS avg_ips,
          AVG(age) AS avg_age,
          SUM(total_card_spend_last_30_days) AS total_card_spend,
          SAFE_DIVIDE(COUNTIF(has_active_mortgage), COUNT(*)) AS pct_mortgage,
          -- portfolio-level ratio (AVG of per-customer ratios is skewed by ~0-savings outliers)
          SAFE_DIVIDE(SUM(total_loan_outstanding), SUM(total_savings_balance)) AS portfolio_ltv
        FROM {MART}
    """)
    return df.iloc[0].to_dict()


def age_distribution() -> pd.DataFrame:
    return _run(f"SELECT age, propensity_score_segment AS segment FROM {MART}")


def tier_vs_segment() -> pd.DataFrame:
    return _run(f"""
        SELECT customer_segment AS tier, propensity_score_segment AS segment, COUNT(*) AS customers
        FROM {MART}
        GROUP BY tier, segment
    """)


def portfolio_totals() -> pd.DataFrame:
    return _run(f"""
        SELECT 'Savings' AS pool, SUM(total_savings_balance) AS amount FROM {MART}
        UNION ALL SELECT 'Deposits', SUM(total_deposit_balance) FROM {MART}
        UNION ALL SELECT 'Loans outstanding', SUM(total_loan_outstanding) FROM {MART}
    """)


def region_summary() -> pd.DataFrame:
    return _run(f"""
        SELECT region, COUNT(*) AS customers,
               ROUND(SUM(total_savings_balance), 0) AS total_savings,
               ROUND(AVG(investment_propensity_score), 1) AS avg_ips
        FROM {MART}
        GROUP BY region
        ORDER BY customers DESC
    """)


def income_band_summary() -> pd.DataFrame:
    return _run(f"""
        SELECT income_band, COUNT(*) AS customers,
               ROUND(AVG(total_savings_balance), 0) AS avg_savings,
               ROUND(AVG(annual_income), 0) AS avg_income
        FROM {MART}
        GROUP BY income_band
    """)


def tenure_summary() -> pd.DataFrame:
    return _run(f"""
        SELECT
          CASE
            WHEN tenure_years < 3 THEN '0-2 yrs'
            WHEN tenure_years < 7 THEN '3-6 yrs'
            WHEN tenure_years < 12 THEN '7-11 yrs'
            ELSE '12+ yrs'
          END AS tenure_band,
          COUNT(*) AS customers,
          ROUND(AVG(total_savings_balance), 0) AS avg_savings,
          ROUND(AVG(churn_risk_score), 1) AS avg_churn
        FROM {MART}
        GROUP BY tenure_band
        ORDER BY tenure_band
    """)


def segment_distribution() -> pd.DataFrame:
    return _run(f"""
        SELECT
          propensity_score_segment AS segment,
          COUNT(*) AS customers,
          ROUND(AVG(total_savings_balance), 0) AS avg_savings,
          ROUND(AVG(total_card_spend_last_30_days), 0) AS avg_card_spend
        FROM {MART}
        GROUP BY segment
        ORDER BY customers DESC
    """)


# --- Churn risk --------------------------------------------------------------
def churn_band_counts() -> pd.DataFrame:
    return _run(f"""
        SELECT churn_risk_segment AS band, COUNT(*) AS customers
        FROM {MART}
        GROUP BY band
        ORDER BY band
    """)


def churn_scatter() -> pd.DataFrame:
    return _run(f"""
        SELECT
          customer_id, churn_risk_segment, churn_risk_score,
          atm_withdrawals_last_30_days, total_savings_balance,
          cc_spend_last_30_days
        FROM {MART}
    """)


def high_churn_customers(limit: int = 50) -> pd.DataFrame:
    return _run(f"""
        SELECT
          customer_id, full_name, churn_risk_segment, churn_risk_score,
          atm_withdrawals_last_30_days, total_savings_balance, cc_spend_last_30_days
        FROM {MART}
        WHERE churn_risk_segment IN ('HIGH', 'MEDIUM')
        ORDER BY churn_risk_score DESC
        LIMIT {limit}
    """)


# --- Marketing / NBA ---------------------------------------------------------
def top_spending_categories() -> pd.DataFrame:
    return _run(f"""
        SELECT top_spending_category AS category, COUNT(*) AS customers
        FROM {MART}
        WHERE top_spending_category != 'NONE'
        GROUP BY category
        ORDER BY customers DESC
    """)


def life_stage_bands() -> pd.DataFrame:
    return _run(f"""
        SELECT
          CASE
            WHEN age < 30 THEN '18-29 (early career)'
            WHEN age < 45 THEN '30-44 (family forming)'
            WHEN age < 60 THEN '45-59 (peak earning)'
            ELSE '60+ (retirement)'
          END AS life_stage,
          COUNT(*) AS customers,
          ROUND(AVG(total_savings_balance), 0) AS avg_savings,
          ROUND(AVG(investment_propensity_score), 1) AS avg_ips
        FROM {MART}
        GROUP BY life_stage
        ORDER BY life_stage
    """)


def target_list(segment: str, limit: int = 50) -> pd.DataFrame:
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("segment", "STRING", segment)]
    )
    sql = f"""
        SELECT
          customer_id, full_name, customer_segment,
          total_savings_balance, total_loan_outstanding,
          top_spending_category, investment_propensity_score
        FROM {MART}
        WHERE propensity_score_segment = @segment
        ORDER BY investment_propensity_score DESC
        LIMIT {limit}
    """
    return _default_client().query(sql, job_config=job_config).result().to_dataframe()


# --- Governance demo (cleartext vs masked) -----------------------------------
def _pii_sample_sql(limit: int) -> str:
    # Join a representative card per customer so all four policy tags appear.
    return f"""
        WITH cards AS (
          SELECT customer_id, ANY_VALUE(card_number) AS card_number
          FROM {FCT_CC} GROUP BY customer_id
        )
        SELECT
          c.customer_id, c.full_name, c.phone_number, c.address,
          cards.card_number
        FROM {DIM_CUSTOMERS} c
        LEFT JOIN cards USING (customer_id)
        ORDER BY c.customer_id
        LIMIT {limit}
    """


def pii_cleartext(limit: int = 8) -> pd.DataFrame:
    return _run(_pii_sample_sql(limit), client=_default_client())


def pii_masked(limit: int = 8) -> pd.DataFrame:
    return _run(_pii_sample_sql(limit), client=_masked_client())


# --- Churn risk (extra insight) ----------------------------------------------
def churn_drivers() -> pd.DataFrame:
    return _run(f"""
        SELECT
          churn_risk_segment AS band,
          COUNT(*) AS customers,
          ROUND(AVG(atm_withdrawals_last_30_days), 1) AS avg_atm_withdrawals,
          ROUND(AVG(total_savings_balance), 0) AS avg_savings,
          ROUND(SAFE_DIVIDE(COUNTIF(cc_spend_last_30_days = 0), COUNT(*)), 3) AS pct_dormant_card,
          ROUND(SUM(total_savings_balance), 0) AS savings_at_risk
        FROM {MART}
        GROUP BY band
        ORDER BY band
    """)


def churn_score_distribution() -> pd.DataFrame:
    return _run(f"SELECT churn_risk_score, churn_risk_segment AS band FROM {MART}")


def churn_by_age_band() -> pd.DataFrame:
    return _run(f"""
        SELECT {AGE_BAND_SQL} AS age_band, churn_risk_segment AS band, COUNT(*) AS customers
        FROM {MART}
        GROUP BY age_band, band
        ORDER BY age_band
    """)


# --- Marketing / NBA (extra insight) -----------------------------------------
def propensity_distribution() -> pd.DataFrame:
    return _run(f"SELECT investment_propensity_score, propensity_score_segment AS segment FROM {MART}")


def spend_by_category_segment() -> pd.DataFrame:
    return _run(f"""
        SELECT propensity_score_segment AS segment, top_spending_category AS category,
               COUNT(*) AS customers
        FROM {MART}
        WHERE top_spending_category != 'NONE'
        GROUP BY segment, category
    """)


def cross_sell_opportunities() -> pd.DataFrame:
    """Customers to scatter for cross-sell: savings vs CC spend, flagged by mortgage holding."""
    return _run(f"""
        SELECT customer_id, total_savings_balance, cc_spend_last_30_days,
               investment_propensity_score, has_active_mortgage, propensity_score_segment
        FROM {MART}
    """)


def hnw_no_mortgage(limit: int = 50) -> pd.DataFrame:
    return _run(f"""
        SELECT customer_id, full_name, total_savings_balance, total_deposit_balance,
               investment_propensity_score, top_spending_category
        FROM {MART}
        WHERE total_savings_balance > 100000 AND has_active_mortgage = FALSE
        ORDER BY total_savings_balance DESC
        LIMIT {limit}
    """)


# --- Spend & transaction trends ----------------------------------------------
def daily_spend() -> pd.DataFrame:
    """Daily debit-vs-credit purchase spend over the trailing 90 days."""
    return _run(f"""
        WITH tx AS (
          SELECT transaction_date AS d, 'Credit' AS channel, transaction_amount AS amt
          FROM {FCT_CC} WHERE transaction_type = 'DEBIT'
          UNION ALL
          SELECT transaction_date, 'Debit', transaction_amount
          FROM {FCT_DC} WHERE transaction_type = 'DEBIT'
        )
        SELECT d AS txn_date, channel, ROUND(SUM(amt), 2) AS spend
        FROM tx
        WHERE d >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
        GROUP BY txn_date, channel
        ORDER BY txn_date
    """)


def weekly_category_mix() -> pd.DataFrame:
    return _run(f"""
        WITH tx AS (
          SELECT transaction_date AS d, spending_category AS cat, transaction_amount AS amt
          FROM {FCT_CC} WHERE transaction_type = 'DEBIT'
          UNION ALL
          SELECT transaction_date, spending_category, transaction_amount
          FROM {FCT_DC} WHERE transaction_type = 'DEBIT'
        )
        SELECT DATE_TRUNC(d, WEEK) AS week, cat AS category, ROUND(SUM(amt), 2) AS spend
        FROM tx
        WHERE d >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
        GROUP BY week, category
        ORDER BY week
    """)


def atm_trend() -> pd.DataFrame:
    return _run(f"""
        SELECT DATE_TRUNC(transaction_date, WEEK) AS week,
               COUNT(*) AS withdrawals, ROUND(SUM(transaction_amount), 2) AS amount
        FROM {FCT_DC}
        WHERE is_atm_withdrawal
          AND transaction_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
        GROUP BY week
        ORDER BY week
    """)
