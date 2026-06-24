// Bronze-layer source declarations.
// These raw AS400 tables are loaded into the Bronze dataset by the orchestrator
// (Cloud Workflows / Composer) before Dataform runs. Declaring them registers
// them as input nodes in the Dataform dependency graph so Silver models can
// reference them via ref("AS400_...").

const bronze = dataform.projectConfig.vars.bronze_dataset;

["AS400_CUST_MAST", "AS400_SVDP_MAST", "AS400_CC_TXN", "AS400_DC_TXN", "AS400_LOAN_MAST"].forEach((name) => {
  declare({
    schema: bronze,
    name: name,
  });
});
