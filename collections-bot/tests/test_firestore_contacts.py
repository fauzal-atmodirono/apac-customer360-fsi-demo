"""FirestoreContacts tests against an in-memory fake client (dict-like + caching)."""
from firestore_contacts import FirestoreContacts


class _Snap:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    def to_dict(self):
        return dict(self._data)


class _Collection:
    def __init__(self, docs):
        self._docs = docs

    def stream(self):
        return iter(_Snap(k, v) for k, v in self._docs.items())


class FakeFirestore:
    def __init__(self, docs):
        self._docs = docs

    def collection(self, name):
        return _Collection(self._docs)


CONTACTS = {
    "001": {"customer_id": "001", "name": "Encik Ahmad", "dpd_stage": "SOFT_REMINDER",
            "whatsapp": "whatsapp:+60A", "sms": "+60A", "email": "a@x.com"},
    "002": {"customer_id": "002", "name": "Puan Siti", "dpd_stage": "INTENSIVE",
            "whatsapp": "whatsapp:+60B", "sms": "+60B", "email": "b@x.com"},
}


def make(docs=None):
    return FirestoreContacts(project="p", database="d", client=FakeFirestore(docs if docs is not None else dict(CONTACTS)))


def test_get_and_values():
    c = make()
    assert c.get("001").name == "Encik Ahmad"
    assert c.get("002").dpd_stage == "INTENSIVE"
    assert c.get("999") is None
    assert {x.customer_id for x in c.values()} == {"001", "002"}
    assert "001" in c and "999" not in c


def test_derives_id_from_doc_when_field_missing():
    docs = {"077": {"name": "No CIF Field", "dpd_stage": "FIELD_VISIT", "whatsapp": "w"}}
    c = make(docs)
    assert c.get("077").name == "No CIF Field"
    assert c.get("077").customer_id == "077"


def test_ttl_cache_avoids_reload_then_refreshes():
    docs = dict(CONTACTS)
    c = FirestoreContacts(project="p", database="d", ttl=999, client=FakeFirestore(docs))
    assert c.get("001") is not None
    docs.pop("001")  # mutate underlying store
    assert c.get("001") is not None  # still cached (long TTL)
    c._ttl = 0  # force expiry
    assert c.get("001") is None  # reloaded, reflects the change
