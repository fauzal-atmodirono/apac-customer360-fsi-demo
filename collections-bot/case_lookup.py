"""Look up a debtor's collections case facts from BigQuery (read-only)."""
from conversation import CaseFacts


def build_sql(project: str, dataset: str) -> str:
    return f"""
        SELECT m.stage AS stage,
               CAST(m.outstanding AS FLOAT64) AS outstanding,
               m.loan_id AS loan_id,
               COALESCE(f.current_dpd, 0) AS current_dpd
        FROM `{project}.{dataset}.mart_collection_recovery` m
        LEFT JOIN `{project}.{dataset}.mart_financing_health` f USING (customer_id)
        WHERE m.customer_id = @id
        ORDER BY m.outstanding DESC
        LIMIT 1
    """


class CaseLookup:
    def __init__(self, settings, client=None):
        self._s = settings
        self._client = client

    def _bq(self):
        if self._client is None:
            from google.cloud import bigquery
            self._client = bigquery.Client(project=self._s.gcp_project, location=self._s.bq_location)
        return self._client

    def facts_for(self, customer_id: str, name: str) -> CaseFacts:
        default = CaseFacts(stage="SOFT_REMINDER", dpd=0, outstanding=0.0, loan_id="", name=name)
        try:
            from google.cloud import bigquery
            job_config = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("id", "STRING", customer_id)]
            )
            client = self._bq()
            sql = build_sql(self._s.gcp_project, self._s.gold_dataset)
            rows = list(client.query(sql, job_config=job_config).result())
        except Exception:  # noqa: BLE001 - demo must not hard-fail on BQ issues
            return default
        if not rows:
            return default
        r = rows[0]
        return CaseFacts(
            stage=r.get("stage") or "SOFT_REMINDER",
            dpd=int(r.get("current_dpd") or 0),
            outstanding=float(r.get("outstanding") or 0.0),
            loan_id=r.get("loan_id") or "",
            name=name,
        )
