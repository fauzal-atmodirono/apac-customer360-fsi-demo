# Cloud Run runtime identity for the Next.js PWA (webapp/).
# Reads BigQuery for the dashboard, sees cleartext PII (fine-grained reader), and
# impersonates the masked-reader SA for the governance "masked" view.
locals {
  webapp_sa_member = var.create_webapp_sa ? "serviceAccount:${google_service_account.webapp[0].email}" : ""
}

resource "google_service_account" "webapp" {
  count        = var.create_webapp_sa ? 1 : 0
  project      = var.project_id
  account_id   = "c360-webapp"
  display_name = "Customer 360 web app (Cloud Run) runtime"
}

resource "google_project_iam_member" "webapp_jobuser" {
  count   = var.create_webapp_sa ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = local.webapp_sa_member
}

resource "google_bigquery_dataset_iam_member" "webapp_viewer" {
  for_each   = var.create_webapp_sa ? toset([module.bigquery.silver_dataset_id, module.bigquery.gold_dataset_id]) : []
  project    = var.project_id
  dataset_id = each.value
  role       = "roles/bigquery.dataViewer"
  member     = local.webapp_sa_member
}

# Cleartext PII (the "fine-grained reader" governance side + name/phone in lists).
resource "google_data_catalog_policy_tag_iam_member" "webapp_fgr" {
  for_each   = var.create_webapp_sa ? toset(["PII_Name", "PII_Phone", "PII_Address", "Card_PAN"]) : toset([])
  policy_tag = module.governance.policy_tag_ids[each.value]
  role       = "roles/datacatalog.categoryFineGrainedReader"
  member     = local.webapp_sa_member
}

# Impersonate the masked-reader SA for the governance "masked" view.
resource "google_service_account_iam_member" "webapp_impersonate_masked" {
  count              = var.create_webapp_sa && var.create_masked_demo_sa ? 1 : 0
  service_account_id = "projects/${var.project_id}/serviceAccounts/${module.governance.masked_demo_sa}"
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = local.webapp_sa_member
}

output "webapp_sa" {
  value = var.create_webapp_sa ? google_service_account.webapp[0].email : null
}
