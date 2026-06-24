-- Seeds a prior-period (~30 days ago) baseline for the Executive KPI growth deltas.
-- The synthetic mock data has no recent sign-ups and is recent-spend-heavy, so a literal
-- period-over-period derivation is degenerate (0% customers / ~+90% spend). For a clean,
-- representative demo we seed each baseline as current × a small factor; loan-to-savings is
-- derived from the seeded savings/loans so it stays internally consistent. The snapshot
-- TABLE itself is the production-shaped part — a scheduled job would APPEND real daily rows.
CREATE OR REPLACE TABLE `demo_gold_analytics.kpi_snapshots` AS
WITH cur AS (
  SELECT
    COUNT(*) AS customers,
    SUM(total_savings_balance) AS savings,
    SUM(total_loan_outstanding) AS loans,
    AVG(investment_propensity_score) AS ips,
    SAFE_DIVIDE(COUNTIF(has_active_mortgage), COUNT(*)) AS pct_mortgage,
    SUM(total_card_spend_last_30_days) AS card_spend
  FROM `demo_gold_analytics.mart_customer_360`
)
SELECT
  DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) AS snapshot_date,
  CAST(ROUND(customers * 0.970) AS INT64) AS base_customers,          -- ~ +3.1%
  CAST(card_spend  * 0.930 AS FLOAT64)    AS base_card_spend,         -- ~ +7.5%
  CAST(savings     * 0.965 AS FLOAT64)    AS base_total_savings,      -- ~ +3.6%
  CAST(loans       * 0.980 AS FLOAT64)    AS base_total_loans,        -- ~ +2.0%
  CAST(ips         * 0.988 AS FLOAT64)    AS base_avg_ips,            -- ~ +1.2%
  CAST(pct_mortgage * 0.985 AS FLOAT64)   AS base_pct_mortgage,       -- ~ +1.5%
  CAST(SAFE_DIVIDE(loans * 0.980, savings * 0.965) AS FLOAT64) AS base_ltv
FROM cur;
