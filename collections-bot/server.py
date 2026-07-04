"""FastAPI app for the collections bot: outbound trigger + inbound webhook + read model."""
from dataclasses import replace
from fastapi import FastAPI, Request, Response, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import conversation
import tones
from config import load_settings, load_contacts


class StartIn(BaseModel):
    customer_id: str
    channel: str = "whatsapp"


def build_app(settings, contacts, store, adapter, lookup, llm_call) -> FastAPI:
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

    @app.get("/healthz")
    def healthz():
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
        try:
            sid, status = adapter.send(inp.channel, dest, opening)
        except Exception as e:  # noqa: BLE001 - record the failure, surface to UI
            store.add_message(cid, "out", inp.channel, opening, twilio_sid=None, status="failed")
            return JSONResponse({"conversation_id": cid, "send_error": str(e)}, status_code=200)
        store.add_message(cid, "out", inp.channel, opening, twilio_sid=sid, status=status)
        return {"conversation_id": cid}

    @app.get("/conversations", dependencies=[Depends(_auth)])
    def conversations():
        return store.list_conversations()

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
        return Response(content="", media_type="application/xml")

    return app


def _build_default_app() -> FastAPI:
    from dotenv import load_dotenv
    load_dotenv()
    settings = load_settings()
    contacts = load_contacts("demo-contacts.json")
    from store import Store
    from twilio_adapter import TwilioAdapter
    from case_lookup import CaseLookup
    from llm import Gemini
    store = Store(settings.conversation_db_path)
    adapter = TwilioAdapter(settings)
    lookup = CaseLookup(settings)
    gemini = Gemini(settings.gemini_model, settings.google_api_key, settings.gcp_project, settings.vertex_location)
    return build_app(settings, contacts, store, adapter, lookup, gemini.generate)


app = None  # built lazily by uvicorn entrypoint below to avoid import-time env/file reads


def get_app() -> FastAPI:
    global app
    if app is None:
        app = _build_default_app()
    return app
