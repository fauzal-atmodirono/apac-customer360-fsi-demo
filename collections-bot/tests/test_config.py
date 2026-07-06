import json
from config import load_settings, load_contacts

def test_load_settings_reads_env_values():
    env = {
        "TWILIO_ACCOUNT_SID": "AC1", "TWILIO_AUTH_TOKEN": "tok",
        "TWILIO_SMS_FROM": "+1999", "TWILIO_WHATSAPP_FROM": "whatsapp:+1888",
        "EMAIL_FROM": "a@b.com", "EMAIL_FROM_NAME": "Bank",
        "GOOGLE_API_KEY": "g", "GEMINI_MODEL": "gemini-2.5-flash",
        "GCP_PROJECT": "proj", "BQ_LOCATION": "asia-southeast2", "GOLD_DATASET": "gold",
        "BOT_PORT": "8100", "CONVERSATION_DB_PATH": "./x.sqlite",
        "PUBLIC_BASE_URL": "https://t.ngrok.app", "VERIFY_TWILIO_SIGNATURE": "false",
        "SMTP_HOST": "smtp.x", "SMTP_PORT": "2525", "SMTP_STARTTLS": "false",
        "GOOGLE_CLOUD_LOCATION": "asia-southeast1",
    }
    s = load_settings(env)
    assert s.twilio_account_sid == "AC1"
    assert s.whatsapp_from == "whatsapp:+1888"
    assert s.gemini_model == "gemini-2.5-flash"
    assert s.verify_twilio_signature is False
    assert s.bot_port == 8100
    assert s.smtp_host == "smtp.x"
    assert s.smtp_port == 2525
    assert s.smtp_starttls is False
    assert s.vertex_location == "asia-southeast1"

def test_load_contacts_parses_file(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({
        "001": {"name": "A", "dpd_stage": "SOFT_REMINDER",
                "whatsapp": "whatsapp:+1", "sms": "+1", "email": "a@b.com"}
    }))
    contacts = load_contacts(str(p))
    assert contacts["001"].name == "A"
    assert contacts["001"].dpd_stage == "SOFT_REMINDER"

def test_fake_today_env_flag():
    assert load_settings({}).fake_today == ""
    assert load_settings({"BOT_FAKE_TODAY": "2026-01-01"}).fake_today == "2026-01-01"
