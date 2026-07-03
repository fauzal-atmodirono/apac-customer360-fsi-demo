"""Pure DPD -> stage -> tone -> outcome logic. No I/O. Single source of truth for
the collections tone state machine (see spec section 4)."""

STAGES = ["SOFT_REMINDER", "INTENSIVE", "FIELD_VISIT", "RECOVERY_LEGAL"]
INTENTS = ["AGREE", "HOSTILE", "HARDSHIP", "OTHER"]
TONE_ORDER = ["FRIENDLY", "FIRM", "ASSERTIVE", "LEGAL"]

_FLOOR = {
    "SOFT_REMINDER": "FRIENDLY",
    "INTENSIVE": "FIRM",
    "FIELD_VISIT": "ASSERTIVE",
    "RECOVERY_LEGAL": "LEGAL",
}

_TONE_GUIDANCE = {
    "FRIENDLY": "Friendly, polite and helpful ('bot manis'). A gentle nudge, warm and respectful.",
    "FIRM": "Neutral, firm and persistent. Warn plainly about accumulating arrears and the credit-score impact.",
    "ASSERTIVE": "Assertive and authoritative. Serious; urge immediate action and warn of escalation.",
    "LEGAL": "Direct and authoritative ('agak keras'). State the legal-warning / field-visit escalation clearly and formally.",
}

_OUTCOME = {
    "AGREE": "PTP_OBTAINED",
    "HARDSHIP": "RESTRUCTURE_OFFERED",
    "HOSTILE": "HOSTILE_ESCALATED",
    "OTHER": "OPENED",
}

CANNED_OPENING = {
    "SOFT_REMINDER": "Salam, ini peringatan mesra daripada Bank Muamalat berkenaan bayaran pembiayaan anda yang telah tertunggak. Sila buat pembayaran secepat mungkin. Terima kasih.",
    "INTENSIVE": "Salam daripada Bank Muamalat. Bayaran pembiayaan anda kini tertunggak dan jumlah tunggakan semakin meningkat. Ini boleh menjejaskan rekod kredit anda. Sila jelaskan bayaran segera.",
    "FIELD_VISIT": "Notis daripada Bank Muamalat: akaun pembiayaan anda tertunggak dengan serius. Sila hubungi kami dan buat bayaran segera untuk mengelakkan tindakan lanjut.",
    "RECOVERY_LEGAL": "Notis rasmi Bank Muamalat: akaun anda kini di peringkat pemulihan. Kegagalan menjelaskan tunggakan boleh membawa kepada tindakan undang-undang atau lawatan penagihan. Sila hubungi kami dengan segera.",
}

CANNED_REPLY = {
    "SOFT_REMINDER": "Terima kasih atas maklum balas anda. Sila hubungi kami jika anda memerlukan bantuan untuk pembayaran.",
    "INTENSIVE": "Kami memahami. Sila jelaskan tunggakan anda secepat mungkin bagi mengelakkan kesan kepada rekod kredit anda.",
    "FIELD_VISIT": "Sila ambil tindakan segera untuk menjelaskan tunggakan bagi mengelakkan tindakan lanjut.",
    "RECOVERY_LEGAL": "Akaun anda memerlukan penyelesaian segera. Sila hubungi kami untuk mengelakkan tindakan undang-undang.",
}


def stage_for_dpd(dpd: int) -> str:
    if dpd <= 30:
        return "SOFT_REMINDER"
    if dpd <= 60:
        return "INTENSIVE"
    if dpd <= 90:
        return "FIELD_VISIT"
    return "RECOVERY_LEGAL"


def floor_tone(stage: str) -> str:
    return _FLOOR[stage]


def resolve_tone(stage: str, intent: str) -> str:
    floor = floor_tone(stage)
    if intent == "HOSTILE":
        idx = min(TONE_ORDER.index(floor) + 1, len(TONE_ORDER) - 1)
        return TONE_ORDER[idx]
    return floor


def outcome_for(intent: str) -> str:
    return _OUTCOME.get(intent, "OPENED")


def tone_guidance(tone: str) -> str:
    return _TONE_GUIDANCE[tone]
