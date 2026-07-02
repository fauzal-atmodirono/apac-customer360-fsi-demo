#!/usr/bin/env python3
"""Load AS400 CSV extracts from GCS (or local files) into the Bronze dataset.

Portable GCS->Bronze loader used for manual/local runs and as the reference
implementation behind the orchestrator's load step. The Cloud Workflow performs
the equivalent load natively via the BigQuery connector; this script is handy
for ad-hoc loads, local smoke tests, and the TC-1.1 failure case.

Usage:
    python load_bronze.py --project my-proj --dataset demo_bronze_as400 \
        --bucket my-proj-as400-core-data-drop
    # or load from local files instead of GCS:
    python load_bronze.py --project my-proj --dataset demo_bronze_as400 \
        --local-dir ./data_generator/out

Requires: pip install google-cloud-bigquery
"""
from __future__ import annotations

import argparse
import sys

# file -> (Bronze table, ordered column list). Bronze is loaded as raw text:
# every column is STRING, so the legacy representation is preserved faithfully
# (leading-zero CIFs like "0010000001", YYYYMMDD date numbers, masked card PANs).
# Silver does all typed parsing (CAST / PARSE_DATE). An explicit schema also makes
# a malformed file fail the load (TC-1.1) instead of being silently auto-detected.
SOURCES = {
    "AS400_CUST_MAST.csv": ("AS400_CUST_MAST", ["CMCIF", "CMNAME", "CMADR1", "CMDOB", "CMSEG", "CMPHNE", "CMRGN", "CMSINCE", "CMINC"]),
    "AS400_SVDP_MAST.csv": ("AS400_SVDP_MAST", ["ACCNO", "AC_CIF", "ACTYPE", "ACBAL", "ACOPDT", "ACSTAT"]),
    "AS400_CC_TXN.csv": ("AS400_CC_TXN", ["TXNID", "CRDNO", "CC_CIF", "TXNDT", "TXNTM", "TXNAMT", "TXN_CAT", "TXNTYP"]),
    "AS400_DC_TXN.csv": ("AS400_DC_TXN", ["TXNID", "DCRDNO", "DC_CIF", "DC_ACCNO", "TXNDT", "TXNTM", "TXNAMT", "TXN_CAT", "TXNTYP"]),
    "AS400_LOAN_MAST.csv": ("AS400_LOAN_MAST", ["LN_NO", "LN_CIF", "LNTYPE", "LN_AMT", "LN_BAL", "LNMTHP", "LN_DUE"]),
    "AS400_PRODUCT_MAST.csv": ("AS400_PRODUCT_MAST", ["PRDCODE", "PRDNAME", "PRDCAT", "PRDCONTRACT", "PRDTYPE", "PRDRATE", "PRDDESC"]),
    "AS400_PROD_HOLD.csv": ("AS400_PROD_HOLD", ["HOLDID", "PH_CIF", "PRDCODE", "PHSTAT", "PHOPDT", "PHBAL"]),
    "AS400_ACCT_TXN.csv": ("AS400_ACCT_TXN", ["TXNID", "AT_CIF", "ACCNO", "AT_DATE", "AT_AMT", "AT_TYPE", "AT_CAT"]),
    "AS400_BAL_HIST.csv": ("AS400_BAL_HIST", ["BH_ACCNO", "BH_CIF", "BH_MONTH", "BH_BAL"]),
    "AS400_CAMPAIGN_MAST.csv": ("AS400_CAMPAIGN_MAST", ["CAMPID", "CAMPNAME", "PRDCODE", "CHANNEL", "CMP_START", "CMP_END"]),
    "AS400_CAMPAIGN_RESP.csv": ("AS400_CAMPAIGN_RESP", ["RESPID", "CR_CIF", "CAMPID", "SENT_DT", "STATUS", "RESP_DT"]),
    "AS400_FIN_REPAY.csv": ("AS400_FIN_REPAY", ["REPAYID", "FR_CIF", "LN_NO", "DUE_DT", "DUE_AMT", "PAID_DT", "PAID_AMT", "STATUS", "DPD"]),
    "AS400_XFER_TXN.csv": ("AS400_XFER_TXN", ["XFERID", "XF_CIF", "ACCNO", "XFER_DT", "XFER_AMT", "XFER_TYPE", "BENEF_BANK", "BENEF_COUNTRY", "FEE", "DIRECTION"]),
    "AS400_PROFIT_DIST.csv": ("AS400_PROFIT_DIST", ["DISTID", "PD_CIF", "ACCNO", "PRDCODE", "DIST_DT", "PROFIT_AMT", "RATE"]),
    "AS400_TELLER_TXN.csv": ("AS400_TELLER_TXN", ["TELLERID", "TL_CIF", "ACCNO", "TXN_DT", "TXN_AMT", "TXN_TYPE", "CHANNEL", "BRANCH_REGION"]),
    "AS400_COLL_CASE.csv": ("AS400_COLL_CASE", ["CASEID", "CC_CIF", "LN_NO", "OPEN_DT", "STAGE", "COLLECTOR", "OUTSTANDING", "CASE_STAT"]),
    "AS400_COLL_ACT.csv": ("AS400_COLL_ACT", ["ACTID", "CASEID", "ACT_DT", "CHANNEL", "OUTCOME", "PTP_AMT", "PTP_DT", "PTP_KEPT"]),
    "AS400_RECOVERY.csv": ("AS400_RECOVERY", ["RECID", "CASEID", "RC_CIF", "REC_DT", "REC_AMT", "REC_TYPE"]),
}


def main() -> int:
    p = argparse.ArgumentParser(description="Load AS400 CSV extracts into BigQuery Bronze.")
    p.add_argument("--project", required=True)
    p.add_argument("--dataset", default="demo_bronze_as400")
    p.add_argument("--bucket", help="GCS bucket holding the CSVs (omit if using --local-dir).")
    p.add_argument("--local-dir", help="Local directory holding the CSVs (alternative to --bucket).")
    p.add_argument("--location", default="US", help="BigQuery dataset location.")
    args = p.parse_args()

    if not args.bucket and not args.local_dir:
        p.error("provide either --bucket or --local-dir")

    from google.cloud import bigquery

    client = bigquery.Client(project=args.project)

    def job_config_for(columns: list[str]) -> "bigquery.LoadJobConfig":
        return bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            autodetect=False,
            schema=[bigquery.SchemaField(c, "STRING") for c in columns],
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )

    failures = 0
    for csv_name, (table, columns) in SOURCES.items():
        table_ref = f"{args.project}.{args.dataset}.{table}"
        job_config = job_config_for(columns)
        try:
            if args.bucket:
                uri = f"gs://{args.bucket}/{csv_name}"
                job = client.load_table_from_uri(uri, table_ref, job_config=job_config,
                                                 location=args.location)
            else:
                path = f"{args.local_dir.rstrip('/')}/{csv_name}"
                with open(path, "rb") as fh:
                    job = client.load_table_from_file(fh, table_ref, job_config=job_config,
                                                      location=args.location)
            job.result()  # wait; raises on schema mismatch (drives TC-1.1)
            dest = client.get_table(table_ref)
            print(f"OK  {table:<18} {dest.num_rows:>7} rows")
        except Exception as exc:  # noqa: BLE001 - surface load failures clearly
            failures += 1
            print(f"FAIL {table:<18} {exc}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
