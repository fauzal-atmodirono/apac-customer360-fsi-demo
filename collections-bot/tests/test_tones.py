import tones

def test_stage_for_dpd_boundaries():
    assert tones.stage_for_dpd(0) == "SOFT_REMINDER"
    assert tones.stage_for_dpd(30) == "SOFT_REMINDER"
    assert tones.stage_for_dpd(31) == "INTENSIVE"
    assert tones.stage_for_dpd(60) == "INTENSIVE"
    assert tones.stage_for_dpd(61) == "FIELD_VISIT"
    assert tones.stage_for_dpd(90) == "FIELD_VISIT"
    assert tones.stage_for_dpd(91) == "RECOVERY_LEGAL"
    assert tones.stage_for_dpd(120) == "RECOVERY_LEGAL"

def test_floor_tone_per_stage():
    assert tones.floor_tone("SOFT_REMINDER") == "FRIENDLY"
    assert tones.floor_tone("INTENSIVE") == "FIRM"
    assert tones.floor_tone("FIELD_VISIT") == "ASSERTIVE"
    assert tones.floor_tone("RECOVERY_LEGAL") == "LEGAL"

def test_resolve_tone_never_below_floor():
    # AGREE keeps the floor even at a late stage (no de-escalation to friendly).
    assert tones.resolve_tone("FIELD_VISIT", "AGREE") == "ASSERTIVE"
    # HOSTILE bumps one sterner from the floor...
    assert tones.resolve_tone("SOFT_REMINDER", "HOSTILE") == "FIRM"
    # ...but is capped at LEGAL.
    assert tones.resolve_tone("RECOVERY_LEGAL", "HOSTILE") == "LEGAL"
    # HARDSHIP stays at the floor (empathy layered on, tone not softened).
    assert tones.resolve_tone("INTENSIVE", "HARDSHIP") == "FIRM"

def test_outcome_for_intent():
    assert tones.outcome_for("AGREE") == "PTP_OBTAINED"
    assert tones.outcome_for("HARDSHIP") == "RESTRUCTURE_OFFERED"
    assert tones.outcome_for("HOSTILE") == "HOSTILE_ESCALATED"
    assert tones.outcome_for("OTHER") == "OPENED"
