output "landing_bucket" {
  description = "GCS bucket where AS400 extracts are dropped."
  value       = module.storage.landing_bucket_name
}

output "bronze_dataset" {
  value = module.bigquery.bronze_dataset_id
}

output "silver_dataset" {
  value = module.bigquery.silver_dataset_id
}

output "gold_dataset" {
  value = module.bigquery.gold_dataset_id
}

# Feed these straight into Dataform compilation vars:
#   dataform compile --vars=policy_tag_pii_name=...,policy_tag_pii_phone=...,...
output "policy_tag_vars" {
  description = "Dataform --vars map for column-level security."
  value = {
    policy_tag_pii_name    = module.governance.policy_tag_ids["PII_Name"]
    policy_tag_pii_phone   = module.governance.policy_tag_ids["PII_Phone"]
    policy_tag_pii_address = module.governance.policy_tag_ids["PII_Address"]
    policy_tag_card_pan    = module.governance.policy_tag_ids["Card_PAN"]
  }
}

output "taxonomy_id" {
  value = module.governance.taxonomy_id
}

output "dataform_service_account" {
  value = local.dataform_sa
}

output "masked_demo_sa" {
  description = "Impersonate this SA to see the masked side of column-level security (bq query --impersonate_service_account=...)."
  value       = module.governance.masked_demo_sa
}

output "workflow_name" {
  value       = var.create_orchestration ? module.orchestration[0].workflow_name : null
  description = "Cloud Workflow that runs the daily medallion load."
}
