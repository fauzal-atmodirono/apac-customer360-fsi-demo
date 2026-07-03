import pytest
from conversation import (
    CaseFacts, compose_opening, next_turn, build_opening_prompt,
)
from llm import LLMError

FACTS = CaseFacts(stage="INTENSIVE", dpd=45, outstanding=3200.0, loan_id="LN9", name="Encik Ahmad")

def test_build_opening_prompt_includes_case_facts_and_tone():
    system, user = build_opening_prompt(FACTS, default_language="ms")
    assert "3200" in user or "3,200" in user
    assert "45" in user
    assert "Encik Ahmad" in user
    assert "FIRM" in system  # INTENSIVE floor tone name surfaced to the model

def test_compose_opening_uses_llm_when_available():
    out = compose_opening(FACTS, llm_call=lambda s, u: "Salam Encik Ahmad, sila jelaskan bayaran.")
    assert "Ahmad" in out

def test_compose_opening_falls_back_on_llm_error():
    def boom(s, u):
        raise LLMError("down")
    out = compose_opening(FACTS, llm_call=boom)
    assert "Bank Muamalat" in out  # canned INTENSIVE opening

def test_next_turn_hardship_offers_restructure():
    def fake(s, u):
        return '{"intent":"HARDSHIP","language":"ms","reply":"Kami boleh tawarkan penstrukturan semula."}'
    turn = next_turn(stage="INTENSIVE", current_language="ms", history=[],
                     inbound_text="saya tengah susah", llm_call=fake)
    assert turn.intent == "HARDSHIP"
    assert turn.outcome == "RESTRUCTURE_OFFERED"
    assert turn.tone == "FIRM"        # floor held, not softened
    assert turn.degraded is False

def test_next_turn_hostile_escalates_tone():
    def fake(s, u):
        return '{"intent":"HOSTILE","language":"en","reply":"This is a formal notice."}'
    turn = next_turn(stage="SOFT_REMINDER", current_language="ms", history=[],
                     inbound_text="I will not pay", llm_call=fake)
    assert turn.intent == "HOSTILE"
    assert turn.outcome == "HOSTILE_ESCALATED"
    assert turn.tone == "FIRM"        # bumped one sterner from FRIENDLY floor
    assert turn.language == "en"      # switched to the debtor's language

def test_next_turn_falls_back_on_bad_output():
    def bad(s, u):
        return "not json at all"
    turn = next_turn(stage="RECOVERY_LEGAL", current_language="ms", history=[],
                     inbound_text="???", llm_call=bad)
    assert turn.degraded is True
    assert turn.intent == "OTHER"
    assert turn.reply == __import__("tones").CANNED_REPLY["RECOVERY_LEGAL"]
