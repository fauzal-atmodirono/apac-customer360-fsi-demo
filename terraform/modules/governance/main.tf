variable "project_id" { type = string }
variable "location" { type = string }
variable "labels" { type = map(string) }
variable "dataform_service_account" { type = string }
variable "group_data_engineers" { type = string }
variable "group_data_analysts" { type = string }
variable "group_marketing_users" { type = string }
variable "group_compliance_auditors" { type = string }
variable "transform_runner" {
  type    = string
  default = ""
}
variable "create_masked_demo_sa" {
  type    = bool
  default = false
}
variable "grant_dataform_sa" {
  type    = bool
  default = false
}
# The Dataform execution SA that writes tables + policy tags (empty = none yet).
variable "policy_tag_writer" {
  type    = string
  default = ""
}

locals {
  # Data Catalog taxonomy region + BigQuery data-policy location use the
  # lower-cased BigQuery location ("US" -> "us"; regional values pass through).
  dc_location = lower(var.location)
}

# --- Taxonomy: Banking_Customer_Data_Classification (BRD section 7.2.1) ------
resource "google_data_catalog_taxonomy" "banking" {
  project                = var.project_id
  region                 = local.dc_location
  display_name           = "Banking_Customer_Data_Classification"
  description            = "Centralized PII + financial data classification for Customer 360."
  activated_policy_types = ["FINE_GRAINED_ACCESS_CONTROL"]
}

# --- Policy tags -------------------------------------------------------------
resource "google_data_catalog_policy_tag" "tags" {
  for_each = {
    PII_Name    = "Customer full name (highly sensitive PII)."
    PII_Phone   = "Customer phone number (highly sensitive PII)."
    PII_Address = "Customer residential address (highly sensitive PII)."
    Card_PAN    = "Credit-card PAN (sensitive financials)."
  }
  taxonomy     = google_data_catalog_taxonomy.banking.id
  display_name = each.key
  description  = each.value
}

# --- Custom masking routines (UDFs) -----------------------------------------
# BigQuery built-ins cover the name (SHA256) and address (nullify) cases, but
# the phone "XXXX-XXXX-1234" and card "XXXXXXXXXXXX4444" formats require custom
# masking routines. These MUST be created with data_governance_type=DATA_MASKING.
resource "google_bigquery_dataset" "security" {
  project       = var.project_id
  dataset_id    = "demo_security_udf"
  friendly_name = "demo_security_udf"
  description   = "Holds custom data-masking routines referenced by BigQuery data policies."
  location      = var.location
  labels        = var.labels
}

resource "google_bigquery_routine" "mask_phone" {
  project              = var.project_id
  dataset_id           = google_bigquery_dataset.security.dataset_id
  routine_id           = "mask_phone"
  routine_type         = "SCALAR_FUNCTION"
  language             = "SQL"
  data_governance_type = "DATA_MASKING"
  # DATA_MASKING routines only allow a restricted function set (RIGHT/REPEAT are
  # rejected); CONCAT + SUBSTR(negative offset) yields the same "XXXX-XXXX-1234".
  definition_body = "CONCAT('XXXX-XXXX-', SUBSTR(v, -4))"
  arguments {
    name      = "v"
    data_type = jsonencode({ typeKind = "STRING" })
  }
  return_type = jsonencode({ typeKind = "STRING" })
}

resource "google_bigquery_routine" "mask_card_pan" {
  project              = var.project_id
  dataset_id           = google_bigquery_dataset.security.dataset_id
  routine_id           = "mask_card_pan"
  routine_type         = "SCALAR_FUNCTION"
  language             = "SQL"
  data_governance_type = "DATA_MASKING"
  # 16-digit PAN -> first 12 masked, last 4 visible ("XXXXXXXXXXXX4444").
  definition_body = "CONCAT('XXXXXXXXXXXX', SUBSTR(v, -4))"
  arguments {
    name      = "v"
    data_type = jsonencode({ typeKind = "STRING" })
  }
  return_type = jsonencode({ typeKind = "STRING" })
}

# --- Data masking policies (bind a masking rule to each policy tag) ----------
resource "google_bigquery_datapolicy_data_policy" "name" {
  project          = var.project_id
  location         = local.dc_location
  data_policy_id   = "mask_pii_name"
  policy_tag       = google_data_catalog_policy_tag.tags["PII_Name"].id
  data_policy_type = "DATA_MASKING_POLICY"
  data_masking_policy { predefined_expression = "SHA256" }
}

resource "google_bigquery_datapolicy_data_policy" "address" {
  project          = var.project_id
  location         = local.dc_location
  data_policy_id   = "mask_pii_address"
  policy_tag       = google_data_catalog_policy_tag.tags["PII_Address"].id
  data_policy_type = "DATA_MASKING_POLICY"
  data_masking_policy { predefined_expression = "ALWAYS_NULL" }
}

resource "google_bigquery_datapolicy_data_policy" "phone" {
  project          = var.project_id
  location         = local.dc_location
  data_policy_id   = "mask_pii_phone"
  policy_tag       = google_data_catalog_policy_tag.tags["PII_Phone"].id
  data_policy_type = "DATA_MASKING_POLICY"
  data_masking_policy { routine = google_bigquery_routine.mask_phone.id }
}

resource "google_bigquery_datapolicy_data_policy" "card" {
  project          = var.project_id
  location         = local.dc_location
  data_policy_id   = "mask_card_pan"
  policy_tag       = google_data_catalog_policy_tag.tags["Card_PAN"].id
  data_policy_type = "DATA_MASKING_POLICY"
  data_masking_policy { routine = google_bigquery_routine.mask_card_pan.id }
}

# --- Masked-reader demo identity --------------------------------------------
# A service account that can query masked PII (but not cleartext), so the masked
# side of column-level security is demonstrable without Cloud Identity groups.
resource "google_service_account" "masked_demo" {
  count        = var.create_masked_demo_sa ? 1 : 0
  project      = var.project_id
  account_id   = "c360-masked-reader"
  display_name = "Customer 360 masked-reader demo identity"
}

output "taxonomy_id" { value = google_data_catalog_taxonomy.banking.id }
output "policy_tag_ids" {
  value = { for k, v in google_data_catalog_policy_tag.tags : k => v.id }
}
output "masked_demo_sa" {
  value = var.create_masked_demo_sa ? google_service_account.masked_demo[0].email : null
}
