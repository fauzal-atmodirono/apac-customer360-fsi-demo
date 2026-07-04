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

_ALLOWED_UPDATES = {"tone", "language", "detected_intent", "outcome"}


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
        docs = [d.to_dict() for d in self._convs.where(filter=self._eq("dest", dest)).stream()]
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
