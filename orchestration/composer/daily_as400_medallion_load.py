"""Reference Cloud Composer 3 (Apache Airflow 2.x) DAG — BRD section 6.1.

This is the enterprise-faithful orchestration path. The demo defaults to the
lighter Cloud Workflows definition (../workflows/medallion_load.yaml) to avoid
the Composer environment cost, but this DAG is shipped so the production pattern
is documented and deployable: drop it into the Composer environment's dags/
folder (gs://<composer-bucket>/dags/).

Pipeline: wait for 4 GCS files -> load each to Bronze -> Dataform compile ->
Dataform invoke (Silver + Gold + assertions) -> state sensor. A failed assertion
(e.g. negative savings balance) fails the invocation and blocks Gold writes.

Required Airflow Variables / env config:
  GCP_PROJECT, GCP_REGION (e.g. us-central1), BQ_LOCATION (e.g. US),
  LANDING_BUCKET, DATAFORM_REPOSITORY, and POLICY_TAG_* for column-level security.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import models
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator
from airflow.providers.google.cloud.sensors.gcs import GCSObjectExistenceSensor
from airflow.providers.google.cloud.operators.dataform import (
    DataformCreateCompilationResultOperator,
    DataformCreateWorkflowInvocationOperator,
)

PROJECT = "{{ var.value.get('GCP_PROJECT', 'my-gcp-project') }}"
REGION = "{{ var.value.get('GCP_REGION', 'us-central1') }}"
BQ_LOCATION = "{{ var.value.get('BQ_LOCATION', 'US') }}"
BUCKET = "{{ var.value.get('LANDING_BUCKET', 'c360-as400-core-data-drop') }}"
REPOSITORY = "{{ var.value.get('DATAFORM_REPOSITORY', 'c360-medallion') }}"
BRONZE_DATASET = "demo_bronze_as400"

# file -> Bronze table
SOURCES = {
    "AS400_CUST_MAST.csv": "AS400_CUST_MAST",
    "AS400_SVDP_MAST.csv": "AS400_SVDP_MAST",
    "AS400_CC_TXN.csv": "AS400_CC_TXN",
    "AS400_DC_TXN.csv": "AS400_DC_TXN",
    "AS400_LOAN_MAST.csv": "AS400_LOAN_MAST",
}

# Policy-tag vars injected into the Dataform compilation (column-level security).
COMPILE_VARS = {
    "policy_tag_pii_name": "{{ var.value.get('POLICY_TAG_PII_NAME', '') }}",
    "policy_tag_pii_phone": "{{ var.value.get('POLICY_TAG_PII_PHONE', '') }}",
    "policy_tag_pii_address": "{{ var.value.get('POLICY_TAG_PII_ADDRESS', '') }}",
    "policy_tag_card_pan": "{{ var.value.get('POLICY_TAG_CARD_PAN', '') }}",
}

default_args = {
    "owner": "data-engineering",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "depends_on_past": False,
}

with models.DAG(
    dag_id="daily_as400_medallion_load",
    description="AS400 -> Bronze -> Dataform Silver/Gold Customer 360 load.",
    schedule="0 2 * * *",  # 02:00 UTC daily (PRD NFR-1: mart fresh by 05:00 UTC)
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    max_active_runs=1,
    tags=["customer-360", "medallion", "dataform"],
) as dag:

    compile_result = DataformCreateCompilationResultOperator(
        task_id="dataform_compile",
        project_id=PROJECT,
        region=REGION,
        repository_id=REPOSITORY,
        compilation_result={
            "git_commitish": "main",
            "code_compilation_config": {
                "default_database": PROJECT,
                "default_location": BQ_LOCATION,
                "vars": COMPILE_VARS,
            },
        },
    )

    invoke = DataformCreateWorkflowInvocationOperator(
        task_id="dataform_invoke",
        project_id=PROJECT,
        region=REGION,
        repository_id=REPOSITORY,
        # Block downstream success on assertion failures.
        asynchronous=False,
        workflow_invocation={
            "compilation_result": "{{ ti.xcom_pull('dataform_compile')['name'] }}",
            "invocation_config": {"transitive_dependencies_included": True},
        },
    )

    for csv_name, table in SOURCES.items():
        wait = GCSObjectExistenceSensor(
            task_id=f"wait_{table.lower()}",
            bucket=BUCKET,
            object=csv_name,
            poke_interval=60,
            timeout=60 * 60,
            mode="reschedule",
        )

        load = GCSToBigQueryOperator(
            task_id=f"load_{table.lower()}",
            bucket=BUCKET,
            source_objects=[csv_name],
            destination_project_dataset_table=f"{PROJECT}.{BRONZE_DATASET}.{table}",
            source_format="CSV",
            skip_leading_rows=1,
            autodetect=True,
            write_disposition="WRITE_TRUNCATE",
        )

        # Each file must arrive and load before the Dataform compile runs.
        wait >> load >> compile_result

    compile_result >> invoke
