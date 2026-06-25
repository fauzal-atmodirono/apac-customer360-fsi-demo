import "server-only";
import { runQuery, PROJECT, GOLD, SILVER, MART, PERS, DIM_CUSTOMERS, FCT_CC, FCT_DC, DIM_PRODUCTS, FCT_HOLDINGS, FCT_ACCT_TXN, MART_CASHFLOW, MART_CAMPAIGNS, MART_KPI_HISTORY, FCT_FINREPAY, FCT_TRANSFERS, FCT_TELLER, MART_FINANCING, MART_TRANSFERS, MART_PROFIT, MART_CHANNEL } from "./bigquery";
import { money } from "./format";

// Server-side BigQuery Standard SQL for the dashboard API routes.
// Aggregates are CAST to FLOAT64 so the JSON carries plain JS numbers.
const q = runQuery;

const AGE_BAND = `CASE WHEN age<30 THEN '18-29' WHEN age<45 THEN '30-44' WHEN age<60 THEN '45-59' ELSE '60+' END`;

export async function executiveData() {
  const [kpis, segments, age, tier, portfolio, snap, hist, metrics, aumTrend] = await Promise.all([
    q(`SELECT COUNT(*) AS customers,
         CAST(SUM(total_savings_balance) AS FLOAT64) AS total_savings,
         CAST(SUM(total_deposit_balance) AS FLOAT64) AS total_deposit,
         CAST(SUM(total_loan_outstanding) AS FLOAT64) AS total_loans,
         CAST(AVG(investment_propensity_score) AS FLOAT64) AS avg_ips,
         CAST(AVG(age) AS FLOAT64) AS avg_age,
         CAST(SUM(total_card_spend_last_30_days) AS FLOAT64) AS total_card_spend,
         CAST(SAFE_DIVIDE(COUNTIF(has_active_mortgage), COUNT(*)) AS FLOAT64) AS pct_mortgage,
         CAST(SAFE_DIVIDE(SUM(total_loan_outstanding), SUM(total_savings_balance)) AS FLOAT64) AS ltv
       FROM ${MART}`),
    q(`SELECT propensity_score_segment AS segment, COUNT(*) AS customers,
         CAST(AVG(total_savings_balance) AS FLOAT64) AS avg_savings,
         CAST(AVG(total_card_spend_last_30_days) AS FLOAT64) AS avg_card_spend
       FROM ${MART} GROUP BY segment ORDER BY customers DESC`),
    q(`SELECT age, propensity_score_segment AS segment FROM ${MART}`),
    q(`SELECT customer_segment AS tier, propensity_score_segment AS segment, COUNT(*) AS customers
       FROM ${MART} GROUP BY tier, segment`),
    q(`SELECT 'Savings' AS pool, CAST(SUM(total_savings_balance) AS FLOAT64) AS amount FROM ${MART}
       UNION ALL SELECT 'Deposits', CAST(SUM(total_deposit_balance) AS FLOAT64) FROM ${MART}
       UNION ALL SELECT 'Loans', CAST(SUM(total_loan_outstanding) AS FLOAT64) FROM ${MART}`),
    q(`SELECT base_customers, base_card_spend, base_total_savings, base_total_loans,
              base_avg_ips, base_pct_mortgage, base_ltv
       FROM \`${PROJECT}.${GOLD}.kpi_snapshots\` ORDER BY snapshot_date DESC LIMIT 1`),
    // Real month-over-month from balance/txn history (latest two months).
    q(`SELECT customers, total_savings, total_card_spend
       FROM ${MART_KPI_HISTORY} ORDER BY month DESC LIMIT 2`),
    // Board-level cross-mart headline metrics (scalar sub-queries over the Gold marts).
    q(`SELECT
         (SELECT CAST(SUM(total_savings_balance + total_deposit_balance) AS FLOAT64) FROM ${MART}) AS aum,
         (SELECT CAST(AVG(n) AS FLOAT64) FROM (SELECT COUNT(DISTINCT product_code) AS n FROM ${FCT_HOLDINGS} GROUP BY customer_id)) AS avg_products,
         (SELECT CAST(SAFE_DIVIDE(COUNTIF(has_salary), COUNT(*)) AS FLOAT64) FROM ${MART_CASHFLOW}) AS primary_bank,
         (SELECT CAST(AVG(wellness_score) AS FLOAT64) FROM ${MART_CASHFLOW}) AS avg_wellness,
         (SELECT CAST(SAFE_DIVIDE(COUNTIF(is_npf), COUNT(*)) AS FLOAT64) FROM ${MART_FINANCING}) AS npf_rate,
         (SELECT CAST(SUM(total_arrears) AS FLOAT64) FROM ${MART_FINANCING}) AS arrears,
         (SELECT COUNTIF(churn_risk_segment IN ('HIGH','MEDIUM')) FROM ${MART}) AS at_risk,
         (SELECT CAST(SUM(IF(churn_risk_segment IN ('HIGH','MEDIUM'), total_savings_balance, 0)) AS FLOAT64) FROM ${MART}) AS at_risk_dollars,
         (SELECT CAST(SUM(total_profit_paid) AS FLOAT64) FROM ${MART_PROFIT}) AS profit_paid,
         (SELECT CAST(AVG(NULLIF(effective_yield, 0)) AS FLOAT64) FROM ${MART_PROFIT}) AS avg_yield,
         (SELECT CAST(SUM(total_fees) AS FLOAT64) FROM ${MART_TRANSFERS}) AS fee_income,
         (SELECT CAST(AVG(digital_ratio) AS FLOAT64) FROM ${MART_CHANNEL}) AS digital_ratio,
         (SELECT CAST(SAFE_DIVIDE(SUM(converted), SUM(sent)) AS FLOAT64) FROM ${MART_CAMPAIGNS}) AS conv_rate`),
    q(`SELECT FORMAT_DATE('%Y-%m', month) AS month, CAST(total_savings AS FLOAT64) AS savings,
              CAST(total_deposits AS FLOAT64) AS deposits FROM ${MART_KPI_HISTORY} ORDER BY month`),
  ]);
  const k = kpis[0] as Record<string, number>;
  const b = (snap[0] ?? {}) as Record<string, number>;
  const g = (cur: number, base?: number) =>
    base && base !== 0 ? ((Number(cur) - Number(base)) / Number(base)) * 100 : null;
  // Real month-over-month: latest vs prior month from mart_kpi_history.
  const cur = (hist[0] ?? {}) as Record<string, number>;
  const prev = (hist[1] ?? {}) as Record<string, number>;
  const growth = {
    customers: g(cur.customers, prev.customers) ?? g(k.customers, b.base_customers),
    total_savings: g(cur.total_savings, prev.total_savings) ?? g(k.total_savings, b.base_total_savings),
    total_card_spend: g(cur.total_card_spend, prev.total_card_spend) ?? g(k.total_card_spend, b.base_card_spend),
    // point-in-time metrics keep the seeded baseline (no monthly history available)
    total_loans: g(k.total_loans, b.base_total_loans),
    avg_ips: g(k.avg_ips, b.base_avg_ips),
    pct_mortgage: g(k.pct_mortgage, b.base_pct_mortgage),
    ltv: g(k.ltv, b.base_ltv),
  };
  return { kpis: k, growth, segments, age, tier, portfolio, metrics: metrics[0], aumTrend };
}

export async function demographicsData() {
  const [regions, income, tenure] = await Promise.all([
    q(`SELECT region, COUNT(*) AS customers,
         CAST(SUM(total_savings_balance) AS FLOAT64) AS total_savings,
         CAST(AVG(investment_propensity_score) AS FLOAT64) AS avg_ips
       FROM ${MART} GROUP BY region ORDER BY customers DESC`),
    q(`SELECT income_band, COUNT(*) AS customers,
         CAST(AVG(total_savings_balance) AS FLOAT64) AS avg_savings,
         CAST(AVG(annual_income) AS FLOAT64) AS avg_income
       FROM ${MART} GROUP BY income_band`),
    q(`SELECT CASE WHEN tenure_years<3 THEN '0-2 yrs' WHEN tenure_years<7 THEN '3-6 yrs'
                   WHEN tenure_years<12 THEN '7-11 yrs' ELSE '12+ yrs' END AS tenure_band,
         COUNT(*) AS customers,
         CAST(AVG(total_savings_balance) AS FLOAT64) AS avg_savings,
         CAST(AVG(churn_risk_score) AS FLOAT64) AS avg_churn
       FROM ${MART} GROUP BY tenure_band ORDER BY tenure_band`),
  ]);
  return { regions, income, tenure };
}

export async function churnData() {
  const [drivers, bands, scatter, scoreDist, byAge, list] = await Promise.all([
    q(`SELECT churn_risk_segment AS band, COUNT(*) AS customers,
         CAST(AVG(atm_withdrawals_last_30_days) AS FLOAT64) AS avg_atm,
         CAST(AVG(total_savings_balance) AS FLOAT64) AS avg_savings,
         CAST(SAFE_DIVIDE(COUNTIF(cc_spend_last_30_days=0), COUNT(*)) AS FLOAT64) AS pct_dormant,
         CAST(SUM(total_savings_balance) AS FLOAT64) AS savings_at_risk
       FROM ${MART} GROUP BY band ORDER BY band`),
    q(`SELECT churn_risk_segment AS band, COUNT(*) AS customers FROM ${MART} GROUP BY band`),
    q(`SELECT customer_id, churn_risk_segment AS band,
         CAST(churn_risk_score AS FLOAT64) AS churn_risk_score,
         atm_withdrawals_last_30_days AS atm,
         CAST(total_savings_balance AS FLOAT64) AS savings
       FROM ${MART}`),
    q(`SELECT CAST(churn_risk_score AS FLOAT64) AS churn_risk_score, churn_risk_segment AS band FROM ${MART}`),
    q(`SELECT ${AGE_BAND} AS age_band, churn_risk_segment AS band, COUNT(*) AS customers
       FROM ${MART} GROUP BY age_band, band ORDER BY age_band`),
    q(`SELECT customer_id, full_name, churn_risk_segment AS band,
         CAST(churn_risk_score AS FLOAT64) AS churn_risk_score,
         atm_withdrawals_last_30_days AS atm,
         CAST(total_savings_balance AS FLOAT64) AS savings
       FROM ${MART} WHERE churn_risk_segment IN ('HIGH','MEDIUM')
       ORDER BY churn_risk_score DESC LIMIT 50`),
  ]);
  return { drivers, bands, scatter, scoreDist, byAge, list };
}

export async function marketingData() {
  const [categories, ipsDist, catBySegment, crossSell, hnwTargets, hnwNoMortgage] = await Promise.all([
    q(`SELECT top_spending_category AS category, COUNT(*) AS customers
       FROM ${MART} WHERE top_spending_category!='NONE' GROUP BY category ORDER BY customers DESC`),
    q(`SELECT CAST(investment_propensity_score AS FLOAT64) AS ips, propensity_score_segment AS segment FROM ${MART}`),
    q(`SELECT propensity_score_segment AS segment, top_spending_category AS category, COUNT(*) AS customers
       FROM ${MART} WHERE top_spending_category!='NONE' GROUP BY segment, category`),
    q(`SELECT customer_id, CAST(total_savings_balance AS FLOAT64) AS savings,
         CAST(cc_spend_last_30_days AS FLOAT64) AS cc_spend,
         CAST(investment_propensity_score AS FLOAT64) AS ips, has_active_mortgage
       FROM ${MART}`),
    q(`SELECT customer_id, full_name, customer_segment,
         CAST(total_savings_balance AS FLOAT64) AS savings,
         CAST(total_loan_outstanding AS FLOAT64) AS loans,
         top_spending_category, CAST(investment_propensity_score AS FLOAT64) AS ips
       FROM ${MART} WHERE propensity_score_segment='HNW_INVESTOR'
       ORDER BY investment_propensity_score DESC LIMIT 50`),
    q(`SELECT customer_id, full_name, CAST(total_savings_balance AS FLOAT64) AS savings,
         CAST(total_deposit_balance AS FLOAT64) AS deposits,
         CAST(investment_propensity_score AS FLOAT64) AS ips, top_spending_category
       FROM ${MART} WHERE total_savings_balance>100000 AND has_active_mortgage=FALSE
       ORDER BY total_savings_balance DESC LIMIT 50`),
  ]);
  return { categories, ipsDist, catBySegment, crossSell, hnwTargets, hnwNoMortgage };
}

const TX90 = `WITH tx AS (
  SELECT transaction_date AS d, time_of_day, transaction_hour AS hr, day_of_week, day_of_week_num, day_group, transaction_amount AS amt
  FROM ${FCT_CC} WHERE transaction_type='DEBIT'
  UNION ALL
  SELECT transaction_date, time_of_day, transaction_hour, day_of_week, day_of_week_num, day_group, transaction_amount
  FROM ${FCT_DC} WHERE transaction_type='DEBIT')`;

export async function trendsData() {
  const [daily, weekly, atm, byTimeOfDay, byHour, byDayGroup, byDayOfWeek] = await Promise.all([
    q(`WITH tx AS (
         SELECT transaction_date AS d, 'Credit' AS channel, transaction_amount AS amt FROM ${FCT_CC} WHERE transaction_type='DEBIT'
         UNION ALL SELECT transaction_date, 'Debit', transaction_amount FROM ${FCT_DC} WHERE transaction_type='DEBIT')
       SELECT CAST(d AS STRING) AS txn_date, channel, CAST(SUM(amt) AS FLOAT64) AS spend
       FROM tx WHERE d>=DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
       GROUP BY txn_date, channel ORDER BY txn_date`),
    q(`WITH tx AS (
         SELECT transaction_date AS d, spending_category AS cat, transaction_amount AS amt FROM ${FCT_CC} WHERE transaction_type='DEBIT'
         UNION ALL SELECT transaction_date, spending_category, transaction_amount FROM ${FCT_DC} WHERE transaction_type='DEBIT')
       SELECT CAST(DATE_TRUNC(d, WEEK) AS STRING) AS week, cat AS category, CAST(SUM(amt) AS FLOAT64) AS spend
       FROM tx WHERE d>=DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
       GROUP BY week, category ORDER BY week`),
    q(`SELECT CAST(DATE_TRUNC(transaction_date, WEEK) AS STRING) AS week,
         COUNT(*) AS withdrawals, CAST(SUM(transaction_amount) AS FLOAT64) AS amount
       FROM ${FCT_DC} WHERE is_atm_withdrawal AND transaction_date>=DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
       GROUP BY week ORDER BY week`),
    // --- transaction timing (90d, cc+dc purchases) ---
    q(`${TX90} SELECT time_of_day, COUNT(*) AS txns, CAST(SUM(amt) AS FLOAT64) AS spend
       FROM tx WHERE d>=DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY) GROUP BY time_of_day`),
    q(`${TX90} SELECT hr AS hour, COUNT(*) AS txns, CAST(SUM(amt) AS FLOAT64) AS spend
       FROM tx WHERE d>=DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY) GROUP BY hour ORDER BY hour`),
    q(`${TX90} SELECT day_group, COUNT(*) AS txns, CAST(SUM(amt) AS FLOAT64) AS spend,
              COUNT(DISTINCT d) AS active_days
       FROM tx WHERE d>=DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY) GROUP BY day_group`),
    q(`${TX90} SELECT day_of_week, ANY_VALUE(day_of_week_num) AS dow_num,
              COUNT(*) AS txns, CAST(SUM(amt) AS FLOAT64) AS spend
       FROM tx WHERE d>=DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY) GROUP BY day_of_week ORDER BY dow_num`),
  ]);
  return { daily, weekly, atm, byTimeOfDay, byHour, byDayGroup, byDayOfWeek };
}

const PII_SAMPLE = (limit: number) => `
  WITH cards AS (SELECT customer_id, ANY_VALUE(card_number) AS card_number FROM ${FCT_CC} GROUP BY customer_id)
  SELECT c.customer_id, c.full_name, c.phone_number, c.address, cards.card_number
  FROM ${DIM_CUSTOMERS} c LEFT JOIN cards USING (customer_id)
  ORDER BY c.customer_id LIMIT ${limit}`;

export async function governanceData() {
  const [cleartext, masked] = await Promise.all([
    q(PII_SAMPLE(8)),
    q(PII_SAMPLE(8), { masked: true }),
  ]);
  return { cleartext, masked };
}

// --- Individual customer (list + detail) -------------------------------------
export async function customerList() {
  return q(`
    SELECT customer_id, full_name, customer_segment, region,
           CAST(total_savings_balance AS FLOAT64) AS savings,
           CAST(investment_propensity_score AS FLOAT64) AS ips,
           propensity_score_segment, churn_risk_segment
    FROM ${MART}
    ORDER BY total_savings_balance DESC
  `);
}

type Mart = Record<string, number | string | boolean | null>;

function nextBestActions(m: Mart) {
  const out: { title: string; reason: string; priority: "High" | "Medium" | "Low" }[] = [];
  const seg = String(m.propensity_score_segment);
  const ips = Number(m.investment_propensity_score);
  const savings = Number(m.total_savings_balance);
  const deposits = Number(m.total_deposit_balance);
  const ccSpend = Number(m.cc_spend_last_30_days);
  const ddr = Number(m.debt_to_deposit_ratio);
  const churn = String(m.churn_risk_segment);

  if (churn === "HIGH" || churn === "MEDIUM")
    out.push({ title: "Retention outreach", reason: `Churn risk is ${churn} — proactive loyalty offer / fee waiver before defection.`, priority: churn === "HIGH" ? "High" : "Medium" });
  if (!m.has_active_mortgage && savings > 100000)
    out.push({ title: "Home-loan cross-sell", reason: `Holds ${money(savings)} in savings with no mortgage — strong home-lending lead.`, priority: "High" });
  if (seg === "HNW_INVESTOR" || ips >= 70)
    out.push({ title: "Term deposit / wealth advisory", reason: `Investment propensity ${ips.toFixed(0)}/100 — pitch high-yield term deposit or advisory.`, priority: "High" });
  if (deposits === 0 && savings > 20000)
    out.push({ title: "Move idle cash to term deposit", reason: `${money(savings)} savings but no term deposit — convert idle balances.`, priority: "Medium" });
  if (seg === "DIGITAL_SHOPPER" || ccSpend > 5000)
    out.push({ title: "Premium rewards card", reason: `High card spend (${money(ccSpend)}/30d) — upgrade to a cashback/rewards card.`, priority: "Medium" });
  if (seg === "LEVERAGED_BORROWER" || ddr > 5)
    out.push({ title: "Debt consolidation", reason: `Debt-to-deposit ratio ${ddr.toFixed(1)} — offer restructuring / consolidation.`, priority: "High" });
  if (!out.length)
    out.push({ title: "Maintain & monitor", reason: "Healthy, stable profile — standard engagement cadence.", priority: "Low" });
  return out;
}

export async function cashflowData() {
  const [bands, primary, trend, kpis, profit] = await Promise.all([
    q(`SELECT wellness_band AS band, COUNT(*) AS customers FROM ${MART_CASHFLOW} GROUP BY 1`),
    q(`SELECT has_salary AS primary_bank, COUNT(*) AS customers FROM ${MART_CASHFLOW} GROUP BY 1`),
    q(`SELECT FORMAT_DATE('%Y-%m', DATE_TRUNC(txn_date, MONTH)) AS month,
              CAST(SUM(IF(direction='CREDIT', amount, 0)) AS FLOAT64) AS inflow,
              CAST(SUM(IF(direction='DEBIT', amount, 0)) AS FLOAT64) AS outflow
       FROM ${FCT_ACCT_TXN} GROUP BY 1 ORDER BY 1`),
    q(`SELECT CAST(AVG(wellness_score) AS FLOAT64) AS avg_wellness,
              CAST(AVG(surplus_margin) AS FLOAT64) AS avg_savings_rate,
              CAST(SAFE_DIVIDE(COUNTIF(has_salary), COUNT(*)) AS FLOAT64) AS pct_primary,
              COUNTIF(wellness_band='Stretched') AS stretched
       FROM ${MART_CASHFLOW}`),
    q(`SELECT CAST(SUM(total_profit_paid) AS FLOAT64) AS total_profit,
              CAST(AVG(NULLIF(effective_yield,0)) AS FLOAT64) AS avg_yield,
              COUNT(*) AS earners FROM ${MART_PROFIT}`),
  ]);
  return { bands, primary, trend, kpis: kpis[0], profit: profit[0] };
}

export async function financingHealthData() {
  const ARREARS_ORDER = ["Current", "1-30", "31-60", "61-90", "90+"];
  const [buckets, dpd, kpis, worst] = await Promise.all([
    q(`SELECT arrears_bucket AS bucket, COUNT(*) AS customers, CAST(SUM(total_arrears) AS FLOAT64) AS arrears
       FROM ${MART_FINANCING} GROUP BY 1`),
    q(`SELECT current_dpd AS dpd FROM ${MART_FINANCING} WHERE current_dpd > 0`),
    q(`SELECT COUNT(*) AS financed, COUNTIF(is_npf) AS npf,
              CAST(SAFE_DIVIDE(COUNTIF(is_npf), COUNT(*)) AS FLOAT64) AS npf_rate,
              CAST(AVG(on_time_rate) AS FLOAT64) AS avg_on_time,
              CAST(SUM(total_arrears) AS FLOAT64) AS total_arrears
       FROM ${MART_FINANCING}`),
    q(`SELECT f.customer_id, c.full_name, c.customer_segment, f.current_dpd, f.arrears_bucket,
              CAST(f.total_arrears AS FLOAT64) AS total_arrears
       FROM ${MART_FINANCING} f JOIN ${DIM_CUSTOMERS} c USING(customer_id)
       WHERE f.current_dpd > 0 ORDER BY f.current_dpd DESC, f.total_arrears DESC LIMIT 20`),
  ]);
  (buckets as { bucket: string }[]).sort((a, b) => ARREARS_ORDER.indexOf(a.bucket) - ARREARS_ORDER.indexOf(b.bucket));
  return { buckets, dpd, kpis: kpis[0], worst };
}

export async function paymentsData() {
  const [byType, corridors, channels, cash, kpis] = await Promise.all([
    q(`SELECT transfer_type AS type, COUNT(*) AS txns, CAST(SUM(amount) AS FLOAT64) AS value,
              CAST(SUM(fee) AS FLOAT64) AS fees
       FROM ${FCT_TRANSFERS} GROUP BY 1 ORDER BY value DESC`),
    q(`SELECT beneficiary_country AS corridor, COUNT(*) AS txns, CAST(SUM(amount) AS FLOAT64) AS value
       FROM ${FCT_TRANSFERS} WHERE transfer_type='INTL' GROUP BY 1 ORDER BY value DESC`),
    q(`SELECT channel, COUNT(*) AS txns, CAST(SUM(amount) AS FLOAT64) AS amount
       FROM ${FCT_TELLER} GROUP BY 1 ORDER BY txns DESC`),
    q(`SELECT txn_type AS type, CAST(SUM(amount) AS FLOAT64) AS amount FROM ${FCT_TELLER} GROUP BY 1`),
    q(`SELECT (SELECT COUNT(*) FROM ${FCT_TRANSFERS}) AS transfers,
              (SELECT CAST(SUM(fee) AS FLOAT64) FROM ${FCT_TRANSFERS}) AS fee_income,
              (SELECT COUNT(DISTINCT customer_id) FROM ${FCT_TRANSFERS} WHERE transfer_type='INTL') AS remitters,
              (SELECT CAST(AVG(digital_ratio) AS FLOAT64) FROM ${MART_CHANNEL}) AS avg_digital`),
  ]);
  return { byType, corridors, channels, cash, kpis: kpis[0] };
}

export async function campaignsData() {
  const [campaigns, byChannel, kpis] = await Promise.all([
    q(`SELECT campaign_name, product_name, channel, sent, opened, clicked, converted,
              CAST(conversion_rate AS FLOAT64) AS conversion_rate, CAST(roi AS FLOAT64) AS roi
       FROM ${MART_CAMPAIGNS} ORDER BY conversion_rate DESC`),
    q(`SELECT channel, SUM(sent) AS sent, SUM(converted) AS converted,
              CAST(SAFE_DIVIDE(SUM(converted), SUM(sent)) AS FLOAT64) AS conversion_rate
       FROM ${MART_CAMPAIGNS} GROUP BY 1 ORDER BY conversion_rate DESC`),
    q(`SELECT SUM(sent) AS sent, SUM(opened) AS opened, SUM(clicked) AS clicked, SUM(converted) AS converted,
              CAST(SAFE_DIVIDE(SUM(converted), SUM(sent)) AS FLOAT64) AS conversion_rate,
              CAST(AVG(roi) AS FLOAT64) AS avg_roi
       FROM ${MART_CAMPAIGNS}`),
  ]);
  return { campaigns, byChannel, kpis: kpis[0] };
}

export async function socialFinanceData() {
  const [byType, monthly, hajj, itekad, kpis] = await Promise.all([
    q(`SELECT category AS type, COUNT(DISTINCT customer_id) AS contributors, CAST(SUM(amount) AS FLOAT64) AS total
       FROM ${FCT_ACCT_TXN} WHERE category IN ('ZAKAT','SADAQAH','WAKAF') GROUP BY 1 ORDER BY total DESC`),
    q(`SELECT FORMAT_DATE('%Y-%m', DATE_TRUNC(txn_date, MONTH)) AS month, category AS type,
              CAST(SUM(amount) AS FLOAT64) AS total
       FROM ${FCT_ACCT_TXN} WHERE category IN ('ZAKAT','SADAQAH','WAKAF') GROUP BY 1,2 ORDER BY 1`),
    q(`SELECT COUNT(DISTINCT h.customer_id) AS customers
       FROM ${FCT_HOLDINGS} h WHERE h.product_code = 'SVC-HAJJ'`),
    q(`SELECT COUNT(DISTINCT h.customer_id) AS customers, CAST(SUM(h.balance) AS FLOAT64) AS total
       FROM ${FCT_HOLDINGS} h WHERE h.product_code = 'FIN-ITEKAD'`),
    q(`SELECT COUNT(DISTINCT customer_id) AS zakat_payers,
              CAST(SUM(IF(category='ZAKAT', amount, 0)) AS FLOAT64) AS zakat_total
       FROM ${FCT_ACCT_TXN} WHERE category IN ('ZAKAT','SADAQAH','WAKAF')`),
  ]);
  return { byType, monthly, hajj: hajj[0], itekad: itekad[0], kpis: kpis[0] };
}

export async function productsData() {
  const [catalog, byCategory, perCustomer, kpis] = await Promise.all([
    q(`SELECT p.product_code, p.product_name, p.category, p.islamic_contract, p.product_type,
              CAST(p.indicative_rate AS FLOAT64) AS indicative_rate,
              COUNT(DISTINCT h.customer_id) AS holders
       FROM ${DIM_PRODUCTS} p LEFT JOIN ${FCT_HOLDINGS} h USING(product_code)
       GROUP BY 1,2,3,4,5,6 ORDER BY p.category, holders DESC`),
    q(`SELECT p.category, COUNT(DISTINCT h.customer_id) AS holders, COUNT(*) AS holdings
       FROM ${DIM_PRODUCTS} p LEFT JOIN ${FCT_HOLDINGS} h USING(product_code)
       GROUP BY 1 ORDER BY holders DESC`),
    q(`SELECT products, COUNT(*) AS customers FROM (
         SELECT customer_id, COUNT(DISTINCT product_code) AS products
         FROM ${FCT_HOLDINGS} GROUP BY 1) GROUP BY 1 ORDER BY products`),
    q(`SELECT
         (SELECT COUNT(*) FROM ${DIM_PRODUCTS}) AS catalog_size,
         CAST((SELECT COUNT(DISTINCT product_code) FROM ${FCT_HOLDINGS}) AS FLOAT64) AS products_held,
         CAST(AVG(n) AS FLOAT64) AS avg_products
       FROM (SELECT COUNT(DISTINCT product_code) AS n FROM ${FCT_HOLDINGS} GROUP BY customer_id)`),
  ]);
  return { catalog, byCategory, perCustomer, kpis: kpis[0] };
}

export async function customerDetail(id: string) {
  const p = { params: { id } };
  const [mart, dim, accounts, loans, trend, categories, recent, signals, holdings, cashflow, finhealth, channel] = await Promise.all([
    q(`SELECT * FROM ${MART} WHERE customer_id = @id`, p),
    q(`SELECT address, customer_since FROM ${DIM_CUSTOMERS} WHERE customer_id = @id`, p),
    q(`SELECT account_id, account_type, CAST(balance AS FLOAT64) AS balance, status_desc,
              CAST(open_date AS STRING) AS open_date
       FROM \`${PROJECT}.${SILVER}.dim_accounts\` WHERE customer_id = @id ORDER BY balance DESC`, p),
    q(`SELECT loan_id, loan_type, CAST(principal_amount AS FLOAT64) AS principal,
              CAST(outstanding_balance AS FLOAT64) AS outstanding,
              CAST(monthly_installment AS FLOAT64) AS monthly, CAST(next_due_date AS STRING) AS next_due
       FROM \`${PROJECT}.${SILVER}.dim_loans\` WHERE customer_id = @id ORDER BY outstanding DESC`, p),
    q(`WITH tx AS (
         SELECT transaction_date AS d, 'Credit' AS channel, transaction_amount AS amt FROM ${FCT_CC} WHERE customer_id=@id AND transaction_type='DEBIT'
         UNION ALL SELECT transaction_date, 'Debit', transaction_amount FROM ${FCT_DC} WHERE customer_id=@id AND transaction_type='DEBIT')
       SELECT CAST(DATE_TRUNC(d, WEEK) AS STRING) AS week, channel, CAST(SUM(amt) AS FLOAT64) AS spend
       FROM tx WHERE d >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY) GROUP BY week, channel ORDER BY week`, p),
    q(`WITH tx AS (
         SELECT spending_category AS cat, transaction_amount AS amt FROM ${FCT_CC} WHERE customer_id=@id AND transaction_type='DEBIT'
         UNION ALL SELECT spending_category, transaction_amount FROM ${FCT_DC} WHERE customer_id=@id AND transaction_type='DEBIT')
       SELECT cat AS category, CAST(SUM(amt) AS FLOAT64) AS spend FROM tx GROUP BY category ORDER BY spend DESC`, p),
    q(`SELECT * FROM (
         SELECT CAST(transaction_date AS STRING) AS date, 'Credit' AS channel, spending_category AS category,
                CAST(transaction_amount AS FLOAT64) AS amount, transaction_type AS type FROM ${FCT_CC} WHERE customer_id=@id
         UNION ALL SELECT CAST(transaction_date AS STRING), 'Debit', spending_category,
                CAST(transaction_amount AS FLOAT64), transaction_type FROM ${FCT_DC} WHERE customer_id=@id)
       ORDER BY date DESC LIMIT 15`, p),
    q(`SELECT * FROM ${PERS} WHERE customer_id = @id`, p),
    q(`SELECT pr.product_name, pr.category, pr.islamic_contract, h.holding_kind,
              h.status, CAST(h.open_date AS STRING) AS open_date, CAST(h.balance AS FLOAT64) AS balance
       FROM ${FCT_HOLDINGS} h JOIN ${DIM_PRODUCTS} pr USING(product_code)
       WHERE h.customer_id = @id ORDER BY pr.category, h.balance DESC`, p),
    q(`SELECT monthly_inflow, monthly_outflow, net_surplus, salary_amount, has_salary,
              savings_rate, wellness_score, wellness_band FROM ${MART_CASHFLOW} WHERE customer_id = @id`, p),
    q(`SELECT current_dpd, arrears_bucket, is_npf, on_time_rate, total_arrears
       FROM ${MART_FINANCING} WHERE customer_id = @id`, p),
    q(`SELECT primary_channel, digital_ratio, branch_count, atm_count, cdm_count
       FROM ${MART_CHANNEL} WHERE customer_id = @id`, p),
  ]);
  const profile = mart[0] ? { ...(mart[0] as Mart), ...(dim[0] ?? {}) } : null;
  return {
    profile,
    accounts, loans, trend, categories, recent, holdings,
    signals: signals[0] ?? null,
    cashflow: cashflow[0] ?? null,
    finhealth: finhealth[0] ?? null,
    channel: channel[0] ?? null,
    nba: profile ? nextBestActions(mart[0] as Mart) : [],
  };
}

export async function personalizationData() {
  const [rfm, health, nbp, sow, kpis] = await Promise.all([
    q(`SELECT rfm_segment, COUNT(*) AS customers FROM ${PERS} GROUP BY 1 ORDER BY customers DESC`),
    q(`SELECT financial_health_band AS band, COUNT(*) AS customers FROM ${PERS} GROUP BY 1`),
    q(`SELECT nbp_top AS product, COUNT(*) AS customers FROM ${PERS} GROUP BY 1 ORDER BY customers DESC`),
    q(`SELECT CASE
              WHEN share_of_wallet < 0.1 THEN '0-10%'
              WHEN share_of_wallet < 0.25 THEN '10-25%'
              WHEN share_of_wallet < 0.5 THEN '25-50%'
              WHEN share_of_wallet < 1 THEN '50-100%'
              ELSE '100%+' END AS band,
            COUNT(*) AS customers
       FROM ${PERS} GROUP BY 1`),
    q(`SELECT CAST(AVG(financial_health_score) AS FLOAT64) AS avg_health,
              CAST(AVG(share_of_wallet) AS FLOAT64) AS avg_sow,
              COUNTIF(rfm_segment IN ('At risk','Hibernating')) AS at_risk,
              COUNTIF(financial_health_band='Stretched') AS stretched
       FROM ${PERS}`),
  ]);
  const SOW_ORDER = ["0-10%", "10-25%", "25-50%", "50-100%", "100%+"];
  (sow as { band: string }[]).sort((a, b) => SOW_ORDER.indexOf(a.band) - SOW_ORDER.indexOf(b.band));
  return { rfm, health, nbp, sow, kpis: kpis[0] };
}
