from config import Settings
from case_lookup import CaseLookup, build_sql

def settings():
    return Settings(
        twilio_account_sid="", twilio_auth_token="", sms_from="", whatsapp_from="",
        email_from="", email_from_name="", google_api_key="",
        gemini_model="m", gcp_project="proj", bq_location="loc", gold_dataset="gold",
        bot_port=8100, conversation_db_path=":memory:", public_base_url="", verify_twilio_signature=True,
    )

def test_build_sql_targets_both_marts():
    sql = build_sql("proj", "gold")
    assert "proj.gold.mart_collection_recovery" in sql
    assert "mart_financing_health" in sql

class FakeRow(dict):
    def get(self, k, default=None): return dict.get(self, k, default)

class FakeClient:
    def __init__(self, rows): self._rows = rows
    def query(self, sql, job_config=None):
        rows = self._rows
        class Job:
            def result(self_inner): return iter(rows)
        return Job()

def test_facts_for_maps_row():
    rows = [FakeRow(stage="INTENSIVE", outstanding=3200.0, loan_id="LN9", current_dpd=45)]
    cl = CaseLookup(settings(), client=FakeClient(rows))
    facts = cl.facts_for("001", "Encik Ahmad")
    assert facts.stage == "INTENSIVE"
    assert facts.dpd == 45
    assert facts.outstanding == 3200.0
    assert facts.name == "Encik Ahmad"

def test_facts_for_defaults_when_no_rows():
    cl = CaseLookup(settings(), client=FakeClient([]))
    facts = cl.facts_for("999", "Nobody")
    assert facts.stage == "SOFT_REMINDER"
    assert facts.dpd == 0
    assert facts.name == "Nobody"
