"""Firestore-backed demo contacts, dict-like so it drops into server.py in place of
the JSON-loaded dict (only .get() and .values() are used).

Debtors live in the `contacts` collection of the same Firestore DB as the conversation
store, so they can be edited in the Firebase console and picked up **without a redeploy**.
Reads are cached for a short TTL to avoid a Firestore round-trip per request.
"""
import time

from config import Contact


class FirestoreContacts:
    def __init__(self, project, database="(default)", collection="contacts",
                 ttl=30.0, client=None):
        self._collection = collection
        self._ttl = ttl
        self._cache = None
        self._cache_at = 0.0
        if client is not None:
            self._db = client
        else:
            from google.cloud import firestore
            self._db = firestore.Client(project=project, database=database)

    def _load(self) -> dict:
        out = {}
        for snap in self._db.collection(self._collection).stream():
            d = snap.to_dict() or {}
            cif = d.get("customer_id") or getattr(snap, "id", "")
            if not cif:
                continue
            out[cif] = Contact(
                customer_id=cif, name=d.get("name", ""), dpd_stage=d.get("dpd_stage", ""),
                whatsapp=d.get("whatsapp", ""), sms=d.get("sms", ""), email=d.get("email", ""),
            )
        return out

    def _fresh(self) -> dict:
        now = time.monotonic()
        if self._cache is None or (now - self._cache_at) > self._ttl:
            self._cache = self._load()
            self._cache_at = now
        return self._cache

    # dict-like surface used by server.py
    def get(self, customer_id):
        return self._fresh().get(customer_id)

    def values(self):
        return self._fresh().values()

    def __contains__(self, customer_id):
        return customer_id in self._fresh()

    def __getitem__(self, customer_id):
        return self._fresh()[customer_id]
