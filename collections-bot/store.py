"""SQLite-backed conversation + message store for the collections bot."""
import sqlite3
import uuid
from datetime import datetime, timezone

_ALLOWED_UPDATES = {"tone", "language", "detected_intent", "outcome"}
_ALLOWED_PTP_UPDATES = {"promise_date", "amount", "status"}
_ALLOWED_RESTRUCTURE_UPDATES = {"note", "new_installment", "status"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rollup(convs: list[dict], agg: dict[str, dict]) -> dict[str, dict]:
    """Fold per-conversation message aggregates into a per-customer contact summary.

    `convs` must be sorted oldest->newest so the latest conversation's channel/
    intent/outcome win. Shared by both store backends (FirestoreStore imports it).
    """
    out: dict[str, dict] = {}
    for conv in convs:
        cur = out.setdefault(conv["customer_id"], {
            "contacted": False, "replied": False, "last_contact_at": None,
            "last_channel": None, "last_intent": None, "last_outcome": None,
        })
        a = agg.get(conv["id"])
        if a:
            cur["contacted"] = cur["contacted"] or bool(a["outs"])
            cur["replied"] = cur["replied"] or bool(a["ins"])
            ts = a.get("last_ts")
            if ts and (cur["last_contact_at"] is None or ts > cur["last_contact_at"]):
                cur["last_contact_at"] = ts
        cur["last_channel"] = conv["channel"]
        cur["last_intent"] = conv.get("detected_intent")
        cur["last_outcome"] = conv.get("outcome")
    return out


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
            c.execute("""
                CREATE TABLE IF NOT EXISTS ptps (
                    id TEXT PRIMARY KEY, customer_id TEXT, conversation_id TEXT,
                    promise_date TEXT, amount REAL, status TEXT, source TEXT,
                    created_at TEXT, updated_at TEXT
                )""")
            c.execute("""
                CREATE TABLE IF NOT EXISTS restructures (
                    id TEXT PRIMARY KEY, customer_id TEXT, conversation_id TEXT,
                    note TEXT, new_installment REAL, status TEXT, source TEXT,
                    created_at TEXT, updated_at TEXT
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

    # --- promise-to-pay (PTP) -----------------------------------------------

    def create_ptp(self, customer_id, conversation_id, promise_date, amount, source) -> str:
        pid = uuid.uuid4().hex
        ts = _now()
        with self._conn() as c:
            c.execute(
                """INSERT INTO ptps
                   (id, customer_id, conversation_id, promise_date, amount,
                    status, source, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (pid, customer_id, conversation_id, promise_date, amount,
                 "ACTIVE", source, ts, ts),
            )
        return pid

    def get_ptp(self, ptp_id) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM ptps WHERE id=?", (ptp_id,)).fetchone()
        return dict(row) if row else None

    def list_ptps(self, customer_id=None) -> list[dict]:
        sql = "SELECT * FROM ptps"
        args: tuple = ()
        if customer_id:
            sql += " WHERE customer_id=?"
            args = (customer_id,)
        sql += " ORDER BY created_at DESC, rowid DESC"
        with self._conn() as c:
            rows = c.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def update_ptp(self, ptp_id, **fields) -> None:
        cols = {k: v for k, v in fields.items() if k in _ALLOWED_PTP_UPDATES}
        if not cols:
            return
        assignments = ", ".join(f"{k}=?" for k in cols)
        with self._conn() as c:
            c.execute(
                f"UPDATE ptps SET {assignments}, updated_at=? WHERE id=?",
                (*cols.values(), _now(), ptp_id),
            )

    def mark_broken_ptps(self, today) -> int:
        # Lazy sweep: an ACTIVE promise whose date has passed becomes BROKEN.
        with self._conn() as c:
            cur = c.execute(
                "UPDATE ptps SET status='BROKEN', updated_at=? "
                "WHERE status='ACTIVE' AND promise_date < ?",
                (_now(), today),
            )
            return cur.rowcount

    def active_ptp_for(self, customer_id, today) -> dict | None:
        self.mark_broken_ptps(today)
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM ptps WHERE customer_id=? AND status='ACTIVE' "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (customer_id,),
            ).fetchone()
        return dict(row) if row else None

    # --- restructure (Rekonstruksi) records ----------------------------------
    # A restructure offer suppresses outbound reminders while ACTIVE. Unlike a PTP
    # it has no due date, so it never lazily expires — a collections officer resolves
    # it via the workbench (ACCEPTED / DECLINED / CANCELLED).

    def create_restructure(self, customer_id, conversation_id, note, new_installment, source) -> str:
        rid = uuid.uuid4().hex
        ts = _now()
        with self._conn() as c:
            c.execute(
                """INSERT INTO restructures
                   (id, customer_id, conversation_id, note, new_installment,
                    status, source, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (rid, customer_id, conversation_id, note, new_installment,
                 "ACTIVE", source, ts, ts),
            )
        return rid

    def get_restructure(self, restructure_id) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM restructures WHERE id=?", (restructure_id,)).fetchone()
        return dict(row) if row else None

    def list_restructures(self, customer_id=None) -> list[dict]:
        sql = "SELECT * FROM restructures"
        args: tuple = ()
        if customer_id:
            sql += " WHERE customer_id=?"
            args = (customer_id,)
        sql += " ORDER BY created_at DESC, rowid DESC"
        with self._conn() as c:
            rows = c.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def update_restructure(self, restructure_id, **fields) -> None:
        cols = {k: v for k, v in fields.items() if k in _ALLOWED_RESTRUCTURE_UPDATES}
        if not cols:
            return
        assignments = ", ".join(f"{k}=?" for k in cols)
        with self._conn() as c:
            c.execute(
                f"UPDATE restructures SET {assignments}, updated_at=? WHERE id=?",
                (*cols.values(), _now(), restructure_id),
            )

    def active_restructure_for(self, customer_id) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM restructures WHERE customer_id=? AND status='ACTIVE' "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (customer_id,),
            ).fetchone()
        return dict(row) if row else None

    # --- per-debtor outreach rollup -------------------------------------------

    def outreach_summary(self) -> dict[str, dict]:
        """Per-CIF contact status: keyed by customer_id, only debtors with conversations."""
        with self._conn() as c:
            convs = [dict(r) for r in c.execute(
                "SELECT * FROM conversations ORDER BY started_at ASC, rowid ASC").fetchall()]
            rows = c.execute(
                """SELECT conversation_id,
                          SUM(direction='out') AS outs,
                          SUM(direction='in') AS ins,
                          MAX(ts) AS last_ts
                   FROM messages GROUP BY conversation_id""").fetchall()
        agg = {r["conversation_id"]: dict(r) for r in rows}
        return _rollup(convs, agg)
