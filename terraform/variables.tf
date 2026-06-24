variable "project_id" {
  type        = string
  description = "Target GCP project ID."
}

variable "region" {
  type        = string
  description = "Default region for buckets, Workflows, Scheduler."
  default     = "us-central1"
}

variable "bq_location" {
  type        = string
  description = "BigQuery + Data Catalog taxonomy location (e.g. US, EU, us-central1). Policy tags and the tables they protect must share a location."
  default     = "US"
}

variable "name_prefix" {
  type        = string
  description = "Prefix for globally-unique resource names (e.g. GCS buckets)."
  default     = "c360"
}

variable "labels" {
  type        = map(string)
  description = "Labels applied to supported resources."
  default = {
    demo = "customer-360"
  }
}

# --- Identity groups (PRD section 5.3). Replace with real Cloud Identity groups
# before apply. Leave empty to skip a binding (useful for dry-run / no-IdP demos).
variable "group_data_engineers" {
  type        = string
  description = "Group email for data engineers (masked default access)."
  default     = ""
}

variable "group_data_analysts" {
  type        = string
  description = "Group email for data analysts (masked default access)."
  default     = ""
}

variable "group_marketing_users" {
  type        = string
  description = "Group email for marketing users (fine-grained reader on name + phone)."
  default     = ""
}

variable "group_compliance_auditors" {
  type        = string
  description = "Group email for compliance auditors (fine-grained reader on all tags)."
  default     = ""
}

# --- Feature toggles -------------------------------------------------------
variable "enable_apis" {
  type        = bool
  description = "Whether Terraform should enable the required GCP service APIs."
  default     = true
}

variable "create_orchestration" {
  type        = bool
  description = "Create the Cloud Workflows + Cloud Scheduler orchestration."
  default     = true
}

variable "create_dataform_repo" {
  type        = bool
  description = "Create a Dataform repository resource."
  default     = true
}

variable "dataform_git_remote_url" {
  type        = string
  description = "Optional HTTPS git remote to attach to the Dataform repository. Empty = unconnected repo."
  default     = ""
}

variable "transform_runner" {
  type        = string
  description = "IAM principal that runs `dataform run` from the CLI (e.g. \"user:me@x.com\" or \"serviceAccount:sa@proj.iam.gserviceaccount.com\"). Gets BigQuery edit/job roles + fine-grained reader on all policy tags so it can build tables and write/preserve column-level security. Empty = skip."
  default     = ""
}

variable "create_masked_demo_sa" {
  type        = bool
  description = "Create a c360-masked-reader service account with masked-reader access on all data policies, to demonstrate the masked side of column-level security without Cloud Identity groups."
  default     = true
}

variable "create_webapp_sa" {
  type        = bool
  description = "Create the c360-webapp Cloud Run runtime service account (BigQuery reader + fine-grained reader + impersonator of the masked-reader SA)."
  default     = false
}
