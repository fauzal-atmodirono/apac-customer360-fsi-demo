"""FirestoreStore tests against an in-memory fake client.

The fake mimics the subset of the google-cloud-firestore API the store uses:
collection().document().set/get/update, and collection().where(filter=FieldFilter)
.limit().stream(). It reads FieldFilter's public field_path/op_string/value.
"""
import firestore_store
from firestore_store import FirestoreStore


def _monotonic_now(monkeypatch):
    """Feed strictly increasing timestamps so order-by-started_at is deterministic
    (avoids same-microsecond ties on fast back-to-back creates)."""
    seq = iter(f"2026-07-04T00:00:{i:02d}+00:00" for i in range(60))
    monkeypatch.setattr(firestore_store, "_now", lambda: next(seq))


class _Snap:
    def __init__(self, data):
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class _DocRef:
    def __init__(self, docs, doc_id):
        self._docs = docs
        self._id = doc_id

    def set(self, data):
        self._docs[self._id] = dict(data)

    def get(self):
        return _Snap(self._docs.get(self._id))

    def update(self, data):
        self._docs.setdefault(self._id, {}).update(data)


class _Query:
    def __init__(self, docs, filters=None, limit=None):
        self._docs = docs
        self._filters = filters or []
        self._limit = limit

    def where(self, filter=None):
        f = (filter.field_path, filter.op_string, filter.value)
        return _Query(self._docs, self._filters + [f], self._limit)

    def limit(self, n):
        return _Query(self._docs, self._filters, n)

    def stream(self):
        out = [_Snap(d) for d in self._docs.values()
               if all(op == "==" and d.get(field) == val for field, op, val in self._filters)]
        return iter(out[:self._limit] if self._limit is not None else out)


class _Collection(_Query):
    def document(self, doc_id):
        return _DocRef(self._docs, doc_id)


class FakeFirestore:
    def __init__(self):
        self._collections = {}

    def collection(self, name):
        return _Collection(self._collections.setdefault(name, {}))


def make_store():
    return FirestoreStore(project="p", database="d", client=FakeFirestore())


def test_create_and_get_conversation():
    s = make_store()
    cid = s.create_conversation("001", "whatsapp", 45, "INTENSIVE", "FIRM", "ms", "whatsapp:+60")
    conv = s.get_conversation(cid)
    assert conv["customer_id"] == "001"
    assert conv["stage"] == "INTENSIVE"
    assert conv["outcome"] == "OPENED"
    assert conv["dest"] == "whatsapp:+60"
    assert s.get_conversation("missing") is None


def test_add_messages_and_get_with_messages():
    s = make_store()
    cid = s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms", "whatsapp:+60")
    s.add_message(cid, "out", "whatsapp", "Salam", twilio_sid="SM1")
    s.add_message(cid, "in", "whatsapp", "ok", twilio_sid="SM2")
    full = s.get_with_messages(cid)
    assert len(full["messages"]) == 2
    assert full["messages"][0]["direction"] == "out"
    assert full["messages"][1]["body"] == "ok"
    assert s.get_with_messages("missing") is None


def test_latest_open_by_dest(monkeypatch):
    _monotonic_now(monkeypatch)
    s = make_store()
    s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms", "whatsapp:+60")
    cid2 = s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms", "whatsapp:+60")
    assert s.latest_open_by_dest("whatsapp:+60")["id"] == cid2
    assert s.latest_open_by_dest("whatsapp:+99") is None


def test_update_conversation_and_message_exists():
    s = make_store()
    cid = s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms", "whatsapp:+60")
    s.update_conversation(cid, detected_intent="HARDSHIP", outcome="RESTRUCTURE_OFFERED", tone="FRIENDLY")
    conv = s.get_conversation(cid)
    assert conv["detected_intent"] == "HARDSHIP"
    assert conv["outcome"] == "RESTRUCTURE_OFFERED"
    s.add_message(cid, "in", "whatsapp", "hi", twilio_sid="SMX")
    assert s.message_exists("SMX") is True
    assert s.message_exists("NOPE") is False
    assert s.message_exists(None) is False


def test_update_ignores_unknown_fields():
    s = make_store()
    cid = s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms", "whatsapp:+60")
    s.update_conversation(cid, customer_id="HACK", dpd=999)  # not in allowlist
    conv = s.get_conversation(cid)
    assert conv["customer_id"] == "001"
    assert conv["dpd"] == 10


def test_list_conversations_newest_first(monkeypatch):
    _monotonic_now(monkeypatch)
    s = make_store()
    s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms", "whatsapp:+60")
    c2 = s.create_conversation("002", "sms", 40, "INTENSIVE", "FIRM", "en", "+601")
    rows = s.list_conversations()
    assert len(rows) == 2
    assert rows[0]["id"] == c2  # newest first
