from dataclasses import replace
from fastapi.testclient import TestClient
from config import Settings, Contact
from store import Store
from conversation import CaseFacts
from server import build_app

def settings():
    return Settings(
        twilio_account_sid="AC", twilio_auth_token="tok", sms_from="+1999",
        whatsapp_from="whatsapp:+1888", email_from="a@b.com",
        email_from_name="Bank", google_api_key="", gemini_model="m", gcp_project="p",
        bq_location="loc", gold_dataset="g", bot_port=8100, conversation_db_path=":memory:",
        public_base_url="https://t.app", verify_twilio_signature=False,
    )

CONTACTS = {"001": Contact("001", "Encik Ahmad", "INTENSIVE", "whatsapp:+60123", "+60123", "a@b.com")}

class FakeAdapter:
    def __init__(self): self.sent = []
    def send(self, channel, to, body, subject="", html=""):
        self.sent.append((channel, to, body)); return ("SMx", "queued")
    def verify(self, url, params, signature): return True

class FakeLookup:
    def facts_for(self, customer_id, name):
        return CaseFacts(stage="INTENSIVE", dpd=45, outstanding=3200.0, loan_id="LN9", name=name)

TODAY = "2026-07-06"


def client(tmp_path, adapter=None, llm_call=None, today_fn=None):
    store = Store(str(tmp_path / "s.sqlite"))
    adapter = adapter or FakeAdapter()
    app = build_app(settings(), CONTACTS, store, adapter, FakeLookup(),
                    llm_call=llm_call or (lambda s, u: "Salam Encik Ahmad."),
                    today_fn=today_fn or (lambda: TODAY))
    return TestClient(app), store, adapter

def test_contacts_lists_demo_debtors(tmp_path):
    c, _, _ = client(tmp_path)
    r = c.get("/contacts")
    assert r.status_code == 200
    assert r.json()[0]["customer_id"] == "001"

def test_start_unknown_cif_422(tmp_path):
    c, _, _ = client(tmp_path)
    r = c.post("/start", json={"customer_id": "999", "channel": "whatsapp"})
    assert r.status_code == 422

def test_start_sends_and_creates_conversation(tmp_path):
    c, store, adapter = client(tmp_path)
    r = c.post("/start", json={"customer_id": "001", "channel": "whatsapp"})
    assert r.status_code == 200
    cid = r.json()["conversation_id"]
    assert adapter.sent[0][0] == "whatsapp"
    full = store.get_with_messages(cid)
    assert full["messages"][0]["direction"] == "out"
    assert full["stage"] == "INTENSIVE"

def test_inbound_generates_and_sends_reply(tmp_path):
    adapter = FakeAdapter()
    store = Store(str(tmp_path / "s.sqlite"))
    app = build_app(settings(), CONTACTS, store, adapter, FakeLookup(),
                    llm_call=lambda s, u: '{"intent":"HARDSHIP","language":"ms","reply":"Kami tawarkan penstrukturan."}')
    c = TestClient(app)
    # seed a conversation for the sender
    cid = store.create_conversation("001", "whatsapp", 45, "INTENSIVE", "FIRM", "ms", "whatsapp:+60123")
    r = c.post("/twilio/inbound",
               data={"From": "whatsapp:+60123", "Body": "saya susah", "MessageSid": "IN1"})
    assert r.status_code == 200
    conv = store.get_conversation(cid)
    assert conv["outcome"] == "RESTRUCTURE_OFFERED"
    assert any(ch == "whatsapp" and "penstrukturan" in body for ch, to, body in adapter.sent)

def test_inbound_dedupes_on_message_sid(tmp_path):
    adapter = FakeAdapter()
    store = Store(str(tmp_path / "s.sqlite"))
    app = build_app(settings(), CONTACTS, store, adapter, FakeLookup(),
                    llm_call=lambda s, u: '{"intent":"AGREE","language":"ms","reply":"Terima kasih."}')
    c = TestClient(app)
    store.create_conversation("001", "whatsapp", 45, "INTENSIVE", "FIRM", "ms", "whatsapp:+60123")
    body = {"From": "whatsapp:+60123", "Body": "ok", "MessageSid": "DUP"}
    c.post("/twilio/inbound", data=body)
    c.post("/twilio/inbound", data=body)
    # second call is a dedupe no-op: only one inbound + one outbound reply recorded
    sends = [s for s in adapter.sent]
    assert len(sends) == 1

def test_start_unknown_channel_422(tmp_path):
    c, _, _ = client(tmp_path)
    r = c.post("/start", json={"customer_id": "001", "channel": "carrier-pigeon"})
    assert r.status_code == 422

def test_start_send_failure_records_failed(tmp_path):
    class FailingAdapter(FakeAdapter):
        def send(self, channel, to, body, subject=""):
            raise RuntimeError("twilio 63016")
    c, store, _ = client(tmp_path, adapter=FailingAdapter())
    r = c.post("/start", json={"customer_id": "001", "channel": "whatsapp"})
    assert r.status_code == 200
    assert "send_error" in r.json()
    cid = r.json()["conversation_id"]
    full = store.get_with_messages(cid)
    assert full["messages"][0]["status"] == "failed"

def test_protected_routes_require_key_when_set(tmp_path):
    from server import build_app
    store = Store(str(tmp_path / "a.sqlite"))
    s = settings()
    s = replace(s, bot_api_key="secret")
    app = build_app(s, CONTACTS, store, FakeAdapter(), FakeLookup(),
                    llm_call=lambda sy, u: "Salam.")
    c = TestClient(app)
    assert c.get("/contacts").status_code == 401
    assert c.get("/contacts", headers={"X-Bot-Key": "secret"}).status_code == 200
    assert c.get("/health").status_code == 200  # health stays open

def test_start_suppressed_by_active_ptp(tmp_path):
    c, store, adapter = client(tmp_path)
    store.create_ptp("001", None, "2026-07-10", 500.0, "manual")
    r = c.post("/start", json={"customer_id": "001", "channel": "whatsapp"})
    assert r.status_code == 409
    body = r.json()
    assert body["reason"] == "ACTIVE_PTP"
    assert body["promise_date"] == "2026-07-10"
    assert adapter.sent == []  # nothing was sent


def test_start_allowed_after_promise_date_passes(tmp_path):
    today = {"v": TODAY}
    c, store, adapter = client(tmp_path, today_fn=lambda: today["v"])
    pid = store.create_ptp("001", None, "2026-07-10", None, "manual")
    assert c.post("/start", json={"customer_id": "001", "channel": "whatsapp"}).status_code == 409
    today["v"] = "2026-07-11"  # the promise date has passed
    r = c.post("/start", json={"customer_id": "001", "channel": "whatsapp"})
    assert r.status_code == 200
    assert store.get_ptp(pid)["status"] == "BROKEN"  # lazily marked on read


def test_inbound_agree_creates_bot_ptp_with_extracted_date(tmp_path):
    llm = lambda s, u: ('{"intent":"AGREE","language":"ms","reply":"Terima kasih.",'
                        '"ptp_date":"2026-07-10","ptp_amount":500}')
    c, store, _ = client(tmp_path, llm_call=llm)
    cid = store.create_conversation("001", "whatsapp", 45, "INTENSIVE", "FIRM", "ms", "whatsapp:+60123")
    c.post("/twilio/inbound", data={"From": "whatsapp:+60123", "Body": "saya bayar", "MessageSid": "IN1"})
    ptps = store.list_ptps(customer_id="001")
    assert len(ptps) == 1
    assert ptps[0]["promise_date"] == "2026-07-10"
    assert ptps[0]["amount"] == 500.0
    assert ptps[0]["source"] == "bot"
    assert ptps[0]["conversation_id"] == cid


def test_inbound_agree_without_date_defaults_plus_three_days(tmp_path):
    llm = lambda s, u: '{"intent":"AGREE","language":"ms","reply":"Terima kasih."}'
    c, store, _ = client(tmp_path, llm_call=llm)
    store.create_conversation("001", "whatsapp", 45, "INTENSIVE", "FIRM", "ms", "whatsapp:+60123")
    c.post("/twilio/inbound", data={"From": "whatsapp:+60123", "Body": "ok", "MessageSid": "IN1"})
    ptps = store.list_ptps(customer_id="001")
    assert len(ptps) == 1
    assert ptps[0]["promise_date"] == "2026-07-09"  # TODAY + 3


def test_inbound_second_agree_does_not_duplicate_ptp(tmp_path):
    llm = lambda s, u: '{"intent":"AGREE","language":"ms","reply":"Terima kasih."}'
    c, store, _ = client(tmp_path, llm_call=llm)
    store.create_conversation("001", "whatsapp", 45, "INTENSIVE", "FIRM", "ms", "whatsapp:+60123")
    c.post("/twilio/inbound", data={"From": "whatsapp:+60123", "Body": "ok", "MessageSid": "IN1"})
    c.post("/twilio/inbound", data={"From": "whatsapp:+60123", "Body": "ya saya bayar", "MessageSid": "IN2"})
    assert len(store.list_ptps(customer_id="001")) == 1


def test_ptp_crud_endpoints(tmp_path):
    c, store, _ = client(tmp_path)
    # unknown CIF and bad date are rejected
    assert c.post("/ptps", json={"customer_id": "999", "promise_date": "2026-07-10"}).status_code == 422
    assert c.post("/ptps", json={"customer_id": "001", "promise_date": "not-a-date"}).status_code == 422
    # create
    r = c.post("/ptps", json={"customer_id": "001", "promise_date": "2026-07-10", "amount": 500})
    assert r.status_code == 200
    pid = r.json()["ptp_id"]
    assert store.get_ptp(pid)["source"] == "manual"
    # duplicate ACTIVE rejected
    assert c.post("/ptps", json={"customer_id": "001", "promise_date": "2026-07-12"}).status_code == 409
    # list
    rows = c.get("/ptps", params={"customer_id": "001"}).json()
    assert len(rows) == 1
    # transition to KEPT
    assert c.post(f"/ptps/{pid}", json={"status": "KEPT"}).status_code == 200
    assert store.get_ptp(pid)["status"] == "KEPT"
    # settled PTPs are immutable
    assert c.post(f"/ptps/{pid}", json={"status": "CANCELLED"}).status_code == 409
    # unknown id
    assert c.post("/ptps/nope", json={"status": "KEPT"}).status_code == 404


def test_ptp_edit_accepts_past_date_as_demo_lever(tmp_path):
    c, store, _ = client(tmp_path)
    pid = c.post("/ptps", json={"customer_id": "001", "promise_date": "2026-07-10"}).json()["ptp_id"]
    r = c.post(f"/ptps/{pid}", json={"promise_date": "2026-07-01"})
    assert r.status_code == 200
    # next suppression check lazily breaks it, so sends are allowed again
    assert store.active_ptp_for("001", today=TODAY) is None
    assert store.get_ptp(pid)["status"] == "BROKEN"


def test_outreach_summary_merges_active_ptp(tmp_path):
    c, store, _ = client(tmp_path)
    cid = store.create_conversation("001", "whatsapp", 45, "INTENSIVE", "FIRM", "ms", "whatsapp:+60123")
    store.add_message(cid, "out", "whatsapp", "Salam", twilio_sid="SM1")
    store.create_ptp("001", cid, "2026-07-10", 500.0, "bot")
    r = c.get("/outreach-summary")
    assert r.status_code == 200
    row = r.json()["001"]
    assert row["contacted"] is True
    assert row["replied"] is False
    assert row["active_ptp"]["promise_date"] == "2026-07-10"


def test_ptp_routes_require_key_when_set(tmp_path):
    store = Store(str(tmp_path / "k.sqlite"))
    s = replace(settings(), bot_api_key="secret")
    app = build_app(s, CONTACTS, store, FakeAdapter(), FakeLookup(),
                    llm_call=lambda sy, u: "Salam.", today_fn=lambda: TODAY)
    c = TestClient(app)
    assert c.get("/ptps").status_code == 401
    assert c.get("/outreach-summary").status_code == 401
    assert c.post("/ptps", json={"customer_id": "001", "promise_date": "2026-07-10"}).status_code == 401


def test_start_uses_contact_stage_when_bq_misses(tmp_path):
    class DefaultLookup:
        def facts_for(self, customer_id, name):
            return CaseFacts(stage="SOFT_REMINDER", dpd=0, outstanding=0.0, loan_id="", name=name)
    store = Store(str(tmp_path / "b.sqlite"))
    contacts = {"001": Contact("001", "Encik Ahmad", "RECOVERY_LEGAL", "whatsapp:+60123", "+60123", "a@b.com")}
    app = build_app(settings(), contacts, store, FakeAdapter(), DefaultLookup(),
                    llm_call=lambda sy, u: "Notis.")
    c = TestClient(app)
    r = c.post("/start", json={"customer_id": "001", "channel": "whatsapp"})
    cid = r.json()["conversation_id"]
    assert store.get_conversation(cid)["stage"] == "RECOVERY_LEGAL"
