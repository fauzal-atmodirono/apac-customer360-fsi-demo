"""Firestore-backed conversation + message store.

A drop-in replacement for store.Store (same method signatures / return shapes)
so the bot can run multi-instance on Cloud Run — Firestore is serverless and
concurrency-safe, unlike the single-file SQLite store. The database may live in
a *different* GCP project than the one the bot runs in; pass ``project`` +
``database`` explicitly (the runtime SA just needs roles/datastore.user there).

Queries use equality filters only and sort in memory, so no composite indexes
are required in the target project (fine at demo volumes).
"""
import uuid
from datetime import datetime, timezone

from store import _rollup

_ALLOWED_UPDATES = {"tone", "language", "detected_intent", "outcome"}
_ALLOWED_PTP_UPDATES = {"promise_date", "amount", "status"}
_ALLOWED_RESTRUCTURE_UPDATES = {"note", "new_installment", "status"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FirestoreStore:
    def __init__(self, project: str, database: str = "(default)", client=None):
        if client is not None:
            self._db = client
        else:
            from google.cloud import firestore
            self._db = firestore.Client(project=project, database=database)
        self._convs = self._db.collection("conversations")
        self._msgs = self._db.collection("messages")
        self._ptps = self._db.collection("ptps")
        self._restructures = self._db.collection("restructures")

    @staticmethod
    def _eq(field: str, value):
        from google.cloud.firestore_v1.base_query import FieldFilter
        return FieldFilter(field, "==", value)

    def create_conversation(self, customer_id, channel, dpd, stage, tone, language, dest) -> str:
        cid = uuid.uuid4().hex
        ts = _now()
        self._convs.document(cid).set({
            "id": cid, "customer_id": customer_id, "channel": channel,
            "dpd": dpd, "stage": stage, "tone": tone, "language": language,
            "detected_intent": None, "outcome": "OPENED", "dest": dest,
            "started_at": ts, "updated_at": ts,
        })
        return cid

    def add_message(self, conversation_id, direction, channel, body,
                    twilio_sid=None, status="sent") -> None:
        mid = uuid.uuid4().hex
        self._msgs.document(mid).set({
            "id": mid, "conversation_id": conversation_id, "direction": direction,
            "channel": channel, "body": body, "twilio_sid": twilio_sid,
            "status": status, "ts": _now(),
        })

    def get_conversation(self, conversation_id) -> dict | None:
        snap = self._convs.document(conversation_id).get()
        return snap.to_dict() if snap.exists else None

    def latest_open_by_dest(self, dest) -> dict | None:
        # A conversation's dest may be a comma-list (message broadcast to several numbers);
        # match if `dest` (the inbound sender) is any one of them. Load + filter in memory
        # (demo volumes) since Firestore can't substring-match.
        docs = []
        for snap in self._convs.stream():
            d = snap.to_dict()
            if dest in [x.strip() for x in (d.get("dest") or "").split(",")]:
                docs.append(d)
        if not docs:
            return None
        docs.sort(key=lambda d: d.get("started_at") or "", reverse=True)
        return docs[0]

    def update_conversation(self, conversation_id, **fields) -> None:
        cols = {k: v for k, v in fields.items() if k in _ALLOWED_UPDATES}
        if not cols:
            return
        cols["updated_at"] = _now()
        self._convs.document(conversation_id).update(cols)

    def message_exists(self, twilio_sid) -> bool:
        if not twilio_sid:
            return False
        docs = list(self._msgs.where(filter=self._eq("twilio_sid", twilio_sid)).limit(1).stream())
        return len(docs) > 0

    def list_conversations(self) -> list[dict]:
        docs = [d.to_dict() for d in self._convs.stream()]
        docs.sort(key=lambda d: d.get("started_at") or "", reverse=True)
        return docs

    def get_with_messages(self, conversation_id) -> dict | None:
        conv = self.get_conversation(conversation_id)
        if not conv:
            return None
        msgs = [d.to_dict() for d in
                self._msgs.where(filter=self._eq("conversation_id", conversation_id)).stream()]
        msgs.sort(key=lambda m: m.get("ts") or "")
        conv["messages"] = msgs
        return conv

    # --- promise-to-pay (PTP) -----------------------------------------------

    def create_ptp(self, customer_id, conversation_id, promise_date, amount, source) -> str:
        pid = uuid.uuid4().hex
        ts = _now()
        self._ptps.document(pid).set({
            "id": pid, "customer_id": customer_id, "conversation_id": conversation_id,
            "promise_date": promise_date, "amount": amount,
            "status": "ACTIVE", "source": source, "created_at": ts, "updated_at": ts,
        })
        return pid

    def get_ptp(self, ptp_id) -> dict | None:
        snap = self._ptps.document(ptp_id).get()
        return snap.to_dict() if snap.exists else None

    def list_ptps(self, customer_id=None) -> list[dict]:
        if customer_id:
            q = self._ptps.where(filter=self._eq("customer_id", customer_id))
        else:
            q = self._ptps
        docs = [d.to_dict() for d in q.stream()]
        docs.sort(key=lambda d: d.get("created_at") or "", reverse=True)
        return docs

    def update_ptp(self, ptp_id, **fields) -> None:
        cols = {k: v for k, v in fields.items() if k in _ALLOWED_PTP_UPDATES}
        if not cols:
            return
        cols["updated_at"] = _now()
        self._ptps.document(ptp_id).update(cols)

    def mark_broken_ptps(self, today) -> int:
        # Lazy sweep: an ACTIVE promise whose date has passed becomes BROKEN.
        # Idempotent, so a race between Cloud Run instances is harmless.
        count = 0
        for snap in self._ptps.where(filter=self._eq("status", "ACTIVE")).stream():
            d = snap.to_dict()
            if (d.get("promise_date") or "") < today:
                self._ptps.document(d["id"]).update({"status": "BROKEN", "updated_at": _now()})
                count += 1
        return count

    def active_ptp_for(self, customer_id, today) -> dict | None:
        self.mark_broken_ptps(today)
        docs = [d.to_dict() for d in
                self._ptps.where(filter=self._eq("customer_id", customer_id)).stream()]
        active = [d for d in docs if d.get("status") == "ACTIVE"]
        if not active:
            return None
        active.sort(key=lambda d: d.get("created_at") or "", reverse=True)
        return active[0]

    def paid_to_date(self, customer_id) -> float:
        # Demo overlay: total actually paid = sum of KEPT promise amounts (NULLs skipped).
        docs = [d.to_dict() for d in
                self._ptps.where(filter=self._eq("customer_id", customer_id)).stream()]
        return float(sum(d.get("amount") or 0 for d in docs if d.get("status") == "KEPT"))

    # --- restructure (Rekonstruksi) records ----------------------------------
    # Suppresses reminders while ACTIVE; no due date, so no lazy expiry (resolved
    # manually via the workbench). Mirrors store.Store for a drop-in swap.

    def create_restructure(self, customer_id, conversation_id, note, new_installment, source) -> str:
        rid = uuid.uuid4().hex
        ts = _now()
        self._restructures.document(rid).set({
            "id": rid, "customer_id": customer_id, "conversation_id": conversation_id,
            "note": note, "new_installment": new_installment,
            "status": "ACTIVE", "source": source, "created_at": ts, "updated_at": ts,
        })
        return rid

    def get_restructure(self, restructure_id) -> dict | None:
        snap = self._restructures.document(restructure_id).get()
        return snap.to_dict() if snap.exists else None

    def list_restructures(self, customer_id=None) -> list[dict]:
        if customer_id:
            q = self._restructures.where(filter=self._eq("customer_id", customer_id))
        else:
            q = self._restructures
        docs = [d.to_dict() for d in q.stream()]
        docs.sort(key=lambda d: d.get("created_at") or "", reverse=True)
        return docs

    def update_restructure(self, restructure_id, **fields) -> None:
        cols = {k: v for k, v in fields.items() if k in _ALLOWED_RESTRUCTURE_UPDATES}
        if not cols:
            return
        cols["updated_at"] = _now()
        self._restructures.document(restructure_id).update(cols)

    def active_restructure_for(self, customer_id) -> dict | None:
        docs = [d.to_dict() for d in
                self._restructures.where(filter=self._eq("customer_id", customer_id)).stream()]
        active = [d for d in docs if d.get("status") == "ACTIVE"]
        if not active:
            return None
        active.sort(key=lambda d: d.get("created_at") or "", reverse=True)
        return active[0]

    # --- per-debtor outreach rollup -------------------------------------------

    def outreach_summary(self) -> dict[str, dict]:
        """Per-CIF contact status. Streams both collections and groups in memory
        (demo volumes, same trade-off as latest_open_by_dest)."""
        convs = [d.to_dict() for d in self._convs.stream()]
        convs.sort(key=lambda d: d.get("started_at") or "")
        agg: dict[str, dict] = {}
        for m in (d.to_dict() for d in self._msgs.stream()):
            a = agg.setdefault(m["conversation_id"], {"outs": 0, "ins": 0, "last_ts": None})
            if m.get("direction") == "out":
                a["outs"] += 1
            elif m.get("direction") == "in":
                a["ins"] += 1
            ts = m.get("ts")
            if ts and (a["last_ts"] is None or ts > a["last_ts"]):
                a["last_ts"] = ts
        return _rollup(convs, agg)
