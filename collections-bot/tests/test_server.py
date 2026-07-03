from fastapi.testclient import TestClient
from config import Settings, Contact
from store import Store
from conversation import CaseFacts
from server import build_app

def settings():
    return Settings(
        twilio_account_sid="AC", twilio_auth_token="tok", sms_from="+1999",
        whatsapp_from="whatsapp:+1888", sendgrid_api_key="SG", email_from="a@b.com",
        email_from_name="Bank", google_api_key="", gemini_model="m", gcp_project="p",
        bq_location="loc", gold_dataset="g", bot_port=8100, conversation_db_path=":memory:",
        public_base_url="https://t.app", verify_twilio_signature=False,
    )

CONTACTS = {"001": Contact("001", "Encik Ahmad", "INTENSIVE", "whatsapp:+60123", "+60123", "a@b.com")}

class FakeAdapter:
    def __init__(self): self.sent = []
    def send(self, channel, to, body, subject=""):
        self.sent.append((channel, to, body)); return ("SMx", "queued")
    def verify(self, url, params, signature): return True

class FakeLookup:
    def facts_for(self, customer_id, name):
        return CaseFacts(stage="INTENSIVE", dpd=45, outstanding=3200.0, loan_id="LN9", name=name)

def client(tmp_path, adapter=None):
    store = Store(str(tmp_path / "s.sqlite"))
    adapter = adapter or FakeAdapter()
    app = build_app(settings(), CONTACTS, store, adapter, FakeLookup(),
                    llm_call=lambda s, u: "Salam Encik Ahmad.")
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
