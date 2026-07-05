# Deploy config for the lv-playground-genai demo.
#   terraform plan  -var-file=envs/dev.tfvars
#   terraform apply -var-file=envs/dev.tfvars

project_id  = "lv-playground-genai"
region      = "asia-southeast2"
bq_location = "asia-southeast2"
name_prefix = "lv-playground-genai" # globally-unique bucket names

# CLI transform path: the identity that runs `dataform run`. Replace with your
# gcloud login (the one you run `gcloud auth application-default login` as).
transform_runner = "user:fauzal.atmodirono@devoteam.com"

# Create the masked-reader demo SA so the masked side of CLS is demonstrable.
create_masked_demo_sa = true

# Real Cloud Identity groups (left "" — masking still works; cleartext via transform_runner).
group_data_engineers      = ""
group_data_analysts       = ""
group_marketing_users     = ""
group_compliance_auditors = ""

# Managed Dataform: create the repository (code pushed via the Dataform API).
# Orchestration (Cloud Workflows + Scheduler) stays off for now.
create_orchestration = false
create_dataform_repo = true
create_webapp_sa     = true
