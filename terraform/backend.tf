# Remote state in GCS. The bucket must exist before `terraform init`:
#   gsutil mb -l asia-southeast2 gs://lv-playground-genai-tfstate
#   gsutil versioning set on   gs://lv-playground-genai-tfstate
terraform {
  backend "gcs" {
    bucket = "lv-playground-genai-tfstate"
    prefix = "c360"
  }
}
