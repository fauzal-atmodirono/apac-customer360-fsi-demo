// Bronze-layer source declarations.
// These raw AS400 tables are loaded into the Bronze dataset by the orchestrator
// (Cloud Workflows / Composer) before Dataform runs. Declaring them registers
// them as input nodes in the Dataform dependency graph so Silver models can
// reference them via ref("AS400_...").

const bronze = dataform.projectConfig.vars.bronze_dataset;

["AS400_CUST_MAST", "AS400_SVDP_MAST", "AS400_CC_TXN", "AS400_DC_TXN", "AS400_LOAN_MAST",
 "AS400_PRODUCT_MAST", "AS400_PROD_HOLD", "AS400_ACCT_TXN", "AS400_BAL_HIST",
 "AS400_CAMPAIGN_MAST", "AS400_CAMPAIGN_RESP", "AS400_FIN_REPAY", "AS400_XFER_TXN",
 "AS400_PROFIT_DIST", "AS400_TELLER_TXN", "AS400_COLL_CASE", "AS400_COLL_ACT",
 "AS400_RECOVERY"].forEach((name) => {
  declare({
    schema: bronze,
    name: name,
  });
});
