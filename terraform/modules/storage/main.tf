variable "project_id" { type = string }
variable "region" { type = string }
variable "name_prefix" { type = string }
variable "labels" { type = map(string) }

# Landing zone for AS400 daily extracts (gs://<prefix>-as400-core-data-drop).
resource "google_storage_bucket" "landing" {
  name                        = "${var.name_prefix}-as400-core-data-drop"
  project                     = var.project_id
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
  labels                      = var.labels

  lifecycle_rule {
    condition { age = 30 }
    action { type = "Delete" }
  }
}

# Staging bucket for ingestion code / temp load artifacts.
resource "google_storage_bucket" "staging" {
  name                        = "${var.name_prefix}-pipeline-staging"
  project                     = var.project_id
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
  labels                      = var.labels
}

output "landing_bucket_name" { value = google_storage_bucket.landing.name }
output "staging_bucket_name" { value = google_storage_bucket.staging.name }
