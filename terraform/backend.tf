# Remote state in GCS. The bucket must exist before `terraform init`:
#   gsutil mb -l asia-southeast2 gs://nbs-playground-data-analytics-tfstate
#   gsutil versioning set on   gs://nbs-playground-data-analytics-tfstate
terraform {
  backend "gcs" {
    bucket = "nbs-playground-data-analytics-tfstate"
    prefix = "c360"
  }
}
