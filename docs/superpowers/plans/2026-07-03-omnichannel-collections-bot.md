# Omnichannel AI Collections Bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a bot-initiated, multi-channel (WhatsApp two-way, SMS + Email send-only) AI collections bot that opens outreach with a DPD-driven tone and adapts to hostile/hardship replies, triggered from the webapp with a live transcript.

**Architecture:** A new standalone Python FastAPI service `collections-bot/` (sibling to `agent/`) owns Twilio I/O, a bilingual Gemini conversation engine with a DPD tone state machine, and a SQLite conversation store. The Next.js webapp gets a new "Outreach" page + a thin proxy route to the bot (mirroring the existing `app/api/chat` → `AGENT_URL` pattern). The bot reads case facts from BigQuery but never writes back.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, `twilio`, `sendgrid`, `google-genai` (Gemini), `google-cloud-bigquery`, SQLite (stdlib), pytest. Webapp: Next.js 14 App Router, SWR.

Design spec: `docs/superpowers/specs/2026-07-03-omnichannel-collections-bot-design.md`.

## Global Constraints

- **Python 3.12** (matches `agent/Dockerfile`).
- **Demo-grade:** no BigQuery writes, no auth beyond Twilio signature verification, no scale concerns.
- **WhatsApp `to`/`from` MUST be `whatsapp:`-prefixed** (e.g. `whatsapp:+60123456789`). SMS uses bare E.164.
- **Default outbound language is Bahasa Malaysia (`ms`)**; if a debtor replies in English, continue in English. Track `language` on the conversation.
- **Tone-floor rule:** tone is fixed by DPD stage and never de-escalates below that floor. Intent may move it *sterner* (HOSTILE) but never softer. Stage→floor: `SOFT_REMINDER`→`FRIENDLY`, `INTENSIVE`→`FIRM`, `FIELD_VISIT`→`ASSERTIVE`, `RECOVERY_LEGAL`→`LEGAL`.
- **Stage from DPD:** `≤30`→`SOFT_REMINDER`, `31–60`→`INTENSIVE`, `61–90`→`FIELD_VISIT`, `>90`→`RECOVERY_LEGAL`.
- **Intents:** `AGREE`, `HOSTILE`, `HARDSHIP`, `OTHER`. **Outcomes:** `OPENED`, `PTP_OBTAINED`, `RESTRUCTURE_OFFERED`, `HOSTILE_ESCALATED`, `NO_RESPONSE`.
- **Env var names are exact** (see spec §5): `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_SMS_FROM`, `TWILIO_WHATSAPP_FROM`, `SENDGRID_API_KEY`, `EMAIL_FROM`, `EMAIL_FROM_NAME`, `GOOGLE_API_KEY`, `GEMINI_MODEL`, `GCP_PROJECT`, `BQ_LOCATION`, `GOLD_DATASET`, `BOT_PORT`, `CONVERSATION_DB_PATH`, `PUBLIC_BASE_URL`, `VERIFY_TWILIO_SIGNATURE`.
- **Restructuring content is Shariah-consistent:** waive/reduce charges (no penalty interest), payment-plan adjustment, installment extension ("Rekonstruksi").
- **All new Python files live under `collections-bot/`.** Run tests with `cd collections-bot && python -m pytest`.

## File Structure

**New Python service `collections-bot/`:**
- `requirements.txt` — pinned deps
- `.env.example` — config template (committed); `.env` is gitignored
- `demo-contacts.example.json` — contacts template (committed); `demo-contacts.json` gitignored
- `.gitignore` — ignore `.env`, `demo-contacts.json`, `*.sqlite`
- `config.py` — env + contacts loading
- `tones.py` — pure DPD/tone/intent/outcome logic (no I/O)
- `store.py` — SQLite conversation store
- `llm.py` — Gemini wrapper + JSON parsing
- `conversation.py` — engine: compose opening, next turn (uses llm + tones)
- `twilio_adapter.py` — send WhatsApp/SMS/Email + inbound signature verify
- `case_lookup.py` — BigQuery case-facts lookup
- `server.py` — FastAPI app wiring it all
- `README.md` — runbook (setup, tunnel, dry-run checklist)
- `tests/` — pytest suite (`conftest.py`, `test_*.py`)

**Webapp (Next.js):**
- Create: `webapp/app/api/outreach/[...path]/route.ts` — proxy to `BOT_URL`
- Create: `webapp/app/(dashboard)/outreach/page.tsx` — outreach UI + live transcript
- Modify: `webapp/components/shell/app-sidebar.tsx` — add "Outreach" nav item

---

### Task 1: Scaffold service (deps, config, contacts, gitignore)

**Files:**
- Create: `collections-bot/requirements.txt`
- Create: `collections-bot/.gitignore`
- Create: `collections-bot/.env.example`
- Create: `collections-bot/demo-contacts.example.json`
- Create: `collections-bot/config.py`
- Test: `collections-bot/tests/test_config.py`
- Test: `collections-bot/tests/conftest.py`

**Interfaces:**
- Produces: `config.Settings` (dataclass with all env fields), `config.load_settings(env: dict|None=None) -> Settings`, `config.Contact` (dataclass: `customer_id, name, dpd_stage, whatsapp, sms, email`), `config.load_contacts(path: str) -> dict[str, Contact]`.

- [ ] **Step 1: Create `requirements.txt`**

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
twilio>=9.0.0
sendgrid>=6.11.0
google-genai>=1.0.0
google-cloud-bigquery>=3.25.0
python-dotenv>=1.0.0
pytest>=8.0.0
httpx>=0.27.0
```

- [ ] **Step 2: Create `.gitignore`**

```
.env
demo-contacts.json
*.sqlite
__pycache__/
.pytest_cache/
```

- [ ] **Step 3: Create `.env.example`** (copy the block from spec §5 verbatim)

```bash
# Twilio core
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
# Senders (one purchased number)
TWILIO_SMS_FROM=+1XXXXXXXXXX
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
# Email via SendGrid
SENDGRID_API_KEY=SG.xxxxxxxx
EMAIL_FROM=collections@yourverifieddomain.com
EMAIL_FROM_NAME=Bank Muamalat Collections
# Gemini
GOOGLE_API_KEY=xxxxxxxx
GEMINI_MODEL=gemini-2.5-flash
# BigQuery lookup
GCP_PROJECT=nbs-playground-data-analytics
BQ_LOCATION=asia-southeast2
GOLD_DATASET=demo_gold_analytics
# Service
BOT_PORT=8100
CONVERSATION_DB_PATH=./conversations.sqlite
PUBLIC_BASE_URL=
VERIFY_TWILIO_SIGNATURE=true
```

- [ ] **Step 4: Create `demo-contacts.example.json`**

```json
{
  "0010000042": {
    "name": "Encik Ahmad",
    "dpd_stage": "SOFT_REMINDER",
    "whatsapp": "whatsapp:+60123456789",
    "sms": "+15005550006",
    "email": "ahmad@example.com"
  },
  "0010000088": {
    "name": "Puan Siti",
    "dpd_stage": "INTENSIVE",
    "whatsapp": "whatsapp:+60123456790",
    "sms": "+15005550006",
    "email": "siti@example.com"
  },
  "0010000131": {
    "name": "Encik Rajesh",
    "dpd_stage": "RECOVERY_LEGAL",
    "whatsapp": "whatsapp:+60123456791",
    "sms": "+15005550006",
    "email": "rajesh@example.com"
  }
}
```

- [ ] **Step 5: Create `tests/conftest.py`**

```python
import sys
from pathlib import Path

# Make the service root importable as top-level modules in tests.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 6: Write the failing test `tests/test_config.py`**

```python
import json
from config import load_settings, load_contacts

def test_load_settings_reads_env_values():
    env = {
        "TWILIO_ACCOUNT_SID": "AC1", "TWILIO_AUTH_TOKEN": "tok",
        "TWILIO_SMS_FROM": "+1999", "TWILIO_WHATSAPP_FROM": "whatsapp:+1888",
        "SENDGRID_API_KEY": "SG.x", "EMAIL_FROM": "a@b.com", "EMAIL_FROM_NAME": "Bank",
        "GOOGLE_API_KEY": "g", "GEMINI_MODEL": "gemini-2.5-flash",
        "GCP_PROJECT": "proj", "BQ_LOCATION": "asia-southeast2", "GOLD_DATASET": "gold",
        "BOT_PORT": "8100", "CONVERSATION_DB_PATH": "./x.sqlite",
        "PUBLIC_BASE_URL": "https://t.ngrok.app", "VERIFY_TWILIO_SIGNATURE": "false",
    }
    s = load_settings(env)
    assert s.twilio_account_sid == "AC1"
    assert s.whatsapp_from == "whatsapp:+1888"
    assert s.gemini_model == "gemini-2.5-flash"
    assert s.verify_twilio_signature is False
    assert s.bot_port == 8100

def test_load_contacts_parses_file(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({
        "001": {"name": "A", "dpd_stage": "SOFT_REMINDER",
                "whatsapp": "whatsapp:+1", "sms": "+1", "email": "a@b.com"}
    }))
    contacts = load_contacts(str(p))
    assert contacts["001"].name == "A"
    assert contacts["001"].dpd_stage == "SOFT_REMINDER"
```

- [ ] **Step 7: Run test to verify it fails**

Run: `cd collections-bot && python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 8: Create `config.py`**

```python
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
    sendgrid_api_key: str
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
        sendgrid_api_key=g("SENDGRID_API_KEY"),
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
    )


def load_contacts(path: str) -> dict[str, Contact]:
    with open(path) as f:
        raw = json.load(f)
    return {
        cif: Contact(customer_id=cif, name=v["name"], dpd_stage=v["dpd_stage"],
                     whatsapp=v.get("whatsapp", ""), sms=v.get("sms", ""), email=v.get("email", ""))
        for cif, v in raw.items()
    }
```

- [ ] **Step 9: Run test to verify it passes**

Run: `cd collections-bot && python -m pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 10: Commit**

```bash
git add collections-bot/requirements.txt collections-bot/.gitignore collections-bot/.env.example \
  collections-bot/demo-contacts.example.json collections-bot/config.py \
  collections-bot/tests/conftest.py collections-bot/tests/test_config.py
git commit -m "feat(collections-bot): scaffold service config + contacts loading"
```

---

### Task 2: Tone / intent / outcome core logic (pure)

**Files:**
- Create: `collections-bot/tones.py`
- Test: `collections-bot/tests/test_tones.py`

**Interfaces:**
- Produces: `tones.stage_for_dpd(dpd: int) -> str`, `tones.floor_tone(stage: str) -> str`, `tones.resolve_tone(stage: str, intent: str) -> str`, `tones.outcome_for(intent: str) -> str`, `tones.tone_guidance(tone: str) -> str`, and constants `STAGES`, `INTENTS`, `TONE_ORDER`, `CANNED_OPENING: dict[str,str]`, `CANNED_REPLY: dict[str,str]`.

- [ ] **Step 1: Write the failing test `tests/test_tones.py`**

```python
import tones

def test_stage_for_dpd_boundaries():
    assert tones.stage_for_dpd(0) == "SOFT_REMINDER"
    assert tones.stage_for_dpd(30) == "SOFT_REMINDER"
    assert tones.stage_for_dpd(31) == "INTENSIVE"
    assert tones.stage_for_dpd(60) == "INTENSIVE"
    assert tones.stage_for_dpd(61) == "FIELD_VISIT"
    assert tones.stage_for_dpd(90) == "FIELD_VISIT"
    assert tones.stage_for_dpd(91) == "RECOVERY_LEGAL"
    assert tones.stage_for_dpd(120) == "RECOVERY_LEGAL"

def test_floor_tone_per_stage():
    assert tones.floor_tone("SOFT_REMINDER") == "FRIENDLY"
    assert tones.floor_tone("INTENSIVE") == "FIRM"
    assert tones.floor_tone("FIELD_VISIT") == "ASSERTIVE"
    assert tones.floor_tone("RECOVERY_LEGAL") == "LEGAL"

def test_resolve_tone_never_below_floor():
    # AGREE keeps the floor even at a late stage (no de-escalation to friendly).
    assert tones.resolve_tone("FIELD_VISIT", "AGREE") == "ASSERTIVE"
    # HOSTILE bumps one sterner from the floor...
    assert tones.resolve_tone("SOFT_REMINDER", "HOSTILE") == "FIRM"
    # ...but is capped at LEGAL.
    assert tones.resolve_tone("RECOVERY_LEGAL", "HOSTILE") == "LEGAL"
    # HARDSHIP stays at the floor (empathy layered on, tone not softened).
    assert tones.resolve_tone("INTENSIVE", "HARDSHIP") == "FIRM"

def test_outcome_for_intent():
    assert tones.outcome_for("AGREE") == "PTP_OBTAINED"
    assert tones.outcome_for("HARDSHIP") == "RESTRUCTURE_OFFERED"
    assert tones.outcome_for("HOSTILE") == "HOSTILE_ESCALATED"
    assert tones.outcome_for("OTHER") == "OPENED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd collections-bot && python -m pytest tests/test_tones.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tones'`

- [ ] **Step 3: Create `tones.py`**

```python
"""Pure DPD -> stage -> tone -> outcome logic. No I/O. Single source of truth for
the collections tone state machine (see spec section 4)."""

STAGES = ["SOFT_REMINDER", "INTENSIVE", "FIELD_VISIT", "RECOVERY_LEGAL"]
INTENTS = ["AGREE", "HOSTILE", "HARDSHIP", "OTHER"]
TONE_ORDER = ["FRIENDLY", "FIRM", "ASSERTIVE", "LEGAL"]

_FLOOR = {
    "SOFT_REMINDER": "FRIENDLY",
    "INTENSIVE": "FIRM",
    "FIELD_VISIT": "ASSERTIVE",
    "RECOVERY_LEGAL": "LEGAL",
}

_TONE_GUIDANCE = {
    "FRIENDLY": "Friendly, polite and helpful ('bot manis'). A gentle nudge, warm and respectful.",
    "FIRM": "Neutral, firm and persistent. Warn plainly about accumulating arrears and the credit-score impact.",
    "ASSERTIVE": "Assertive and authoritative. Serious; urge immediate action and warn of escalation.",
    "LEGAL": "Direct and authoritative ('agak keras'). State the legal-warning / field-visit escalation clearly and formally.",
}

_OUTCOME = {
    "AGREE": "PTP_OBTAINED",
    "HARDSHIP": "RESTRUCTURE_OFFERED",
    "HOSTILE": "HOSTILE_ESCALATED",
    "OTHER": "OPENED",
}

CANNED_OPENING = {
    "SOFT_REMINDER": "Salam, ini peringatan mesra daripada Bank Muamalat berkenaan bayaran pembiayaan anda yang telah tertunggak. Sila buat pembayaran secepat mungkin. Terima kasih.",
    "INTENSIVE": "Salam daripada Bank Muamalat. Bayaran pembiayaan anda kini tertunggak dan jumlah tunggakan semakin meningkat. Ini boleh menjejaskan rekod kredit anda. Sila jelaskan bayaran segera.",
    "FIELD_VISIT": "Notis daripada Bank Muamalat: akaun pembiayaan anda tertunggak dengan serius. Sila hubungi kami dan buat bayaran segera untuk mengelakkan tindakan lanjut.",
    "RECOVERY_LEGAL": "Notis rasmi Bank Muamalat: akaun anda kini di peringkat pemulihan. Kegagalan menjelaskan tunggakan boleh membawa kepada tindakan undang-undang atau lawatan penagihan. Sila hubungi kami dengan segera.",
}

CANNED_REPLY = {
    "SOFT_REMINDER": "Terima kasih atas maklum balas anda. Sila hubungi kami jika anda memerlukan bantuan untuk pembayaran.",
    "INTENSIVE": "Kami memahami. Sila jelaskan tunggakan anda secepat mungkin bagi mengelakkan kesan kepada rekod kredit anda.",
    "FIELD_VISIT": "Sila ambil tindakan segera untuk menjelaskan tunggakan bagi mengelakkan tindakan lanjut.",
    "RECOVERY_LEGAL": "Akaun anda memerlukan penyelesaian segera. Sila hubungi kami untuk mengelakkan tindakan undang-undang.",
}


def stage_for_dpd(dpd: int) -> str:
    if dpd <= 30:
        return "SOFT_REMINDER"
    if dpd <= 60:
        return "INTENSIVE"
    if dpd <= 90:
        return "FIELD_VISIT"
    return "RECOVERY_LEGAL"


def floor_tone(stage: str) -> str:
    return _FLOOR[stage]


def resolve_tone(stage: str, intent: str) -> str:
    floor = floor_tone(stage)
    if intent == "HOSTILE":
        idx = min(TONE_ORDER.index(floor) + 1, len(TONE_ORDER) - 1)
        return TONE_ORDER[idx]
    return floor


def outcome_for(intent: str) -> str:
    return _OUTCOME.get(intent, "OPENED")


def tone_guidance(tone: str) -> str:
    return _TONE_GUIDANCE[tone]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd collections-bot && python -m pytest tests/test_tones.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add collections-bot/tones.py collections-bot/tests/test_tones.py
git commit -m "feat(collections-bot): DPD tone/intent/outcome state machine"
```

---

### Task 3: SQLite conversation store

**Files:**
- Create: `collections-bot/store.py`
- Test: `collections-bot/tests/test_store.py`

**Interfaces:**
- Produces: `store.Store(db_path: str)` with methods:
  - `create_conversation(customer_id, channel, dpd, stage, tone, language, dest) -> str` (returns new id)
  - `add_message(conversation_id, direction, channel, body, twilio_sid=None, status="sent") -> None`
  - `get_conversation(conversation_id) -> dict | None`
  - `latest_open_by_dest(dest) -> dict | None` (most recent conversation whose `dest` matches; used by the webhook to find the thread from an inbound `From`)
  - `update_conversation(conversation_id, **fields) -> None` (allowed fields: `tone, language, detected_intent, outcome`)
  - `message_exists(twilio_sid) -> bool` (idempotency for inbound retries)
  - `list_conversations() -> list[dict]`
  - `get_with_messages(conversation_id) -> dict | None` (conversation dict + `messages` list)

- [ ] **Step 1: Write the failing test `tests/test_store.py`**

```python
from store import Store

def make_store(tmp_path):
    return Store(str(tmp_path / "t.sqlite"))

def test_create_and_get_conversation(tmp_path):
    s = make_store(tmp_path)
    cid = s.create_conversation("001", "whatsapp", 45, "INTENSIVE", "FIRM", "ms", "whatsapp:+60")
    conv = s.get_conversation(cid)
    assert conv["customer_id"] == "001"
    assert conv["stage"] == "INTENSIVE"
    assert conv["outcome"] == "OPENED"
    assert conv["dest"] == "whatsapp:+60"

def test_add_messages_and_get_with_messages(tmp_path):
    s = make_store(tmp_path)
    cid = s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms", "whatsapp:+60")
    s.add_message(cid, "out", "whatsapp", "Salam", twilio_sid="SM1")
    s.add_message(cid, "in", "whatsapp", "ok", twilio_sid="SM2")
    full = s.get_with_messages(cid)
    assert len(full["messages"]) == 2
    assert full["messages"][0]["direction"] == "out"
    assert full["messages"][1]["body"] == "ok"

def test_latest_open_by_dest(tmp_path):
    s = make_store(tmp_path)
    s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms", "whatsapp:+60")
    cid2 = s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms", "whatsapp:+60")
    assert s.latest_open_by_dest("whatsapp:+60")["id"] == cid2
    assert s.latest_open_by_dest("whatsapp:+99") is None

def test_update_conversation_and_message_exists(tmp_path):
    s = make_store(tmp_path)
    cid = s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms", "whatsapp:+60")
    s.update_conversation(cid, detected_intent="HARDSHIP", outcome="RESTRUCTURE_OFFERED", tone="FRIENDLY")
    conv = s.get_conversation(cid)
    assert conv["detected_intent"] == "HARDSHIP"
    assert conv["outcome"] == "RESTRUCTURE_OFFERED"
    s.add_message(cid, "in", "whatsapp", "hi", twilio_sid="SMX")
    assert s.message_exists("SMX") is True
    assert s.message_exists("NOPE") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd collections-bot && python -m pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'store'`

- [ ] **Step 3: Create `store.py`**

```python
"""SQLite-backed conversation + message store for the collections bot."""
import sqlite3
import uuid
from datetime import datetime, timezone

_ALLOWED_UPDATES = {"tone", "language", "detected_intent", "outcome"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY, customer_id TEXT, channel TEXT,
                    dpd INTEGER, stage TEXT, tone TEXT, language TEXT,
                    detected_intent TEXT, outcome TEXT, dest TEXT,
                    started_at TEXT, updated_at TEXT
                )""")
            c.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY, conversation_id TEXT, direction TEXT,
                    channel TEXT, body TEXT, twilio_sid TEXT, status TEXT, ts TEXT
                )""")

    def create_conversation(self, customer_id, channel, dpd, stage, tone, language, dest) -> str:
        cid = uuid.uuid4().hex
        ts = _now()
        with self._conn() as c:
            c.execute(
                """INSERT INTO conversations
                   (id, customer_id, channel, dpd, stage, tone, language,
                    detected_intent, outcome, dest, started_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cid, customer_id, channel, dpd, stage, tone, language,
                 None, "OPENED", dest, ts, ts),
            )
        return cid

    def add_message(self, conversation_id, direction, channel, body,
                    twilio_sid=None, status="sent") -> None:
        with self._conn() as c:
            c.execute(
                """INSERT INTO messages
                   (id, conversation_id, direction, channel, body, twilio_sid, status, ts)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (uuid.uuid4().hex, conversation_id, direction, channel, body,
                 twilio_sid, status, _now()),
            )

    def get_conversation(self, conversation_id) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        return dict(row) if row else None

    def latest_open_by_dest(self, dest) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM conversations WHERE dest=? ORDER BY started_at DESC, rowid DESC LIMIT 1",
                (dest,),
            ).fetchone()
        return dict(row) if row else None

    def update_conversation(self, conversation_id, **fields) -> None:
        cols = {k: v for k, v in fields.items() if k in _ALLOWED_UPDATES}
        if not cols:
            return
        assignments = ", ".join(f"{k}=?" for k in cols)
        with self._conn() as c:
            c.execute(
                f"UPDATE conversations SET {assignments}, updated_at=? WHERE id=?",
                (*cols.values(), _now(), conversation_id),
            )

    def message_exists(self, twilio_sid) -> bool:
        if not twilio_sid:
            return False
        with self._conn() as c:
            row = c.execute("SELECT 1 FROM messages WHERE twilio_sid=? LIMIT 1", (twilio_sid,)).fetchone()
        return row is not None

    def list_conversations(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM conversations ORDER BY started_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_with_messages(self, conversation_id) -> dict | None:
        conv = self.get_conversation(conversation_id)
        if not conv:
            return None
        with self._conn() as c:
            msgs = c.execute(
                "SELECT * FROM messages WHERE conversation_id=? ORDER BY ts ASC, rowid ASC",
                (conversation_id,),
            ).fetchall()
        conv["messages"] = [dict(m) for m in msgs]
        return conv
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd collections-bot && python -m pytest tests/test_store.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add collections-bot/store.py collections-bot/tests/test_store.py
git commit -m "feat(collections-bot): SQLite conversation store"
```

---

### Task 4: Gemini LLM wrapper + JSON parsing

**Files:**
- Create: `collections-bot/llm.py`
- Test: `collections-bot/tests/test_llm.py`

**Interfaces:**
- Produces:
  - `llm.parse_json_block(text: str) -> dict` — tolerant extraction of a JSON object from raw model text (handles ```json fences and surrounding prose); raises `ValueError` if none found.
  - `llm.Gemini(model: str, api_key: str = "")` with `generate(system: str, user: str) -> str`.
  - `llm.LLMError(Exception)`.
- Consumes: nothing from earlier tasks.

Note: `Gemini.generate` is thin and network-bound; tests cover only `parse_json_block` (pure). The engine (Task 5) takes any callable `llm(system, user) -> str`, so `Gemini.generate` is injected there and mocked in tests.

- [ ] **Step 1: Write the failing test `tests/test_llm.py`**

```python
import pytest
from llm import parse_json_block

def test_parse_plain_json():
    assert parse_json_block('{"intent": "AGREE", "language": "en", "reply": "ok"}')["intent"] == "AGREE"

def test_parse_fenced_json_with_prose():
    raw = 'Sure!\n```json\n{"intent": "HARDSHIP", "language": "ms", "reply": "baik"}\n```\nthanks'
    out = parse_json_block(raw)
    assert out["intent"] == "HARDSHIP"
    assert out["reply"] == "baik"

def test_parse_raises_when_no_json():
    with pytest.raises(ValueError):
        parse_json_block("no json here")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd collections-bot && python -m pytest tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'llm'`

- [ ] **Step 3: Create `llm.py`**

```python
"""Gemini wrapper + tolerant JSON extraction for the collections bot."""
import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


class LLMError(Exception):
    pass


def parse_json_block(text: str) -> dict:
    """Extract the first JSON object from model output (fenced or bare)."""
    if text:
        m = _FENCE_RE.search(text)
        if m:
            return json.loads(m.group(1))
        m = _OBJ_RE.search(text)
        if m:
            return json.loads(m.group(0))
    raise ValueError("no JSON object found in model output")


class Gemini:
    def __init__(self, model: str, api_key: str = ""):
        self._model = model
        self._api_key = api_key
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from google import genai  # imported lazily so tests need no SDK/creds
            # api_key set -> Gemini Developer API; empty -> Vertex via ADC/env.
            self._client = genai.Client(api_key=self._api_key) if self._api_key else genai.Client()
        return self._client

    def generate(self, system: str, user: str) -> str:
        try:
            from google.genai import types
            client = self._ensure_client()
            resp = client.models.generate_content(
                model=self._model,
                contents=user,
                config=types.GenerateContentConfig(system_instruction=system, temperature=0.4),
            )
            return resp.text or ""
        except Exception as e:  # noqa: BLE001 - surface a single wrapped error to the engine
            raise LLMError(str(e)) from e
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd collections-bot && python -m pytest tests/test_llm.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add collections-bot/llm.py collections-bot/tests/test_llm.py
git commit -m "feat(collections-bot): Gemini wrapper + JSON parsing"
```

---

### Task 5: Conversation engine (compose opening + next turn)

**Files:**
- Create: `collections-bot/conversation.py`
- Test: `collections-bot/tests/test_conversation.py`

**Interfaces:**
- Consumes: `tones` (Task 2), `llm.parse_json_block` + `llm.LLMError` (Task 4).
- Produces:
  - `conversation.CaseFacts` dataclass: `stage: str, dpd: int, outstanding: float, loan_id: str, name: str`.
  - `conversation.Turn` dataclass: `reply: str, intent: str, language: str, tone: str, outcome: str, degraded: bool`.
  - `conversation.compose_opening(facts: CaseFacts, llm_call, default_language="ms") -> str` — `llm_call` is `Callable[[str,str],str]`; falls back to `tones.CANNED_OPENING[stage]` on `LLMError`.
  - `conversation.next_turn(*, stage, current_language, history, inbound_text, llm_call) -> Turn` — classifies intent+language and drafts a reply in the resolved tone; applies `tones.resolve_tone`/`outcome_for`; falls back to `tones.CANNED_REPLY[stage]` (intent `OTHER`, `degraded=True`) on `LLMError` or unparseable output.
  - `conversation.build_opening_prompt(facts, default_language) -> tuple[str,str]` and `conversation.build_reply_prompt(stage, current_language, history, inbound_text) -> tuple[str,str]` (exposed for testing the prompt carries case facts + rules).

- [ ] **Step 1: Write the failing test `tests/test_conversation.py`**

```python
import pytest
from conversation import (
    CaseFacts, compose_opening, next_turn, build_opening_prompt,
)
from llm import LLMError

FACTS = CaseFacts(stage="INTENSIVE", dpd=45, outstanding=3200.0, loan_id="LN9", name="Encik Ahmad")

def test_build_opening_prompt_includes_case_facts_and_tone():
    system, user = build_opening_prompt(FACTS, default_language="ms")
    assert "3200" in user or "3,200" in user
    assert "45" in user
    assert "Encik Ahmad" in user
    assert "FIRM" in system  # INTENSIVE floor tone name surfaced to the model

def test_compose_opening_uses_llm_when_available():
    out = compose_opening(FACTS, llm_call=lambda s, u: "Salam Encik Ahmad, sila jelaskan bayaran.")
    assert "Ahmad" in out

def test_compose_opening_falls_back_on_llm_error():
    def boom(s, u):
        raise LLMError("down")
    out = compose_opening(FACTS, llm_call=boom)
    assert "Bank Muamalat" in out  # canned INTENSIVE opening

def test_next_turn_hardship_offers_restructure():
    def fake(s, u):
        return '{"intent":"HARDSHIP","language":"ms","reply":"Kami boleh tawarkan penstrukturan semula."}'
    turn = next_turn(stage="INTENSIVE", current_language="ms", history=[],
                     inbound_text="saya tengah susah", llm_call=fake)
    assert turn.intent == "HARDSHIP"
    assert turn.outcome == "RESTRUCTURE_OFFERED"
    assert turn.tone == "FIRM"        # floor held, not softened
    assert turn.degraded is False

def test_next_turn_hostile_escalates_tone():
    def fake(s, u):
        return '{"intent":"HOSTILE","language":"en","reply":"This is a formal notice."}'
    turn = next_turn(stage="SOFT_REMINDER", current_language="ms", history=[],
                     inbound_text="I will not pay", llm_call=fake)
    assert turn.intent == "HOSTILE"
    assert turn.outcome == "HOSTILE_ESCALATED"
    assert turn.tone == "FIRM"        # bumped one sterner from FRIENDLY floor
    assert turn.language == "en"      # switched to the debtor's language

def test_next_turn_falls_back_on_bad_output():
    def bad(s, u):
        return "not json at all"
    turn = next_turn(stage="RECOVERY_LEGAL", current_language="ms", history=[],
                     inbound_text="???", llm_call=bad)
    assert turn.degraded is True
    assert turn.intent == "OTHER"
    assert turn.reply == __import__("tones").CANNED_REPLY["RECOVERY_LEGAL"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd collections-bot && python -m pytest tests/test_conversation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'conversation'`

- [ ] **Step 3: Create `conversation.py`**

```python
"""Conversation engine: compose the DPD-toned opening and adapt to each reply.

Pure orchestration around an injected `llm_call(system, user) -> str`, so it is
fully testable with a fake callable (no network)."""
from dataclasses import dataclass

import tones
from llm import LLMError, parse_json_block


@dataclass(frozen=True)
class CaseFacts:
    stage: str
    dpd: int
    outstanding: float
    loan_id: str
    name: str


@dataclass(frozen=True)
class Turn:
    reply: str
    intent: str
    language: str
    tone: str
    outcome: str
    degraded: bool


_LANG_NAME = {"ms": "Bahasa Malaysia", "en": "English"}


def build_opening_prompt(facts: CaseFacts, default_language: str) -> tuple[str, str]:
    tone = tones.floor_tone(facts.stage)
    system = (
        "You are an outbound collections assistant for Bank Muamalat, a Malaysian Islamic bank. "
        f"Write ONE short outreach message (2-4 sentences). Tone: {tone}. {tones.tone_guidance(tone)} "
        f"Write in {_LANG_NAME.get(default_language, 'Bahasa Malaysia')}. "
        "This is Islamic financing: never mention interest or penalty interest. "
        "Do not invent figures beyond those provided. Output only the message text, no preamble."
    )
    user = (
        f"Debtor name: {facts.name}\n"
        f"Financing account: {facts.loan_id}\n"
        f"Days past due (DPD): {facts.dpd}\n"
        f"Outstanding arrears: RM {facts.outstanding:,.2f}\n"
        f"Collections stage: {facts.stage}\n"
        "Write the opening reminder message now."
    )
    return system, user


def compose_opening(facts: CaseFacts, llm_call, default_language: str = "ms") -> str:
    system, user = build_opening_prompt(facts, default_language)
    try:
        text = llm_call(system, user).strip()
        return text or tones.CANNED_OPENING[facts.stage]
    except LLMError:
        return tones.CANNED_OPENING[facts.stage]


def build_reply_prompt(stage: str, current_language: str, history: list, inbound_text: str) -> tuple[str, str]:
    floor = tones.floor_tone(stage)
    convo = "\n".join(f"{m['direction']}: {m['body']}" for m in history)
    system = (
        "You are an outbound collections assistant for Bank Muamalat (Malaysian Islamic bank). "
        "Classify the debtor's latest reply and draft the next message. "
        "Reply ONLY with a JSON object: "
        '{"intent": one of ["AGREE","HOSTILE","HARDSHIP","OTHER"], '
        '"language": "ms" or "en" (match the debtor\'s language), '
        '"reply": the message text to send back}. '
        f"Base tone floor for this stage ({stage}) is {floor} — never be softer than this floor. "
        "If intent is HOSTILE, be sterner, official and firm about consequences (legal warning / field visit). "
        "If intent is HARDSHIP, be empathetic and OFFER restructuring ('Rekonstruksi'): "
        "waive or reduce charges (no interest — this is Islamic financing), adjust the payment plan, "
        "or extend installments. If intent is AGREE, thank them and give clear payment guidance. "
        "Keep the reply to 2-4 sentences."
    )
    user = (
        f"Conversation so far:\n{convo}\n\n"
        f"Debtor's latest reply: {inbound_text}\n"
        f"Current language: {current_language}\n"
        "Return the JSON now."
    )
    return system, user


def next_turn(*, stage: str, current_language: str, history: list, inbound_text: str, llm_call) -> Turn:
    system, user = build_reply_prompt(stage, current_language, history, inbound_text)
    try:
        parsed = parse_json_block(llm_call(system, user))
        intent = parsed.get("intent", "OTHER")
        if intent not in tones.INTENTS:
            intent = "OTHER"
        language = parsed.get("language", current_language)
        if language not in ("ms", "en"):
            language = current_language
        reply = (parsed.get("reply") or "").strip()
        if not reply:
            raise ValueError("empty reply")
        return Turn(
            reply=reply, intent=intent, language=language,
            tone=tones.resolve_tone(stage, intent), outcome=tones.outcome_for(intent),
            degraded=False,
        )
    except (LLMError, ValueError):
        return Turn(
            reply=tones.CANNED_REPLY[stage], intent="OTHER", language=current_language,
            tone=tones.floor_tone(stage), outcome="OPENED", degraded=True,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd collections-bot && python -m pytest tests/test_conversation.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add collections-bot/conversation.py collections-bot/tests/test_conversation.py
git commit -m "feat(collections-bot): bilingual conversation engine with tone adaptation"
```

---

### Task 6: Twilio adapter (send + signature verify)

**Files:**
- Create: `collections-bot/twilio_adapter.py`
- Test: `collections-bot/tests/test_twilio_adapter.py`

**Interfaces:**
- Consumes: `config.Settings` (Task 1).
- Produces: `twilio_adapter.TwilioAdapter(settings)` with:
  - `send(channel: str, to: str, body: str, subject: str = "") -> tuple[str, str]` returning `(sid, status)`; dispatches to WhatsApp/SMS/Email. Raises `SendError` on failure.
  - `verify(url: str, params: dict, signature: str) -> bool`.
  - Internals `_send_whatsapp`, `_send_sms`, `_send_email` (injected clients for tests via constructor kwargs `messages_client`, `email_client`, `validator`).
  - `twilio_adapter.SendError(Exception)`.

- [ ] **Step 1: Write the failing test `tests/test_twilio_adapter.py`**

```python
import pytest
from config import Settings
from twilio_adapter import TwilioAdapter, SendError

def settings():
    return Settings(
        twilio_account_sid="AC", twilio_auth_token="tok", sms_from="+1999",
        whatsapp_from="whatsapp:+1888", sendgrid_api_key="SG", email_from="a@b.com",
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd collections-bot && python -m pytest tests/test_twilio_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'twilio_adapter'`

- [ ] **Step 3: Create `twilio_adapter.py`**

```python
"""Twilio (WhatsApp/SMS) + SendGrid (Email) send and inbound signature verify."""


class SendError(Exception):
    pass


class TwilioAdapter:
    def __init__(self, settings, messages_client=None, email_client=None, validator=None):
        self._s = settings
        self._messages = messages_client
        self._email = email_client
        self._validator = validator

    # -- lazy real clients (skipped when tests inject fakes) --------------
    def _messages_client(self):
        if self._messages is None:
            from twilio.rest import Client
            self._messages = Client(self._s.twilio_account_sid, self._s.twilio_auth_token).messages
        return self._messages

    def _email_client(self):
        if self._email is None:
            from sendgrid import SendGridAPIClient
            self._email = SendGridAPIClient(self._s.sendgrid_api_key)
        return self._email

    def _request_validator(self):
        if self._validator is None:
            from twilio.request_validator import RequestValidator
            self._validator = RequestValidator(self._s.twilio_auth_token)
        return self._validator

    # -- public API -------------------------------------------------------
    def send(self, channel: str, to: str, body: str, subject: str = "") -> tuple[str, str]:
        if channel == "whatsapp":
            return self._send_message(self._s.whatsapp_from, to, body)
        if channel == "sms":
            return self._send_message(self._s.sms_from, to, body)
        if channel == "email":
            return self._send_email(to, subject or "Bank Muamalat — Peringatan Pembayaran", body)
        raise SendError(f"unknown channel: {channel}")

    def _send_message(self, from_: str, to: str, body: str) -> tuple[str, str]:
        try:
            msg = self._messages_client().create(from_=from_, to=to, body=body)
            return msg.sid, msg.status
        except Exception as e:  # noqa: BLE001
            raise SendError(str(e)) from e

    def _send_email(self, to: str, subject: str, body: str) -> tuple[str, str]:
        try:
            from sendgrid.helpers.mail import Mail
            mail = Mail(
                from_email=(self._s.email_from, self._s.email_from_name),
                to_emails=to, subject=subject, plain_text_content=body,
            )
            resp = self._email_client().send(mail)
            return (resp.headers.get("X-Message-Id", "email") if hasattr(resp, "headers") else "email",
                    str(getattr(resp, "status_code", "sent")))
        except Exception as e:  # noqa: BLE001
            raise SendError(str(e)) from e

    def verify(self, url: str, params: dict, signature: str) -> bool:
        return bool(self._request_validator().validate(url, params, signature))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd collections-bot && python -m pytest tests/test_twilio_adapter.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add collections-bot/twilio_adapter.py collections-bot/tests/test_twilio_adapter.py
git commit -m "feat(collections-bot): Twilio + SendGrid adapter with signature verify"
```

---

### Task 7: BigQuery case-facts lookup

**Files:**
- Create: `collections-bot/case_lookup.py`
- Test: `collections-bot/tests/test_case_lookup.py`

**Interfaces:**
- Consumes: `config.Settings` (Task 1), `conversation.CaseFacts` (Task 5).
- Produces: `case_lookup.CaseLookup(settings, client=None)` with `facts_for(customer_id: str, name: str) -> CaseFacts`. Builds SQL against `${GCP_PROJECT}.${GOLD_DATASET}.mart_collection_recovery` joined to `mart_financing_health`. On no row / client error, returns a safe default `CaseFacts(stage="SOFT_REMINDER", dpd=0, outstanding=0.0, loan_id="", name=name)` so the demo never hard-fails. `client` is injectable for tests.
- Produces: `case_lookup.build_sql(project, dataset) -> str` (exposed for test).

- [ ] **Step 1: Write the failing test `tests/test_case_lookup.py`**

```python
from config import Settings
from case_lookup import CaseLookup, build_sql

def settings():
    return Settings(
        twilio_account_sid="", twilio_auth_token="", sms_from="", whatsapp_from="",
        sendgrid_api_key="", email_from="", email_from_name="", google_api_key="",
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd collections-bot && python -m pytest tests/test_case_lookup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'case_lookup'`

- [ ] **Step 3: Create `case_lookup.py`**

```python
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
```

Note: the test's `FakeClient.query` ignores `job_config`; the real path builds one via `bigquery.QueryJobConfig`. The `import bigquery` inside `facts_for` is only reached on the real path because the injected client short-circuits `_bq()`, but the `QueryJobConfig` line runs regardless — in tests `google.cloud.bigquery` may be installed (it is, via requirements), so this is safe. If the SDK is absent, the `except` returns the default.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd collections-bot && python -m pytest tests/test_case_lookup.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add collections-bot/case_lookup.py collections-bot/tests/test_case_lookup.py
git commit -m "feat(collections-bot): BigQuery case-facts lookup"
```

---

### Task 8: FastAPI server wiring + integration tests

**Files:**
- Create: `collections-bot/server.py`
- Test: `collections-bot/tests/test_server.py`

**Interfaces:**
- Consumes: all prior modules.
- Produces: a FastAPI `app` and a `build_app(settings, contacts, store, adapter, lookup, llm_call) -> FastAPI` factory (dependency-injected so tests pass fakes). Module-level `app` is built from real config for uvicorn.
- Endpoints:
  - `GET /healthz` → `{"ok": true}`
  - `GET /contacts` → `[{customer_id, name, dpd_stage, channels}]`
  - `POST /start` body `{customer_id, channel}` → `{conversation_id}` (422 if unknown CIF)
  - `GET /conversations` → `[conversation, ...]`
  - `GET /conversations/{id}` → `{...conversation, messages: [...]}` (404 if missing)
  - `POST /twilio/inbound` (form-encoded) → `""` (TwiML-empty, 200); verifies signature, dedupes on `MessageSid`, runs the engine, sends the reply.

- [ ] **Step 1: Write the failing test `tests/test_server.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd collections-bot && python -m pytest tests/test_server.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: Create `server.py`**

```python
"""FastAPI app for the collections bot: outbound trigger + inbound webhook + read model."""
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import conversation
import tones
from config import load_settings, load_contacts


class StartIn(BaseModel):
    customer_id: str
    channel: str = "whatsapp"


def build_app(settings, contacts, store, adapter, lookup, llm_call) -> FastAPI:
    app = FastAPI(title="Bank Muamalat — Collections bot")

    def _channels(contact) -> list[str]:
        out = []
        if contact.whatsapp:
            out.append("whatsapp")
        if contact.sms:
            out.append("sms")
        if contact.email:
            out.append("email")
        return out

    def _dest(contact, channel) -> str:
        return {"whatsapp": contact.whatsapp, "sms": contact.sms, "email": contact.email}[channel]

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/contacts")
    def list_contacts():
        return [
            {"customer_id": c.customer_id, "name": c.name, "dpd_stage": c.dpd_stage,
             "channels": _channels(c)}
            for c in contacts.values()
        ]

    @app.post("/start")
    def start(inp: StartIn):
        contact = contacts.get(inp.customer_id)
        if not contact:
            return JSONResponse({"error": f"unknown debtor {inp.customer_id}"}, status_code=422)
        facts = lookup.facts_for(inp.customer_id, contact.name)
        opening = conversation.compose_opening(facts, llm_call=llm_call)
        dest = _dest(contact, inp.channel)
        cid = store.create_conversation(
            inp.customer_id, inp.channel, facts.dpd, facts.stage,
            tones.floor_tone(facts.stage), "ms", dest,
        )
        try:
            sid, status = adapter.send(inp.channel, dest, opening)
        except Exception as e:  # noqa: BLE001 - record the failure, surface to UI
            store.add_message(cid, "out", inp.channel, opening, twilio_sid=None, status="failed")
            return JSONResponse({"conversation_id": cid, "send_error": str(e)}, status_code=200)
        store.add_message(cid, "out", inp.channel, opening, twilio_sid=sid, status=status)
        return {"conversation_id": cid}

    @app.get("/conversations")
    def conversations():
        return store.list_conversations()

    @app.get("/conversations/{conversation_id}")
    def conversation_detail(conversation_id: str):
        full = store.get_with_messages(conversation_id)
        if not full:
            return JSONResponse({"error": "not found"}, status_code=404)
        return full

    @app.post("/twilio/inbound")
    async def inbound(request: Request):
        form = dict((await request.form()))
        sender = form.get("From", "")
        body = form.get("Body", "")
        sid = form.get("MessageSid")

        if settings.verify_twilio_signature:
            signature = request.headers.get("X-Twilio-Signature", "")
            url = f"{settings.public_base_url}/twilio/inbound"
            if not adapter.verify(url, form, signature):
                return Response(status_code=403)

        if store.message_exists(sid):
            return Response(content="", media_type="application/xml")

        conv = store.latest_open_by_dest(sender)
        if not conv:
            return Response(content="", media_type="application/xml")

        store.add_message(conv["id"], "in", "whatsapp", body, twilio_sid=sid, status="received")
        history = store.get_with_messages(conv["id"])["messages"]
        turn = conversation.next_turn(
            stage=conv["stage"], current_language=conv["language"],
            history=history, inbound_text=body, llm_call=llm_call,
        )
        try:
            out_sid, out_status = adapter.send("whatsapp", sender, turn.reply)
        except Exception:  # noqa: BLE001
            out_sid, out_status = None, "failed"
        store.add_message(conv["id"], "out", "whatsapp", turn.reply,
                          twilio_sid=out_sid, status="degraded" if turn.degraded else out_status)
        store.update_conversation(conv["id"], tone=turn.tone, language=turn.language,
                                  detected_intent=turn.intent, outcome=turn.outcome)
        return Response(content="", media_type="application/xml")

    return app


def _build_default_app() -> FastAPI:
    from dotenv import load_dotenv
    load_dotenv()
    settings = load_settings()
    contacts = load_contacts("demo-contacts.json")
    from store import Store
    from twilio_adapter import TwilioAdapter
    from case_lookup import CaseLookup
    from llm import Gemini
    store = Store(settings.conversation_db_path)
    adapter = TwilioAdapter(settings)
    lookup = CaseLookup(settings)
    gemini = Gemini(settings.gemini_model, settings.google_api_key)
    return build_app(settings, contacts, store, adapter, lookup, gemini.generate)


app = None  # built lazily by uvicorn entrypoint below to avoid import-time env/file reads


def get_app() -> FastAPI:
    global app
    if app is None:
        app = _build_default_app()
    return app
```

Note: run the server with `uvicorn server:get_app --factory --host 0.0.0.0 --port $BOT_PORT` (see README). Tests use `build_app(...)` directly and never touch `_build_default_app`, so no `.env`/`demo-contacts.json` is needed in CI.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd collections-bot && python -m pytest tests/test_server.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Run the full suite**

Run: `cd collections-bot && python -m pytest -v`
Expected: PASS (all tasks' tests green)

- [ ] **Step 6: Commit**

```bash
git add collections-bot/server.py collections-bot/tests/test_server.py
git commit -m "feat(collections-bot): FastAPI outbound trigger + inbound webhook"
```

---

### Task 9: Service README / runbook

**Files:**
- Create: `collections-bot/README.md`

**Interfaces:** none (documentation).

- [ ] **Step 1: Create `collections-bot/README.md`**

````markdown
# Collections Bot — Bank Muamalat demo

Bot-initiated omnichannel collections outreach (WhatsApp two-way, SMS + Email send-only)
over Twilio, with a DPD-driven tone that adapts to hostile / hardship replies. Driven by
Gemini; reads case facts from BigQuery (read-only). See the design spec in
`docs/superpowers/specs/2026-07-03-omnichannel-collections-bot-design.md`.

## Setup

```bash
cd collections-bot
python -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env                     # fill in Twilio/SendGrid/Gemini values
cp demo-contacts.example.json demo-contacts.json   # set real WhatsApp numbers
```

## Run (local)

```bash
./.venv/bin/uvicorn server:get_app --factory --host 0.0.0.0 --port 8100
```

Expose the inbound webhook with a tunnel and point Twilio at it:

```bash
ngrok http 8100
# copy the https URL into .env as PUBLIC_BASE_URL, then in the Twilio WhatsApp Sandbox
# set "When a message comes in" -> https://<ngrok>/twilio/inbound  (HTTP POST)
```

## Twilio WhatsApp Sandbox

The purchased number sends SMS immediately, but WhatsApp requires the **Sandbox** until the
number is registered with Meta (won't clear for the demo). Each team WhatsApp number must send
`join <sandbox-code>` to the sandbox number once before it can receive messages.

## Tests

```bash
cd collections-bot && python -m pytest -v
```

## Monday dry-run checklist (mirrors PDF §5)

1. Every WhatsApp recipient has sent `join <code>` to the sandbox number.
2. `PUBLIC_BASE_URL` + the Twilio sandbox webhook both point at the current ngrok URL.
3. From the webapp Outreach page, trigger a **SOFT_REMINDER** debtor → confirm friendly opener arrives.
4. Reply **"saya susah / I'm struggling"** → confirm empathetic restructuring offer + `RESTRUCTURE_OFFERED` in the dashboard.
5. Reply **"I won't pay"** → confirm sterner tone + `HOSTILE_ESCALATED`.
6. Trigger a **RECOVERY_LEGAL** debtor → confirm the legal-notice tone.
7. Fire SMS + Email sends → confirm they appear as sent (dummy SMS number is fine).

## Troubleshooting

- **WhatsApp not delivered (Twilio 63015/63016):** recipient hasn't joined the sandbox.
- **Inbound 403:** `PUBLIC_BASE_URL` doesn't match the Twilio webhook URL. Set
  `VERIFY_TWILIO_SIGNATURE=false` temporarily to unblock local wiring, then fix the URL.
- **ngrok restarted:** re-paste the new URL into both `.env` (`PUBLIC_BASE_URL`) and the Twilio
  sandbox webhook (30-second fix).
````

- [ ] **Step 2: Commit**

```bash
git add collections-bot/README.md
git commit -m "docs(collections-bot): setup + demo runbook"
```

---

### Task 10: Webapp proxy route to the bot

**Files:**
- Create: `webapp/app/api/outreach/[...path]/route.ts`

**Interfaces:**
- Produces: a catch-all proxy forwarding `/api/outreach/<tail>` → `${BOT_URL}/<tail>` for GET + POST, mirroring `app/api/chat/route.ts`. `BOT_URL` defaults to `http://localhost:8100`.

- [ ] **Step 1: Create `webapp/app/api/outreach/[...path]/route.ts`**

```typescript
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BOT_URL = process.env.BOT_URL ?? "http://localhost:8100";

async function forward(method: "GET" | "POST", path: string[], body?: string) {
  const url = `${BOT_URL}/${path.join("/")}`;
  try {
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body,
      signal: AbortSignal.timeout(30_000),
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
    });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 502 });
  }
}

export async function GET(_req: Request, { params }: { params: { path: string[] } }) {
  return forward("GET", params.path);
}

export async function POST(req: Request, { params }: { params: { path: string[] } }) {
  const body = await req.text();
  return forward("POST", params.path, body);
}
```

- [ ] **Step 2: Verify the webapp still builds**

Run: `cd webapp && npm run build`
Expected: build succeeds (route compiles; no type errors)

- [ ] **Step 3: Commit**

```bash
git add webapp/app/api/outreach/[...path]/route.ts
git commit -m "feat(webapp): proxy route to collections bot"
```

---

### Task 11: Webapp Outreach page + sidebar nav

**Files:**
- Create: `webapp/app/(dashboard)/outreach/page.tsx`
- Modify: `webapp/components/shell/app-sidebar.tsx`

**Interfaces:**
- Consumes: proxy route (Task 10) endpoints `/api/outreach/contacts`, `/api/outreach/start`, `/api/outreach/conversations/{id}`. Uses existing `PageHeader` (`@/components/insight`), `Card` (`@/components/ui/card`), SWR.

- [ ] **Step 1: Add the nav item in `app-sidebar.tsx`**

Modify the import line (add `Radio`) and the "Credit & Risk" section. Change:

```typescript
  Wallet, Send, HandHeart, AlertTriangle, ArrowLeftRight, ClipboardList, MessagesSquare,
} from "lucide-react";
```
to:
```typescript
  Wallet, Send, HandHeart, AlertTriangle, ArrowLeftRight, ClipboardList, MessagesSquare, Radio,
} from "lucide-react";
```

And change the "Credit & Risk" items array:
```typescript
    items: [
      { href: "/financing-health", label: "Financing health", icon: AlertTriangle },
      { href: "/collections", label: "Collections & recovery", icon: ClipboardList },
      { href: "/churn", label: "Churn risk", icon: TrendingDown },
    ],
```
to:
```typescript
    items: [
      { href: "/financing-health", label: "Financing health", icon: AlertTriangle },
      { href: "/collections", label: "Collections & recovery", icon: ClipboardList },
      { href: "/outreach", label: "Collections outreach", icon: Radio },
      { href: "/churn", label: "Churn risk", icon: TrendingDown },
    ],
```

- [ ] **Step 2: Create `webapp/app/(dashboard)/outreach/page.tsx`**

```typescript
"use client";

import { useState } from "react";
import useSWR from "swr";
import { Radio, Send, Loader2, MessageSquare, AlertTriangle } from "lucide-react";
import { PageHeader } from "@/components/insight";
import { Card } from "@/components/ui/card";

type Contact = { customer_id: string; name: string; dpd_stage: string; channels: string[] };
type Message = { direction: string; channel: string; body: string; status: string; ts: string };
type Conversation = {
  id: string; customer_id: string; channel: string; dpd: number; stage: string;
  tone: string; language: string; detected_intent: string | null; outcome: string;
  messages: Message[];
};

const fetcher = (u: string) => fetch(u).then((r) => r.json());

const OUTCOME_STYLE: Record<string, string> = {
  OPENED: "bg-muted text-foreground",
  PTP_OBTAINED: "bg-amber-100 text-amber-900",
  RESTRUCTURE_OFFERED: "bg-emerald-100 text-emerald-900",
  HOSTILE_ESCALATED: "bg-red-100 text-red-900",
  NO_RESPONSE: "bg-muted text-muted-foreground",
};

export default function OutreachPage() {
  const { data: contacts } = useSWR<Contact[]>("/api/outreach/contacts", fetcher);
  const [channel, setChannel] = useState("whatsapp");
  const [convId, setConvId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const { data: conv } = useSWR<Conversation>(
    convId ? `/api/outreach/conversations/${convId}` : null,
    fetcher,
    { refreshInterval: 1500 },
  );

  async function startOutreach(customer_id: string) {
    setSending(true);
    setErr(null);
    try {
      const res = await fetch("/api/outreach/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer_id, channel }),
      });
      const data = await res.json();
      if (!res.ok) setErr(data.error ?? `Error ${res.status}`);
      else {
        setConvId(data.conversation_id);
        if (data.send_error) setErr(`Sent recorded but delivery failed: ${data.send_error}`);
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Collections outreach"
        subtitle="Bot-initiated omnichannel reminders (WhatsApp two-way, SMS + Email notice) with a DPD-driven tone that adapts to the debtor's reply."
      />

      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Card className="space-y-4 p-4">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Channel</p>
            <div className="flex gap-2">
              {["whatsapp", "sms", "email"].map((ch) => (
                <button
                  key={ch}
                  onClick={() => setChannel(ch)}
                  className={`rounded-lg border px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                    channel === ch ? "bg-primary text-primary-foreground" : "bg-card hover:bg-muted"
                  }`}
                >
                  {ch}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Debtor (by DPD stage)</p>
            <div className="space-y-2">
              {(contacts ?? []).map((c) => (
                <button
                  key={c.customer_id}
                  disabled={sending || !c.channels.includes(channel)}
                  onClick={() => startOutreach(c.customer_id)}
                  className="flex w-full items-center justify-between rounded-lg border bg-card px-3 py-2 text-left text-sm transition-colors hover:bg-muted disabled:opacity-40"
                >
                  <span>
                    <span className="font-medium">{c.name}</span>
                    <span className="ml-2 text-xs text-muted-foreground">{c.customer_id}</span>
                  </span>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium">{c.dpd_stage}</span>
                </button>
              ))}
            </div>
          </div>
          {sending && (
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Sending…
            </p>
          )}
          {err && (
            <p className="flex items-start gap-2 rounded-lg bg-red-50 p-2 text-xs text-red-800">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {err}
            </p>
          )}
        </Card>

        <Card className="flex min-h-[calc(100vh-16rem)] flex-col p-0">
          {!conv ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center text-muted-foreground">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Radio className="h-6 w-6" />
              </div>
              <p className="text-sm">Pick a debtor to start outreach — the live conversation appears here.</p>
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2 border-b p-4 text-xs">
                <span className="font-medium">{conv.customer_id}</span>
                <span className="rounded-full bg-muted px-2 py-0.5">DPD {conv.dpd} · {conv.stage}</span>
                <span className="rounded-full bg-muted px-2 py-0.5">Tone: {conv.tone}</span>
                <span className="rounded-full bg-muted px-2 py-0.5 uppercase">{conv.language}</span>
                {conv.detected_intent && (
                  <span className="rounded-full bg-muted px-2 py-0.5">Intent: {conv.detected_intent}</span>
                )}
                <span className={`ml-auto rounded-full px-2 py-0.5 font-medium ${OUTCOME_STYLE[conv.outcome] ?? "bg-muted"}`}>
                  {conv.outcome}
                </span>
              </div>
              <div className="flex-1 space-y-3 overflow-y-auto p-4">
                {conv.messages.map((m, i) => (
                  <div key={i} className={`flex ${m.direction === "out" ? "" : "justify-end"}`}>
                    <div
                      className={`max-w-[75%] rounded-xl px-3 py-2 text-sm leading-relaxed ${
                        m.direction === "out"
                          ? m.status === "failed"
                            ? "border border-red-300 bg-red-50 text-red-900"
                            : "border bg-card"
                          : "bg-primary text-primary-foreground"
                      }`}
                    >
                      <p className="whitespace-pre-wrap">{m.body}</p>
                      <p className="mt-1 flex items-center gap-1 text-[10px] opacity-60">
                        <MessageSquare className="h-3 w-3" /> {m.channel} · {m.status}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>
      <p className="text-xs text-muted-foreground">
        Bot-initiated · WhatsApp replies drive tone adaptation · SMS/Email are one-way notices. Demo — AI-generated messages.
      </p>
    </div>
  );
}
```

- [ ] **Step 3: Verify the webapp builds**

Run: `cd webapp && npm run build`
Expected: build succeeds, `/outreach` route compiled.

- [ ] **Step 4: Commit**

```bash
git add "webapp/app/(dashboard)/outreach/page.tsx" webapp/components/shell/app-sidebar.tsx
git commit -m "feat(webapp): collections outreach page with live transcript"
```

---

## Self-Review

**Spec coverage check:**
- Bot-initiated outbound → Task 8 `POST /start`. ✓
- WhatsApp two-way + SMS/Email send-only → Task 6 adapter + Task 8 inbound (WhatsApp only). ✓
- DPD tone progression → Task 2 `tones.py`. ✓
- Hostile/hardship adaptation → Task 5 `next_turn` + Task 2 `resolve_tone`/`outcome_for`. ✓
- Bilingual BM/English → Task 5 (language in prompts + tracked on conversation). ✓
- Demo-contacts config (SMS dummy, WhatsApp real) → Task 1. ✓
- Dashboard button + live transcript → Task 11 (SWR 1.5s polling). ✓
- Twilio signature verify + bypass toggle → Task 6 + Task 8 (`VERIFY_TWILIO_SIGNATURE`). ✓
- Gemini fallback on failure → Task 5 (`degraded`, canned replies). ✓
- Idempotency on `MessageSid` → Task 3 `message_exists` + Task 8. ✓
- Unmapped debtor 422 → Task 8. ✓
- SQLite state → Task 3. ✓
- Reads marts, no BQ writes → Task 7 (SELECT only). ✓
- Runbook / tunnel / dry-run → Task 9. ✓
- `.env`/config surface → Task 1. ✓

**Placeholder scan:** No TBD/TODO; every code step has complete content. ✓

**Type consistency:** `CaseFacts` (Task 5) is produced there and consumed by Task 7/8; `Turn` fields (`reply, intent, language, tone, outcome, degraded`) match Task 5 tests and Task 8 usage; `Store` method names match across Tasks 3/8; `TwilioAdapter.send/verify` signatures match Tasks 6/8; proxy paths (`/contacts`, `/start`, `/conversations/{id}`) match Tasks 8/10/11. ✓

**Note on ordering:** Task 7 imports `CaseFacts` from `conversation` (Task 5), so implement Task 5 before Task 7. Tasks are already ordered 1→11 with no forward dependencies otherwise.
