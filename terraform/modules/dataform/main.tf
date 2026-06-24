variable "project_id" { type = string }
variable "region" { type = string }
variable "git_remote_url" { type = string }
variable "labels" { type = map(string) }
variable "dataset_ids" { type = list(string) }
variable "dataform_service_account" { type = string } # the gcp-sa-dataform service agent
variable "transform_runner" {
  type    = string
  default = ""
}

# Dedicated execution service account for Dataform workflow invocations. Required
# because the project enforces strict "act as" checks (runs can't use the default
# service agent identity). This SA is the identity that actually runs the BigQuery
# jobs and writes the policy tags.
resource "google_service_account" "runner" {
  project      = var.project_id
  account_id   = "c360-dataform-runner"
  display_name = "Customer 360 Dataform execution SA"
}

resource "google_dataform_repository" "c360" {
  provider        = google-beta
  project         = var.project_id
  region          = var.region
  name            = "c360-medallion"
  labels          = var.labels
  service_account = google_service_account.runner.email

  dynamic "git_remote_settings" {
    for_each = var.git_remote_url != "" ? [1] : []
    content {
      url            = var.git_remote_url
      default_branch = "main"
    }
  }

  # The deployer must be able to act as the runner SA before it can be set here.
  depends_on = [google_service_account_iam_member.deployer_act_as]
}

# Execution SA: run BigQuery jobs + own the medallion datasets. dataOwner (not
# just dataEditor) is required so it can apply column policy tags
# (bigquery.tables.setCategory) and create the assertion-result dataset's views.
resource "google_project_iam_member" "runner_jobuser" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.runner.email}"
}

# Reading the policy-tag taxonomy when applying tags during table creation needs
# datacatalog.taxonomies.get (fine-grained reader only covers query-time use).
resource "google_project_iam_member" "runner_datacatalog_viewer" {
  project = var.project_id
  role    = "roles/datacatalog.viewer"
  member  = "serviceAccount:${google_service_account.runner.email}"
}

resource "google_bigquery_dataset_iam_member" "runner_owner" {
  for_each   = toset(var.dataset_ids)
  project    = var.project_id
  dataset_id = each.value
  role       = "roles/bigquery.dataOwner"
  member     = "serviceAccount:${google_service_account.runner.email}"
}

# The Dataform service agent impersonates the runner SA to launch executions.
resource "google_service_account_iam_member" "agent_token_creator" {
  service_account_id = google_service_account.runner.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${var.dataform_service_account}"
}

# The deployer needs to act as the runner SA (to set it on the repo + invoke).
resource "google_service_account_iam_member" "deployer_act_as" {
  count              = var.transform_runner != "" ? 1 : 0
  service_account_id = google_service_account.runner.name
  role               = "roles/iam.serviceAccountUser"
  member             = var.transform_runner
}

output "repository_name" { value = google_dataform_repository.c360.name }
output "runner_sa" { value = google_service_account.runner.email }
