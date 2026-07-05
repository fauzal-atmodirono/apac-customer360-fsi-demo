# Customer 360 demo — one-command targets.
# Override defaults inline, e.g.:  make load PROJECT=my-proj BUCKET=my-bucket

PROJECT     ?= my-gcp-project
REGION      ?= us-central1
BQ_LOCATION ?= US
BUCKET      ?= $(PROJECT)-as400-core-data-drop
OUT_DIR     ?= data_generator/out
TF_DIR      ?= terraform
TFVARS      ?= envs/dev.tfvars
PY          ?= python3

.PHONY: help venv gen-data tf-init tf-plan tf-apply tf-destroy upload load df-compile dataform-deploy df-run seed-analytics verify clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

venv: ## Create venv + install generator deps
	$(PY) -m venv .venv && ./.venv/bin/pip install -q -r data_generator/requirements.txt google-cloud-bigquery

gen-data: ## Generate mock AS400 CSV extracts (+ corrupt fixtures)
	$(PY) data_generator/generate_mock_as400.py --out-dir $(OUT_DIR) --corrupt-dir $(OUT_DIR)/corrupt

tf-init: ## terraform init
	cd $(TF_DIR) && terraform init

tf-plan: ## terraform plan (dry-run-first)
	cd $(TF_DIR) && terraform plan -var-file=$(TFVARS)

tf-apply: ## terraform apply
	cd $(TF_DIR) && terraform apply -var-file=$(TFVARS)

tf-destroy: ## tear everything down
	cd $(TF_DIR) && terraform destroy -var-file=$(TFVARS)

upload: ## Upload generated CSVs to the landing bucket
	gsutil -m cp $(OUT_DIR)/*.csv gs://$(BUCKET)/

load: ## Load GCS CSVs into Bronze (alternative to the orchestrator)
	$(PY) ingestion/load_bronze.py --project $(PROJECT) --bucket $(BUCKET) --location $(BQ_LOCATION)

df-compile: ## Compile the Dataform project locally (no live resources needed)
	cd dataform && npx -y @dataform/cli@latest compile

dataform-deploy: ## Push the SQLX to the managed Dataform repo and run it there (as the runner SA)
	$(PY) ingestion/push_dataform_repo.py --project $(PROJECT) --location $(REGION) \
	  --repo c360-medallion --dataform-dir dataform \
	  --vars-json "$$(cd $(TF_DIR) && terraform output -json policy_tag_vars)"

df-run: ## Run Silver+Gold+assertions via Cloud Workflows (reads policy-tag vars from TF output)
	gcloud workflows run daily_as400_medallion_load --location=$(REGION) \
	  --data="$$(cd $(TF_DIR) && terraform output -json policy_tag_vars | \
	    python3 -c 'import sys,json; v=json.load(sys.stdin); print(json.dumps({"vars":v,"location":"$(REGION)","bq_location":"$(BQ_LOCATION)"}))')"

seed-analytics: ## Seed the Executive KPI baseline table (analytics/kpi_snapshots.sql) the webapp reads
	bq query --project_id=$(PROJECT) --location=$(BQ_LOCATION) --nouse_legacy_sql < analytics/kpi_snapshots.sql

verify: ## Print the demo verification queries to run in BigQuery
	@echo "Run analytics/customer_360_queries.sql in BigQuery as different identities (see README)."

clean: ## Remove generated data + local venv
	rm -rf $(OUT_DIR) .venv
