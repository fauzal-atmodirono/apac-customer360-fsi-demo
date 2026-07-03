"""Conversation engine: compose the DPD-toned opening and adapt to each reply.

Pure orchestration around an injected `llm_call(system, user) -> str`, so it is
fully testable with a fake callable (no network)."""
from dataclasses import dataclass

import tones
from llm import LLMError, parse_json_block


@dataclass(frozen=True)
class CaseFacts:
    stage: str
    dpd: int
    outstanding: float
    loan_id: str
    name: str


@dataclass(frozen=True)
class Turn:
    reply: str
    intent: str
    language: str
    tone: str
    outcome: str
    degraded: bool


_LANG_NAME = {"ms": "Bahasa Malaysia", "en": "English"}


def build_opening_prompt(facts: CaseFacts, default_language: str) -> tuple[str, str]:
    tone = tones.floor_tone(facts.stage)
    system = (
        "You are an outbound collections assistant for Bank Muamalat, a Malaysian Islamic bank. "
        f"Write ONE short outreach message (2-4 sentences). Tone: {tone}. {tones.tone_guidance(tone)} "
        f"Write in {_LANG_NAME.get(default_language, 'Bahasa Malaysia')}. "
        "This is Islamic financing: never mention interest or penalty interest. "
        "Do not invent figures beyond those provided. Output only the message text, no preamble."
    )
    user = (
        f"Debtor name: {facts.name}\n"
        f"Financing account: {facts.loan_id}\n"
        f"Days past due (DPD): {facts.dpd}\n"
        f"Outstanding arrears: RM {facts.outstanding:,.2f}\n"
        f"Collections stage: {facts.stage}\n"
        "Write the opening reminder message now."
    )
    return system, user


def compose_opening(facts: CaseFacts, llm_call, default_language: str = "ms") -> str:
    system, user = build_opening_prompt(facts, default_language)
    try:
        text = llm_call(system, user).strip()
        return text or tones.CANNED_OPENING[facts.stage]
    except LLMError:
        return tones.CANNED_OPENING[facts.stage]


def build_reply_prompt(stage: str, current_language: str, history: list, inbound_text: str) -> tuple[str, str]:
    floor = tones.floor_tone(stage)
    convo = "\n".join(f"{m['direction']}: {m['body']}" for m in history)
    system = (
        "You are an outbound collections assistant for Bank Muamalat (Malaysian Islamic bank). "
        "Classify the debtor's latest reply and draft the next message. "
        "Reply ONLY with a JSON object: "
        '{"intent": one of ["AGREE","HOSTILE","HARDSHIP","OTHER"], '
        '"language": "ms" or "en" (match the debtor\'s language), '
        '"reply": the message text to send back}. '
        f"Base tone floor for this stage ({stage}) is {floor} — never be softer than this floor. "
        "If intent is HOSTILE, be sterner, official and firm about consequences (legal warning / field visit). "
        "If intent is HARDSHIP, be empathetic and OFFER restructuring ('Rekonstruksi'): "
        "waive or reduce charges (no interest — this is Islamic financing), adjust the payment plan, "
        "or extend installments. If intent is AGREE, thank them and give clear payment guidance. "
        "Keep the reply to 2-4 sentences."
    )
    user = (
        f"Conversation so far:\n{convo}\n\n"
        f"Debtor's latest reply: {inbound_text}\n"
        f"Current language: {current_language}\n"
        "Return the JSON now."
    )
    return system, user


def next_turn(*, stage: str, current_language: str, history: list, inbound_text: str, llm_call) -> Turn:
    system, user = build_reply_prompt(stage, current_language, history, inbound_text)
    try:
        parsed = parse_json_block(llm_call(system, user))
        intent = parsed.get("intent", "OTHER")
        if intent not in tones.INTENTS:
            intent = "OTHER"
        language = parsed.get("language", current_language)
        if language not in ("ms", "en"):
            language = current_language
        reply = (parsed.get("reply") or "").strip()
        if not reply:
            raise ValueError("empty reply")
        return Turn(
            reply=reply, intent=intent, language=language,
            tone=tones.resolve_tone(stage, intent), outcome=tones.outcome_for(intent),
            degraded=False,
        )
    except (LLMError, ValueError):
        return Turn(
            reply=tones.CANNED_REPLY[stage], intent="OTHER", language=current_language,
            tone=tones.floor_tone(stage), outcome="OPENED", degraded=True,
        )
