from dataclasses import replace

import pytest
from config import Settings
from twilio_adapter import TwilioAdapter, SendError

def settings():
    return Settings(
        twilio_account_sid="AC", twilio_auth_token="tok", sms_from="+1999",
        whatsapp_from="whatsapp:+1888", email_from="a@b.com",
        email_from_name="Bank", google_api_key="", gemini_model="m", gcp_project="p",
        bq_location="loc", gold_dataset="g", bot_port=8100, conversation_db_path=":memory:",
        public_base_url="https://t.app", verify_twilio_signature=True,
    )

class FakeMsg:
    def __init__(self): self.sent = []
    def create(self, from_, to, body):
        self.sent.append({"from": from_, "to": to, "body": body})
        class R: sid, status = "SM1", "queued"
        return R()

def test_send_whatsapp_prefixes_and_uses_whatsapp_from():
    msgs = FakeMsg()
    a = TwilioAdapter(settings(), messages_client=msgs)
    sid, status = a.send("whatsapp", "whatsapp:+60123", "Salam")
    assert sid == "SM1"
    assert msgs.sent[0]["from"] == "whatsapp:+1888"
    assert msgs.sent[0]["to"] == "whatsapp:+60123"

def test_send_whatsapp_broadcasts_to_all_numbers():
    msgs = FakeMsg()
    a = TwilioAdapter(settings(), messages_client=msgs)
    sid, status = a.send("whatsapp", "whatsapp:+60A, whatsapp:+60B, whatsapp:+60C", "Salam")
    assert [m["to"] for m in msgs.sent] == ["whatsapp:+60A", "whatsapp:+60B", "whatsapp:+60C"]
    assert (sid, status) == ("SM1", "queued")  # primary (first) recipient's result

def test_broadcast_swallows_secondary_failure():
    class Flaky:
        def __init__(self): self.calls = 0
        def create(self, from_, to, body):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("63016 not joined")
            class R: sid, status = "SM1", "queued"
            return R()
    a = TwilioAdapter(settings(), messages_client=Flaky())
    # primary ok, a broadcast copy fails -> swallowed, still returns the primary result
    assert a.send("whatsapp", "whatsapp:+A, whatsapp:+B", "x") == ("SM1", "queued")

def test_send_sms_uses_sms_from():
    msgs = FakeMsg()
    a = TwilioAdapter(settings(), messages_client=msgs)
    a.send("sms", "+60123", "hi")
    assert msgs.sent[0]["from"] == "+1999"
    assert msgs.sent[0]["to"] == "+60123"

def test_send_failure_raises_senderror():
    class Boom:
        def create(self, **k): raise RuntimeError("twilio 63016")
    a = TwilioAdapter(settings(), messages_client=Boom())
    with pytest.raises(SendError) as e:
        a.send("whatsapp", "whatsapp:+60", "x")
    assert "63016" in str(e.value)

def test_verify_delegates_to_validator():
    class V:
        def validate(self, url, params, sig): return sig == "good"
    a = TwilioAdapter(settings(), validator=V())
    assert a.verify("https://t.app/twilio/inbound", {"Body": "x"}, "good") is True
    assert a.verify("https://t.app/twilio/inbound", {"Body": "x"}, "bad") is False

def test_send_email_uses_smtp_sender():
    sent = []
    a = TwilioAdapter(settings(), smtp_sender=lambda msg: sent.append(msg))
    sid, status = a.send("email", "user@example.com", "Body text", subject="Notis")
    assert (sid, status) == ("email", "sent")
    assert sent[0]["To"] == "user@example.com"
    assert sent[0]["Subject"] == "Notis"
    assert "Body text" in sent[0].get_content()

def test_send_email_html_builds_multipart_alternative():
    sent = []
    a = TwilioAdapter(settings(), smtp_sender=lambda m: sent.append(m))
    a.send("email", "u@x.com", "plain fallback", subject="S", html="<p>rich</p>")
    m = sent[0]
    assert m.is_multipart()
    types = {p.get_content_type() for p in m.iter_parts()}
    assert "text/plain" in types and "text/html" in types

def test_simulated_channel_skips_real_send():
    class Boom:
        def create(self, **k): raise AssertionError("real send must not happen for a simulated channel")
    a = TwilioAdapter(replace(settings(), simulate_channels="sms"), messages_client=Boom())
    assert a.send("sms", "+60123", "hi") == ("simulated", "simulated")
    # non-simulated channels still send for real
    msgs = FakeMsg()
    b = TwilioAdapter(replace(settings(), simulate_channels="sms"), messages_client=msgs)
    b.send("whatsapp", "whatsapp:+60123", "Salam")
    assert msgs.sent[0]["to"] == "whatsapp:+60123"
