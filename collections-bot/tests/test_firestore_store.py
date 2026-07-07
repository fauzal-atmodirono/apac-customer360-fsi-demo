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


def test_latest_open_by_dest_matches_any_member():
    s = make_store()
    cid = s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms",
                                "whatsapp:+A, whatsapp:+B, whatsapp:+C")
    assert s.latest_open_by_dest("whatsapp:+B")["id"] == cid
    assert s.latest_open_by_dest("whatsapp:+Z") is None

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


def test_create_and_get_ptp():
    s = make_store()
    pid = s.create_ptp("001", "conv1", "2026-07-10", 500.0, "bot")
    p = s.get_ptp(pid)
    assert p["customer_id"] == "001"
    assert p["conversation_id"] == "conv1"
    assert p["promise_date"] == "2026-07-10"
    assert p["amount"] == 500.0
    assert p["status"] == "ACTIVE"
    assert p["source"] == "bot"
    assert s.get_ptp("missing") is None


def test_list_ptps_filters_by_customer():
    s = make_store()
    s.create_ptp("001", None, "2026-07-10", None, "manual")
    s.create_ptp("002", None, "2026-07-11", 200.0, "bot")
    assert len(s.list_ptps()) == 2
    only = s.list_ptps(customer_id="002")
    assert len(only) == 1
    assert only[0]["customer_id"] == "002"


def test_update_ptp_allowlist():
    s = make_store()
    pid = s.create_ptp("001", None, "2026-07-10", 500.0, "bot")
    s.update_ptp(pid, status="KEPT", promise_date="2026-07-12", amount=250.0, customer_id="HACK")
    p = s.get_ptp(pid)
    assert p["status"] == "KEPT"
    assert p["promise_date"] == "2026-07-12"
    assert p["amount"] == 250.0
    assert p["customer_id"] == "001"  # not in allowlist, unchanged


def test_active_ptp_for_returns_active_future():
    s = make_store()
    pid = s.create_ptp("001", None, "2026-07-10", None, "bot")
    active = s.active_ptp_for("001", today="2026-07-06")
    assert active["id"] == pid
    assert s.active_ptp_for("002", today="2026-07-06") is None


def test_active_ptp_for_lazy_breaks_past_due():
    s = make_store()
    pid = s.create_ptp("001", None, "2026-07-05", None, "bot")
    assert s.active_ptp_for("001", today="2026-07-06") is None
    assert s.get_ptp(pid)["status"] == "BROKEN"  # lazily transitioned on read


def test_active_ptp_for_ignores_settled_statuses():
    s = make_store()
    for status in ("KEPT", "CANCELLED", "BROKEN"):
        pid = s.create_ptp("001", None, "2026-07-10", None, "manual")
        s.update_ptp(pid, status=status)
    assert s.active_ptp_for("001", today="2026-07-06") is None


def test_mark_broken_ptps_sweeps_only_past_due():
    s = make_store()
    past = s.create_ptp("001", None, "2026-07-01", None, "bot")
    future = s.create_ptp("002", None, "2026-07-10", None, "bot")
    kept = s.create_ptp("003", None, "2026-07-01", None, "manual")
    s.update_ptp(kept, status="KEPT")
    assert s.mark_broken_ptps(today="2026-07-06") == 1
    assert s.get_ptp(past)["status"] == "BROKEN"
    assert s.get_ptp(future)["status"] == "ACTIVE"
    assert s.get_ptp(kept)["status"] == "KEPT"


def test_outreach_summary_contacted_and_replied(monkeypatch):
    _monotonic_now(monkeypatch)
    s = make_store()
    cid = s.create_conversation("001", "whatsapp", 45, "INTENSIVE", "FIRM", "ms", "whatsapp:+60")
    s.add_message(cid, "out", "whatsapp", "Salam", twilio_sid="SM1")
    s.add_message(cid, "in", "whatsapp", "ok saya bayar", twilio_sid="SM2")
    s.update_conversation(cid, detected_intent="AGREE", outcome="PTP_OBTAINED", tone="FRIENDLY")
    cid2 = s.create_conversation("002", "sms", 10, "SOFT_REMINDER", "FRIENDLY", "ms", "+601")
    s.add_message(cid2, "out", "sms", "Peringatan", twilio_sid="SM3")
    summary = s.outreach_summary()
    assert summary["001"]["contacted"] is True
    assert summary["001"]["replied"] is True
    assert summary["001"]["last_channel"] == "whatsapp"
    assert summary["001"]["last_intent"] == "AGREE"
    assert summary["001"]["last_outcome"] == "PTP_OBTAINED"
    assert summary["001"]["last_contact_at"] is not None
    assert summary["002"]["contacted"] is True
    assert summary["002"]["replied"] is False
    assert "003" not in summary  # never contacted


def test_outreach_summary_uses_latest_conversation(monkeypatch):
    _monotonic_now(monkeypatch)
    s = make_store()
    old = s.create_conversation("001", "sms", 45, "INTENSIVE", "FIRM", "ms", "+601")
    s.add_message(old, "out", "sms", "Peringatan", twilio_sid="SM1")
    new = s.create_conversation("001", "whatsapp", 45, "INTENSIVE", "FIRM", "ms", "whatsapp:+60")
    s.add_message(new, "out", "whatsapp", "Salam", twilio_sid="SM2")
    s.update_conversation(new, detected_intent="HARDSHIP", outcome="RESTRUCTURE_OFFERED", tone="FRIENDLY")
    summary = s.outreach_summary()
    assert summary["001"]["last_channel"] == "whatsapp"
    assert summary["001"]["last_outcome"] == "RESTRUCTURE_OFFERED"


# --- restructure (Rekonstruksi) records ------------------------------------

def test_create_and_get_restructure():
    s = make_store()
    rid = s.create_restructure("001", "conv1", "Reduce installment to RM300 x 12", 300.0, "bot")
    r = s.get_restructure(rid)
    assert r["customer_id"] == "001"
    assert r["conversation_id"] == "conv1"
    assert r["note"] == "Reduce installment to RM300 x 12"
    assert r["new_installment"] == 300.0
    assert r["status"] == "ACTIVE"
    assert r["source"] == "bot"
    assert s.get_restructure("missing") is None


def test_list_restructures_filters_by_customer():
    s = make_store()
    s.create_restructure("001", None, None, None, "manual")
    s.create_restructure("002", None, "note", 200.0, "bot")
    assert len(s.list_restructures()) == 2
    only = s.list_restructures(customer_id="002")
    assert len(only) == 1
    assert only[0]["customer_id"] == "002"


def test_update_restructure_allowlist():
    s = make_store()
    rid = s.create_restructure("001", None, "old", 400.0, "bot")
    s.update_restructure(rid, status="ACCEPTED", note="new plan", new_installment=250.0, customer_id="HACK")
    r = s.get_restructure(rid)
    assert r["status"] == "ACCEPTED"
    assert r["note"] == "new plan"
    assert r["new_installment"] == 250.0
    assert r["customer_id"] == "001"  # not in allowlist, unchanged


def test_active_restructure_for_returns_active():
    s = make_store()
    rid = s.create_restructure("001", None, None, None, "bot")
    active = s.active_restructure_for("001")
    assert active["id"] == rid
    assert s.active_restructure_for("002") is None


def test_active_restructure_for_ignores_settled():
    s = make_store()
    for status in ("ACCEPTED", "DECLINED", "CANCELLED"):
        rid = s.create_restructure("001", None, None, None, "manual")
        s.update_restructure(rid, status=status)
    assert s.active_restructure_for("001") is None


# --- demo payment overlay (paid-to-date from KEPT PTPs) ---------------------

def test_paid_to_date_sums_kept_amounts():
    s = make_store()
    p1 = s.create_ptp("001", None, "2026-07-10", 1000.0, "bot"); s.update_ptp(p1, status="KEPT")
    p2 = s.create_ptp("001", None, "2026-07-20", 2000.0, "manual"); s.update_ptp(p2, status="KEPT")
    assert s.paid_to_date("001") == 3000.0


def test_paid_to_date_ignores_non_kept_and_null_amounts():
    s = make_store()
    kept = s.create_ptp("001", None, "2026-07-10", 500.0, "bot"); s.update_ptp(kept, status="KEPT")
    s.create_ptp("001", None, "2026-07-11", 999.0, "bot")                                  # ACTIVE — ignored
    nullamt = s.create_ptp("001", None, "2026-07-12", None, "bot"); s.update_ptp(nullamt, status="KEPT")
    assert s.paid_to_date("001") == 500.0


def test_paid_to_date_zero_when_no_kept():
    s = make_store()
    assert s.paid_to_date("001") == 0.0
