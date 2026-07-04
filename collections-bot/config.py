"""Environment + demo-contacts loading for the collections bot."""
import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    twilio_account_sid: str
    twilio_auth_token: str
    sms_from: str
    whatsapp_from: str
    email_from: str
    email_from_name: str
    google_api_key: str
    gemini_model: str
    gcp_project: str
    bq_location: str
    gold_dataset: str
    bot_port: int
    conversation_db_path: str
    public_base_url: str
    verify_twilio_signature: bool
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    vertex_location: str = "global"
    bot_api_key: str = ""
    simulate_channels: str = ""
    store_backend: str = "sqlite"
    firestore_project: str = ""
    firestore_database: str = "(default)"


@dataclass(frozen=True)
class Contact:
    customer_id: str
    name: str
    dpd_stage: str
    whatsapp: str
    sms: str
    email: str


def load_settings(env: dict | None = None) -> Settings:
    e = env if env is not None else os.environ
    def g(key: str, default: str = "") -> str:
        return e.get(key, default)
    return Settings(
        twilio_account_sid=g("TWILIO_ACCOUNT_SID"),
        twilio_auth_token=g("TWILIO_AUTH_TOKEN"),
        sms_from=g("TWILIO_SMS_FROM"),
        whatsapp_from=g("TWILIO_WHATSAPP_FROM"),
        email_from=g("EMAIL_FROM"),
        email_from_name=g("EMAIL_FROM_NAME", "Collections"),
        google_api_key=g("GOOGLE_API_KEY"),
        gemini_model=g("GEMINI_MODEL", "gemini-2.5-flash"),
        gcp_project=g("GCP_PROJECT", "nbs-playground-data-analytics"),
        bq_location=g("BQ_LOCATION", "asia-southeast2"),
        gold_dataset=g("GOLD_DATASET", "demo_gold_analytics"),
        bot_port=int(g("BOT_PORT", "8100")),
        conversation_db_path=g("CONVERSATION_DB_PATH", "./conversations.sqlite"),
        public_base_url=g("PUBLIC_BASE_URL"),
        verify_twilio_signature=g("VERIFY_TWILIO_SIGNATURE", "true").lower() == "true",
        smtp_host=g("SMTP_HOST"),
        smtp_port=int(g("SMTP_PORT", "587")),
        smtp_user=g("SMTP_USER"),
        smtp_password=g("SMTP_PASSWORD"),
        smtp_starttls=g("SMTP_STARTTLS", "true").lower() == "true",
        vertex_location=g("GOOGLE_CLOUD_LOCATION", "global"),
        bot_api_key=g("BOT_API_KEY"),
        simulate_channels=g("SIMULATE_CHANNELS"),
        store_backend=g("STORE_BACKEND", "sqlite").lower(),
        firestore_project=g("FIRESTORE_PROJECT"),
        firestore_database=g("FIRESTORE_DATABASE", "(default)"),
    )


def load_contacts(path: str) -> dict[str, Contact]:
    with open(path) as f:
        raw = json.load(f)
    return {
        cif: Contact(customer_id=cif, name=v["name"], dpd_stage=v["dpd_stage"],
                     whatsapp=v.get("whatsapp", ""), sms=v.get("sms", ""), email=v.get("email", ""))
        for cif, v in raw.items()
    }
