variable "project_id" { type = string }
variable "location" { type = string }
variable "labels" { type = map(string) }

locals {
  datasets = {
    bronze     = { id = "demo_bronze_as400", desc = "Bronze: raw AS400 extracts loaded by the orchestrator." }
    silver     = { id = "demo_silver_banking", desc = "Silver: conformed dimensional models (Dataform)." }
    gold       = { id = "demo_gold_analytics", desc = "Gold: Customer 360 analytical marts (Dataform)." }
    assertions = { id = "dataform_assertions", desc = "Dataform assertion (data-quality) result views." }
  }
}

resource "google_bigquery_dataset" "medallion" {
  for_each      = local.datasets
  project       = var.project_id
  dataset_id    = each.value.id
  friendly_name = each.value.id
  description   = each.value.desc
  location      = var.location
  labels        = var.labels
}

output "bronze_dataset_id" { value = google_bigquery_dataset.medallion["bronze"].dataset_id }
output "silver_dataset_id" { value = google_bigquery_dataset.medallion["silver"].dataset_id }
output "gold_dataset_id" { value = google_bigquery_dataset.medallion["gold"].dataset_id }
output "assertions_dataset_id" { value = google_bigquery_dataset.medallion["assertions"].dataset_id }
