// Shared constants + helpers for the Customer 360 Dataform project.
// Available as the global `constants` object inside every .sqlx config/SQL block.

const vars = dataform.projectConfig.vars || {};

// Policy-tag resource names are created by Terraform and injected as compilation
// vars. See terraform/modules/governance + the orchestrator's --vars flag.
const POLICY_TAGS = {
  PII_NAME: vars.policy_tag_pii_name,
  PII_PHONE: vars.policy_tag_pii_phone,
  PII_ADDRESS: vars.policy_tag_pii_address,
  CARD_PAN: vars.policy_tag_card_pan,
};

// Investment Propensity Score weights / normalizers (PRD section 4.2).
const IPS = {
  W_SAVINGS: 0.7,
  W_DEBT: 0.3,
  SAVINGS_NORM: 100000,
  DEBT_NORM: 500000,
};

// Churn-risk model (BRD churn use case). ATM cash-out intensity is the dominant
// signal: frequent withdrawals draining a thin balance, alongside a dormant
// credit card, flag a customer who may be moving their money elsewhere.
const CHURN = {
  W_ATM: 0.45,          // weight on ATM cash-flight intensity
  W_THIN_SAVINGS: 0.35, // weight on how depleted the savings balance is
  W_DORMANT_CARD: 0.20, // weight on dormant credit-card activity
  ATM_NORM: 10,         // ATM withdrawals/30d that saturate the signal
  SAVINGS_FLOOR: 20000, // savings at/above which "thin" risk is zero
  HIGH_THRESHOLD: 60,
  MEDIUM_THRESHOLD: 35,
};

// SQL expression for the 0-100 churn-risk score. Expects the Gold query's CTE
// aliases in scope: dc (debit aggregates), s (savings), cc (credit card).
function churnRiskScoreSql() {
  return `ROUND(100 * (
      (${CHURN.W_ATM} * LEAST(1.0, COALESCE(dc.atm_withdrawals_last_30_days, 0) / ${CHURN.ATM_NORM}))
    + (${CHURN.W_THIN_SAVINGS} * (1 - LEAST(1.0, COALESCE(s.total_savings_balance, 0) / ${CHURN.SAVINGS_FLOOR})))
    + (${CHURN.W_DORMANT_CARD} * IF(COALESCE(cc.cc_spend_last_30_days, 0) = 0, 1, 0))
  ), 1)`;
}

// Hyper-personalization signal config (mart_personalization_signals). Discretionary
// vs essential category split + financial-health weights, kept here as the single
// source of truth alongside IPS/CHURN.
const PERSONALIZATION = {
  DISCRETIONARY: ["DINING", "TRAVEL", "ENTERTAINMENT", "DIGITAL", "RETAIL"],
  ESSENTIAL: ["GROCERY", "UTILITY", "FUEL", "HEALTH", "TRANSPORT", "ATM"],
  HEALTHY_BUFFER_MONTHS: 6, // savings covering 6+ months of spend = full buffer score
  STRESSED_DSR: 0.5,        // debt-service ratio at/above which the score floors
  SAVINGS_NORM: 100000,     // savings normalizer for the health score
  W_BUFFER: 0.4, W_DSR: 0.4, W_SAVINGS: 0.2,
};

// Regulatory 5-class collectibility (kolektibilitas Kol-1..Kol-5) derived from
// days-past-due. Demo assumption: OJK-style DPD bands (Bank Muamalat Malaysia /
// BNM classifies differently). Single source of truth — the collections-bot's
// tone stages (30/60/90) are a deliberately separate scale.
const COLLECTIBILITY = {
  KOL2_MAX: 90,  // 1-90    -> Kol-2 Special Mention
  KOL3_MAX: 120, // 91-120  -> Kol-3 Substandard
  KOL4_MAX: 180, // 121-180 -> Kol-4 Doubtful; >180 -> Kol-5 Loss
};

// SQL expression mapping a DPD int expr to the 1-5 collectibility class.
function collectibilitySql(dpdExpr) {
  return `CASE
    WHEN ${dpdExpr} = 0 THEN 1
    WHEN ${dpdExpr} <= ${COLLECTIBILITY.KOL2_MAX} THEN 2
    WHEN ${dpdExpr} <= ${COLLECTIBILITY.KOL3_MAX} THEN 3
    WHEN ${dpdExpr} <= ${COLLECTIBILITY.KOL4_MAX} THEN 4
    ELSE 5
  END`;
}

// SQL expression for the human-readable class label.
function collectibilityLabelSql(dpdExpr) {
  return `CASE
    WHEN ${dpdExpr} = 0 THEN 'Kol-1 Current'
    WHEN ${dpdExpr} <= ${COLLECTIBILITY.KOL2_MAX} THEN 'Kol-2 Special Mention'
    WHEN ${dpdExpr} <= ${COLLECTIBILITY.KOL3_MAX} THEN 'Kol-3 Substandard'
    WHEN ${dpdExpr} <= ${COLLECTIBILITY.KOL4_MAX} THEN 'Kol-4 Doubtful'
    ELSE 'Kol-5 Loss'
  END`;
}

// Render a JS string array as a SQL IN-list literal: ['A','B'] -> "'A','B'".
function inList(arr) {
  return arr.map((v) => `'${v}'`).join(", ");
}

// SQL expression mapping an hour-of-day (0-23) to a daypart bucket. Single source
// of truth shared by both transaction fact models. `hourExpr` is any SQL int expr.
function timeOfDay(hourExpr) {
  return `CASE
    WHEN ${hourExpr} BETWEEN 0 AND 3   THEN 'Midnight'
    WHEN ${hourExpr} BETWEEN 4 AND 6   THEN 'Early morning'
    WHEN ${hourExpr} BETWEEN 7 AND 10  THEN 'Morning'
    WHEN ${hourExpr} BETWEEN 11 AND 13 THEN 'Noon'
    WHEN ${hourExpr} BETWEEN 14 AND 16 THEN 'Afternoon'
    WHEN ${hourExpr} BETWEEN 17 AND 19 THEN 'Evening'
    ELSE 'Night'
  END`;
}

// Build a column definition that carries a BigQuery policy tag *only* when the
// corresponding tag var is populated. This keeps `dataform compile` clean in a
// bare checkout (no live taxonomy) while applying real column-level security
// when Terraform-provided URNs are passed in.
//
// NOTE: BigQuery does NOT propagate policy tags to derived tables, so Gold
// models must call this again on inherited PII columns (full_name, phone_number).
function piiColumn(description, tagKey) {
  const tag = POLICY_TAGS[tagKey];
  const col = { description: description };
  if (tag) {
    col.bigqueryPolicyTags = [tag];
  }
  return col;
}

module.exports = { POLICY_TAGS, IPS, CHURN, PERSONALIZATION, COLLECTIBILITY, piiColumn, churnRiskScoreSql, collectibilitySql, collectibilityLabelSql, timeOfDay, inList };
