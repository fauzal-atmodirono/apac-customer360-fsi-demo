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
        # A conversation's dest may be a comma-list (message broadcast to several numbers);
        # match if `dest` (the inbound sender) is any one of them.
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM conversations ORDER BY started_at DESC, rowid DESC"
            ).fetchall()
        for r in rows:
            if dest in [d.strip() for d in (r["dest"] or "").split(",")]:
                return dict(r)
        return None

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
