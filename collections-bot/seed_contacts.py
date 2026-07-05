"""Seed the Firestore `contacts` collection from demo-contacts.json (one-off).

    ./.venv/bin/python seed_contacts.py            # upsert all contacts
    ./.venv/bin/python seed_contacts.py --prune    # also delete contacts not in the JSON

Writes to FIRESTORE_PROJECT / FIRESTORE_DATABASE (the same DB as the conversation store).
After seeding, set CONTACTS_BACKEND=firestore and redeploy once; later edits are
Firebase-console changes with no redeploy.
"""
import json
import sys

from dotenv import load_dotenv

from config import load_settings


def main() -> None:
    load_dotenv()
    s = load_settings()
    from google.cloud import firestore

    db = firestore.Client(project=s.firestore_project, database=s.firestore_database)
    col = db.collection("contacts")

    with open("demo-contacts.json") as f:
        raw = json.load(f)

    for cif, v in raw.items():
        col.document(cif).set({"customer_id": cif, **v})
        print(f"  seeded {cif}  {v.get('name')}")

    if "--prune" in sys.argv:
        keep = set(raw)
        for snap in col.stream():
            if snap.id not in keep:
                col.document(snap.id).delete()
                print(f"  pruned {snap.id}")

    print(f"done: {len(raw)} contacts -> {s.firestore_project}/{s.firestore_database}/contacts")


if __name__ == "__main__":
    main()
