# Access model (PRD section 5.3):
#   - fineGrainedReader on a policy tag  -> sees CLEARTEXT for tagged columns
#   - maskedReader on a data policy      -> sees the MASKED value (still queryable)
#   - neither                            -> query on the column is denied
#
# Bindings to groups are skipped when the group email is "" (dry-run friendly).

locals {
  fgr_role    = "roles/datacatalog.categoryFineGrainedReader"
  masked_role = "roles/bigquerydatapolicy.maskedReader"

  all_tags = keys(google_data_catalog_policy_tag.tags)

  data_policies = {
    PII_Name    = google_bigquery_datapolicy_data_policy.name.data_policy_id
    PII_Phone   = google_bigquery_datapolicy_data_policy.phone.data_policy_id
    PII_Address = google_bigquery_datapolicy_data_policy.address.data_policy_id
    Card_PAN    = google_bigquery_datapolicy_data_policy.card.data_policy_id
  }

  # marketing sees name + phone in clear; compliance sees everything in clear.
  marketing_clear_tags  = var.group_marketing_users != "" ? ["PII_Name", "PII_Phone"] : []
  compliance_clear_tags = var.group_compliance_auditors != "" ? local.all_tags : []

  # masked-default readers, so their queries succeed but return masked PII.
  analyst_masked  = var.group_data_analysts != "" ? local.all_tags : []
  engineer_masked = var.group_data_engineers != "" ? local.all_tags : []
  # marketing still needs masked access to the tags it does NOT read in clear.
  marketing_masked = var.group_marketing_users != "" ? ["PII_Address", "Card_PAN"] : []
}

# --- Dataform execution SA: fine-grained reader on every tag so it can
#     write + preserve policy tags on its output tables (BRD section 7.2.3). ----
resource "google_data_catalog_policy_tag_iam_member" "dataform_fgr" {
  # Granted to the Dataform execution SA once the repository is provisioned.
  for_each   = var.policy_tag_writer != "" ? toset(local.all_tags) : []
  policy_tag = google_data_catalog_policy_tag.tags[each.value].id
  role       = local.fgr_role
  member     = "serviceAccount:${var.policy_tag_writer}"
}

# --- Transform runner (CLI): fine-grained reader on every tag so `dataform run`
#     can write/preserve tags, and so the deployer sees cleartext PII. ----------
resource "google_data_catalog_policy_tag_iam_member" "runner_fgr" {
  for_each   = var.transform_runner != "" ? toset(local.all_tags) : []
  policy_tag = google_data_catalog_policy_tag.tags[each.value].id
  role       = local.fgr_role
  member     = var.transform_runner
}

# --- Masked-reader demo SA: masked access on every data policy. --------------
resource "google_bigquery_datapolicy_data_policy_iam_member" "masked_demo" {
  for_each       = var.create_masked_demo_sa ? local.data_policies : {}
  project        = var.project_id
  location       = local.dc_location
  data_policy_id = each.value
  role           = local.masked_role
  member         = "serviceAccount:${google_service_account.masked_demo[0].email}"
}

# --- Fine-grained (cleartext) readers ---------------------------------------
resource "google_data_catalog_policy_tag_iam_member" "marketing_clear" {
  for_each   = toset(local.marketing_clear_tags)
  policy_tag = google_data_catalog_policy_tag.tags[each.value].id
  role       = local.fgr_role
  member     = "group:${var.group_marketing_users}"
}

resource "google_data_catalog_policy_tag_iam_member" "compliance_clear" {
  for_each   = toset(local.compliance_clear_tags)
  policy_tag = google_data_catalog_policy_tag.tags[each.value].id
  role       = local.fgr_role
  member     = "group:${var.group_compliance_auditors}"
}

# --- Masked readers (default access) ----------------------------------------
resource "google_bigquery_datapolicy_data_policy_iam_member" "analyst_masked" {
  for_each       = toset(local.analyst_masked)
  project        = var.project_id
  location       = local.dc_location
  data_policy_id = local.data_policies[each.value]
  role           = local.masked_role
  member         = "group:${var.group_data_analysts}"
}

resource "google_bigquery_datapolicy_data_policy_iam_member" "engineer_masked" {
  for_each       = toset(local.engineer_masked)
  project        = var.project_id
  location       = local.dc_location
  data_policy_id = local.data_policies[each.value]
  role           = local.masked_role
  member         = "group:${var.group_data_engineers}"
}

resource "google_bigquery_datapolicy_data_policy_iam_member" "marketing_masked" {
  for_each       = toset(local.marketing_masked)
  project        = var.project_id
  location       = local.dc_location
  data_policy_id = local.data_policies[each.value]
  role           = local.masked_role
  member         = "group:${var.group_marketing_users}"
}
