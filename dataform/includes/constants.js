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

module.exports = { POLICY_TAGS, IPS, CHURN, piiColumn, churnRiskScoreSql };
