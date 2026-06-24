-- Customer 360 demo queries — hyper-personalization use cases (BRD section 2)
-- plus governance verification (PRD section 8). Replace `demo_gold_analytics`
-- with `<project>.demo_gold_analytics` if your session default project differs.

-- =====================================================================
-- 0. Persona sanity check — the three seeded archetypes should land in
--    the expected propensity_score_segment buckets.
-- =====================================================================
SELECT
  customer_id, customer_segment, total_savings_balance, total_loan_outstanding,
  cc_spend_last_30_days, atm_withdrawals_last_30_days,
  investment_propensity_score, propensity_score_segment,
  churn_risk_score, churn_risk_segment
FROM demo_gold_analytics.mart_customer_360
WHERE customer_id IN ('0010000001', '0010000002', '0010000003')
ORDER BY customer_id;
-- Expect: 0010000001=HNW_INVESTOR, 0010000002=LEVERAGED_BORROWER, 0010000003=DIGITAL_SHOPPER

-- =====================================================================
-- 1. Next-Best-Action — high-yield savings / rewards-card targeting.
--    HNW investors with idle liquidity and travel affinity.
-- =====================================================================
SELECT customer_id, full_name, total_savings_balance, top_spending_category,
       investment_propensity_score
FROM demo_gold_analytics.mart_customer_360
WHERE propensity_score_segment = 'HNW_INVESTOR'
   OR (investment_propensity_score >= 70 AND total_deposit_balance = 0)
ORDER BY investment_propensity_score DESC
LIMIT 100;

-- =====================================================================
-- 2. Credit scoring & pre-approval — screen for over-leverage before
--    extending offers (uses Debt-to-Deposit Ratio).
-- =====================================================================
SELECT customer_id, full_name, total_loan_outstanding, total_savings_balance,
       ROUND(debt_to_deposit_ratio, 2) AS dsr, has_active_mortgage
FROM demo_gold_analytics.mart_customer_360
WHERE has_active_mortgage = TRUE
  AND debt_to_deposit_ratio < 5.0          -- not dangerously leveraged
ORDER BY debt_to_deposit_ratio ASC
LIMIT 100;

-- =====================================================================
-- 3. Churn risk mitigation — customers showing cash-flight behavior:
--    frequent ATM withdrawals draining thin savings + dormant card usage.
--    Drives defensive retention / loyalty outreach before they defect.
-- =====================================================================
SELECT customer_id, full_name, phone_number,
       churn_risk_segment, churn_risk_score,
       atm_withdrawals_last_30_days, total_savings_balance,
       cc_spend_last_30_days, debit_spend_last_30_days
FROM demo_gold_analytics.mart_customer_360
WHERE churn_risk_segment IN ('HIGH', 'MEDIUM')
ORDER BY churn_risk_score DESC
LIMIT 100;

-- =====================================================================
-- 4. Life-stage marketing — age-band segmentation for lifecycle offers
--    (education savings, car loans, home insurance).
-- =====================================================================
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
FROM demo_gold_analytics.mart_customer_360
GROUP BY life_stage
ORDER BY life_stage;

-- =====================================================================
-- 5. Governance verification (PRD TC-2.1 / TC-2.2).
--    Run as different identities and compare the PII columns:
--      * Default analyst (masked):  full_name = SHA-256 hash,
--        phone_number = XXXX-XXXX-####, address resolves to NULL.
--      * Marketing (fine-grained):  full_name + phone_number in cleartext.
-- =====================================================================
SELECT customer_id, full_name, phone_number
FROM demo_gold_analytics.mart_customer_360
LIMIT 10;
