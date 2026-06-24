variable "project_id" { type = string }
variable "region" { type = string }
variable "labels" { type = map(string) }
variable "landing_bucket" { type = string }
variable "bronze_dataset" { type = string }

# Dedicated runtime identity for the Workflow + Scheduler.
resource "google_service_account" "workflow" {
  project      = var.project_id
  account_id   = "c360-orchestrator"
  display_name = "Customer 360 medallion orchestrator"
}

locals {
  # Minimal roles to: read landing files, run BigQuery loads/jobs, drive Dataform.
  workflow_roles = [
    "roles/dataform.editor",
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/storage.objectViewer",
    "roles/workflows.invoker",
    "roles/logging.logWriter",
  ]
}

resource "google_project_iam_member" "workflow" {
  for_each = toset(local.workflow_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.workflow.email}"
}

resource "google_workflows_workflow" "medallion" {
  project         = var.project_id
  region          = var.region
  name            = "daily_as400_medallion_load"
  description     = "GCS file check -> Bronze load -> Dataform compile + invoke -> status."
  service_account = google_service_account.workflow.id
  labels          = var.labels
  source_contents = file("${path.module}/../../../orchestration/workflows/medallion_load.yaml")
}

# Daily trigger at 02:00 UTC (BRD section 6.2 / PRD NFR-1).
resource "google_cloud_scheduler_job" "daily" {
  project   = var.project_id
  region    = var.region
  name      = "daily-as400-medallion-load"
  schedule  = "0 2 * * *"
  time_zone = "Etc/UTC"

  http_target {
    http_method = "POST"
    uri         = "https://workflowexecutions.googleapis.com/v1/projects/${var.project_id}/locations/${var.region}/workflows/${google_workflows_workflow.medallion.name}/executions"
    oauth_token {
      service_account_email = google_service_account.workflow.email
    }
  }
}

output "workflow_name" { value = google_workflows_workflow.medallion.name }
output "service_account" { value = google_service_account.workflow.email }
