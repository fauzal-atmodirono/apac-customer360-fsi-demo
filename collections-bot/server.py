"""FastAPI app for the collections bot: outbound trigger + inbound webhook + read model."""
from dataclasses import replace
from datetime import date
from fastapi import FastAPI, Request, Response, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import clock
import conversation
import email_template
import ptp
import tones
from config import load_settings, load_contacts


class StartIn(BaseModel):
    customer_id: str
    channel: str = "whatsapp"


class PtpIn(BaseModel):
    customer_id: str
    promise_date: str
    amount: float | None = None
    conversation_id: str | None = None


class PtpUpdateIn(BaseModel):
    status: str | None = None  # KEPT or CANCELLED
    promise_date: str | None = None
    amount: float | None = None


class RestructureIn(BaseModel):
    customer_id: str
    note: str | None = None
    new_installment: float | None = None
    conversation_id: str | None = None


class RestructureUpdateIn(BaseModel):
    status: str | None = None  # ACCEPTED, DECLINED or CANCELLED
    note: str | None = None
    new_installment: float | None = None


def _valid_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def build_app(settings, contacts, store, adapter, lookup, llm_call,
              today_fn=clock.kl_today) -> FastAPI:
    app = FastAPI(title="Bank Muamalat — Collections bot")

    def _auth(x_bot_key: str | None = Header(default=None)):
        if settings.bot_api_key and x_bot_key != settings.bot_api_key:
            raise HTTPException(status_code=401, detail="unauthorized")

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

    # Friendly root so opening the Cloud Run URL in a browser shows a status banner
    # instead of a bare 404 (the API itself has no homepage).
    @app.get("/")
    def root():
        return {
            "service": "Bank Muamalat — Collections bot",
            "status": "ok",
            "endpoints": ["/health", "/start", "/contacts", "/conversations",
                          "/ptps", "/outreach-summary", "/twilio/inbound"],
        }

    # NB: "/healthz" is intercepted by Cloud Run's frontend (returns a Google 404 before
    # reaching the container), so the liveness route is "/health".
    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/contacts", dependencies=[Depends(_auth)])
    def list_contacts():
        return [
            {"customer_id": c.customer_id, "name": c.name, "dpd_stage": c.dpd_stage,
             "channels": _channels(c)}
            for c in contacts.values()
        ]

    @app.post("/start", dependencies=[Depends(_auth)])
    def start(inp: StartIn):
        contact = contacts.get(inp.customer_id)
        if not contact:
            return JSONResponse({"error": f"unknown debtor {inp.customer_id}"}, status_code=422)
        if inp.channel not in ("whatsapp", "sms", "email"):
            return JSONResponse({"error": f"unknown channel {inp.channel}"}, status_code=422)
        # PTP suppression: never chase a debtor whose promise-to-pay is not yet past due.
        # active_ptp_for lazily breaks expired promises, so sends resume the day after.
        active = store.active_ptp_for(inp.customer_id, today_fn())
        if active:
            return JSONResponse(
                {"error": "active promise-to-pay", "reason": "ACTIVE_PTP",
                 "ptp_id": active["id"], "promise_date": active["promise_date"]},
                status_code=409)
        # Restructure suppression: don't chase while a Rekonstruksi offer is on the table.
        restructure = store.active_restructure_for(inp.customer_id)
        if restructure:
            return JSONResponse(
                {"error": "active restructure offer", "reason": "ACTIVE_RESTRUCTURE",
                 "restructure_id": restructure["id"]},
                status_code=409)
        facts = lookup.facts_for(inp.customer_id, contact.name)
        # Demo integrity: when BigQuery has no real case row (default fallback has empty
        # loan_id), trust the contact's configured DPD stage so the badge and the opener tone match.
        if not facts.loan_id:
            facts = replace(facts, stage=contact.dpd_stage)
        opening = conversation.compose_opening(facts, llm_call=llm_call)
        dest = _dest(contact, inp.channel)
        if not dest:
            return JSONResponse({"error": f"debtor {inp.customer_id} has no {inp.channel} destination"}, status_code=422)
        cid = store.create_conversation(
            inp.customer_id, inp.channel, facts.dpd, facts.stage,
            tones.floor_tone(facts.stage), "ms", dest,
        )
        subject, html = "", ""
        if inp.channel == "email":
            subject, html = email_template.render(contact.name, opening, facts)
        try:
            sid, status = adapter.send(inp.channel, dest, opening, subject=subject, html=html)
        except Exception as e:  # noqa: BLE001 - record the failure, surface to UI
            store.add_message(cid, "out", inp.channel, opening, twilio_sid=None, status="failed")
            return JSONResponse({"conversation_id": cid, "send_error": str(e)}, status_code=200)
        store.add_message(cid, "out", inp.channel, opening, twilio_sid=sid, status=status)
        return {"conversation_id": cid}

    @app.get("/conversations", dependencies=[Depends(_auth)])
    def conversations():
        return store.list_conversations()

    @app.get("/ptps", dependencies=[Depends(_auth)])
    def list_ptps(customer_id: str | None = None):
        store.mark_broken_ptps(today_fn())
        return store.list_ptps(customer_id=customer_id)

    @app.post("/ptps", dependencies=[Depends(_auth)])
    def create_ptp(inp: PtpIn):
        if inp.customer_id not in contacts:
            return JSONResponse({"error": f"unknown debtor {inp.customer_id}"}, status_code=422)
        if not _valid_iso_date(inp.promise_date):
            return JSONResponse({"error": f"bad promise_date {inp.promise_date!r} (want YYYY-MM-DD)"},
                                status_code=422)
        active = store.active_ptp_for(inp.customer_id, today_fn())
        if active:
            return JSONResponse({"error": "debtor already has an active promise-to-pay",
                                 "ptp_id": active["id"]}, status_code=409)
        pid = store.create_ptp(inp.customer_id, inp.conversation_id,
                               inp.promise_date, inp.amount, "manual")
        return {"ptp_id": pid}

    @app.post("/ptps/{ptp_id}", dependencies=[Depends(_auth)])
    def update_ptp(ptp_id: str, inp: PtpUpdateIn):
        record = store.get_ptp(ptp_id)
        if not record:
            return JSONResponse({"error": "not found"}, status_code=404)
        if record["status"] != "ACTIVE":
            return JSONResponse({"error": f"ptp is {record['status']}, only ACTIVE can change"},
                                status_code=409)
        fields = {}
        if inp.status is not None:
            if inp.status not in ("KEPT", "CANCELLED"):
                return JSONResponse({"error": "status must be KEPT or CANCELLED"}, status_code=422)
            fields["status"] = inp.status
        if inp.promise_date is not None:
            # Past dates are allowed on purpose: moving the date back is the demo
            # lever for expiring suppression without waiting days.
            if not _valid_iso_date(inp.promise_date):
                return JSONResponse({"error": f"bad promise_date {inp.promise_date!r}"}, status_code=422)
            fields["promise_date"] = inp.promise_date
        if inp.amount is not None:
            fields["amount"] = inp.amount
        if fields:
            store.update_ptp(ptp_id, **fields)
        return {"ptp_id": ptp_id, **store.get_ptp(ptp_id)}

    @app.get("/restructures", dependencies=[Depends(_auth)])
    def list_restructures(customer_id: str | None = None):
        return store.list_restructures(customer_id=customer_id)

    @app.post("/restructures", dependencies=[Depends(_auth)])
    def create_restructure(inp: RestructureIn):
        if inp.customer_id not in contacts:
            return JSONResponse({"error": f"unknown debtor {inp.customer_id}"}, status_code=422)
        if store.active_restructure_for(inp.customer_id):
            return JSONResponse({"error": "debtor already has an active restructure offer"},
                                status_code=409)
        rid = store.create_restructure(inp.customer_id, inp.conversation_id,
                                       inp.note, inp.new_installment, "manual")
        return {"restructure_id": rid}

    @app.post("/restructures/{restructure_id}", dependencies=[Depends(_auth)])
    def update_restructure(restructure_id: str, inp: RestructureUpdateIn):
        record = store.get_restructure(restructure_id)
        if not record:
            return JSONResponse({"error": "not found"}, status_code=404)
        if record["status"] != "ACTIVE":
            return JSONResponse({"error": f"restructure is {record['status']}, only ACTIVE can change"},
                                status_code=409)
        fields = {}
        if inp.status is not None:
            if inp.status not in ("ACCEPTED", "DECLINED", "CANCELLED"):
                return JSONResponse({"error": "status must be ACCEPTED, DECLINED or CANCELLED"},
                                    status_code=422)
            fields["status"] = inp.status
        if inp.note is not None:
            fields["note"] = inp.note
        if inp.new_installment is not None:
            fields["new_installment"] = inp.new_installment
        if fields:
            store.update_restructure(restructure_id, **fields)
        return {"restructure_id": restructure_id, **store.get_restructure(restructure_id)}

    @app.get("/outreach-summary", dependencies=[Depends(_auth)])
    def outreach_summary():
        store.mark_broken_ptps(today_fn())
        summary = store.outreach_summary()
        today = today_fn()
        for cif, row in summary.items():
            row["active_ptp"] = store.active_ptp_for(cif, today)
            row["active_restructure"] = store.active_restructure_for(cif)
        # debtors with a PTP but no conversation yet (manual PTP before first contact)
        for record in store.list_ptps():
            cif = record["customer_id"]
            if record["status"] == "ACTIVE" and cif not in summary:
                summary[cif] = {"contacted": False, "replied": False, "last_contact_at": None,
                                "last_channel": None, "last_intent": None, "last_outcome": None,
                                "active_ptp": record, "active_restructure": None}
        # debtors with a restructure but no conversation yet (manual offer before first contact)
        for record in store.list_restructures():
            cif = record["customer_id"]
            if record["status"] == "ACTIVE" and cif not in summary:
                summary[cif] = {"contacted": False, "replied": False, "last_contact_at": None,
                                "last_channel": None, "last_intent": None, "last_outcome": None,
                                "active_ptp": None, "active_restructure": record}
        return summary

    @app.get("/conversations/{conversation_id}", dependencies=[Depends(_auth)])
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
        if not conv or conv["channel"] != "whatsapp":
            return Response(content="", media_type="application/xml")

        store.add_message(conv["id"], "in", "whatsapp", body, twilio_sid=sid, status="received")
        history = store.get_with_messages(conv["id"])["messages"]
        turn = conversation.next_turn(
            stage=conv["stage"], current_language=conv["language"],
            history=history, inbound_text=body, llm_call=llm_call,
            today=today_fn(),
        )
        try:
            out_sid, out_status = adapter.send("whatsapp", sender, turn.reply)
        except Exception:  # noqa: BLE001
            out_sid, out_status = None, "failed"
        reply_status = "failed" if out_status == "failed" else ("degraded" if turn.degraded else out_status)
        store.add_message(conv["id"], "out", "whatsapp", turn.reply,
                          twilio_sid=out_sid, status=reply_status)
        store.update_conversation(conv["id"], tone=turn.tone, language=turn.language,
                                  detected_intent=turn.intent, outcome=turn.outcome)
        # An AGREE reply is a promise to pay: record it (once) so /start suppresses
        # further chasing until the promised date passes.
        if turn.intent == "AGREE":
            today = today_fn()
            if store.active_ptp_for(conv["customer_id"], today) is None:
                store.create_ptp(conv["customer_id"], conv["id"],
                                 turn.ptp_date or ptp.default_promise_date(today),
                                 turn.ptp_amount, "bot")
        # A HARDSHIP reply triggered a Rekonstruksi offer: record it (once) so /start
        # holds off chasing while the offer is on the table (resolved manually in the UI).
        elif turn.intent == "HARDSHIP":
            if store.active_restructure_for(conv["customer_id"]) is None:
                store.create_restructure(conv["customer_id"], conv["id"], None, None, "bot")
        return Response(content="", media_type="application/xml")

    return app


def _build_default_app() -> FastAPI:
    from dotenv import load_dotenv
    load_dotenv()
    settings = load_settings()
    if settings.contacts_backend == "firestore":
        from firestore_contacts import FirestoreContacts
        contacts = FirestoreContacts(settings.firestore_project, settings.firestore_database)
    else:
        contacts = load_contacts("demo-contacts.json")
    from twilio_adapter import TwilioAdapter
    from case_lookup import CaseLookup
    from llm import Gemini
    if settings.store_backend == "firestore":
        from firestore_store import FirestoreStore
        store = FirestoreStore(settings.firestore_project, settings.firestore_database)
    else:
        from store import Store
        store = Store(settings.conversation_db_path)
    adapter = TwilioAdapter(settings)
    lookup = CaseLookup(settings)
    gemini = Gemini(settings.gemini_model, settings.google_api_key,
                    settings.vertex_project or settings.gcp_project, settings.vertex_location)
    today_fn = (lambda: settings.fake_today) if settings.fake_today else clock.kl_today
    return build_app(settings, contacts, store, adapter, lookup, gemini.generate,
                     today_fn=today_fn)


app = None  # built lazily by uvicorn entrypoint below to avoid import-time env/file reads


def get_app() -> FastAPI:
    global app
    if app is None:
        app = _build_default_app()
    return app
