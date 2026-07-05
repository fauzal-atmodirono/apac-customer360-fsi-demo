data "google_project" "this" {
  project_id = var.project_id
}

locals {
  required_apis = [
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "bigquerydatapolicy.googleapis.com",
    "datacatalog.googleapis.com",
    "dataform.googleapis.com",
    "workflows.googleapis.com",
    "workflowexecutions.googleapis.com",
    "cloudscheduler.googleapis.com",
    # Cloud Run app stack (webapp + ADK "Ask the data" agent).
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "aiplatform.googleapis.com",
    "secretmanager.googleapis.com",
  ]

  # Dataform service agent — needs fine-grained reader to write/preserve policy
  # tags on its output tables, plus dataEditor on the datasets.
  dataform_sa = "service-${data.google_project.this.number}@gcp-sa-dataform.iam.gserviceaccount.com"
}

resource "google_project_service" "apis" {
  for_each           = var.enable_apis ? toset(local.required_apis) : []
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

module "storage" {
  source      = "./modules/storage"
  project_id  = var.project_id
  region      = var.region
  name_prefix = var.name_prefix
  labels      = var.labels
  depends_on  = [google_project_service.apis]
}

module "bigquery" {
  source     = "./modules/bigquery"
  project_id = var.project_id
  location   = var.bq_location
  labels     = var.labels
  depends_on = [google_project_service.apis]
}

module "governance" {
  source     = "./modules/governance"
  project_id = var.project_id
  location   = var.bq_location
  labels     = var.labels

  group_data_engineers      = var.group_data_engineers
  group_data_analysts       = var.group_data_analysts
  group_marketing_users     = var.group_marketing_users
  group_compliance_auditors = var.group_compliance_auditors

  dataform_service_account = local.dataform_sa
  transform_runner         = var.transform_runner
  create_masked_demo_sa    = var.create_masked_demo_sa
  grant_dataform_sa        = var.create_dataform_repo
  # Grant the Dataform execution SA fine-grained reader on the tags (once the repo exists).
  policy_tag_writer = var.create_dataform_repo ? module.dataform[0].runner_sa : ""
  depends_on        = [google_project_service.apis]
}

# --- Transform runner (the `dataform run` CLI identity) BigQuery grants -------
# Lets the runner build Silver/Gold tables. Fine-grained reader on the policy
# tags is granted inside the governance module.
resource "google_project_iam_member" "runner_jobuser" {
  count   = var.transform_runner != "" ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = var.transform_runner
}

resource "google_bigquery_dataset_iam_member" "runner_editor" {
  for_each = var.transform_runner != "" ? toset([
    module.bigquery.bronze_dataset_id,
    module.bigquery.silver_dataset_id,
    module.bigquery.gold_dataset_id,
  ]) : []
  project    = var.project_id
  dataset_id = each.value
  role       = "roles/bigquery.dataEditor"
  member     = var.transform_runner
}

# --- Masked-reader demo SA: needs to run queries + read the Gold/Silver tables
# (the masking policies govern the PII columns once it can read them). And the
# deployer needs token-creator on it to impersonate for the masking demo.
resource "google_project_iam_member" "masked_demo_jobuser" {
  count   = var.create_masked_demo_sa ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${module.governance.masked_demo_sa}"
}

resource "google_bigquery_dataset_iam_member" "masked_demo_viewer" {
  for_each = var.create_masked_demo_sa ? toset([
    module.bigquery.silver_dataset_id,
    module.bigquery.gold_dataset_id,
  ]) : []
  project    = var.project_id
  dataset_id = each.value
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${module.governance.masked_demo_sa}"
}

resource "google_service_account_iam_member" "runner_impersonate_masked" {
  count              = (var.create_masked_demo_sa && var.transform_runner != "") ? 1 : 0
  service_account_id = "projects/${var.project_id}/serviceAccounts/${module.governance.masked_demo_sa}"
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = var.transform_runner
}

module "dataform" {
  source         = "./modules/dataform"
  count          = var.create_dataform_repo ? 1 : 0
  project_id     = var.project_id
  region         = var.region
  git_remote_url = var.dataform_git_remote_url
  labels         = var.labels

  # Grant the Dataform execution SA owner rights on the medallion + assertions datasets.
  dataset_ids = [
    module.bigquery.bronze_dataset_id,
    module.bigquery.silver_dataset_id,
    module.bigquery.gold_dataset_id,
    module.bigquery.assertions_dataset_id,
  ]
  dataform_service_account = local.dataform_sa
  transform_runner         = var.transform_runner
  depends_on               = [google_project_service.apis]
}

module "orchestration" {
  source     = "./modules/orchestration"
  count      = var.create_orchestration ? 1 : 0
  project_id = var.project_id
  region     = var.region
  labels     = var.labels

  landing_bucket = module.storage.landing_bucket_name
  bronze_dataset = module.bigquery.bronze_dataset_id
  depends_on     = [google_project_service.apis]
}
