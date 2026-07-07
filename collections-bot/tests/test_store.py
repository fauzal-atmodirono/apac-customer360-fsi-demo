from store import Store

def make_store(tmp_path):
    return Store(str(tmp_path / "t.sqlite"))

def test_create_and_get_conversation(tmp_path):
    s = make_store(tmp_path)
    cid = s.create_conversation("001", "whatsapp", 45, "INTENSIVE", "FIRM", "ms", "whatsapp:+60")
    conv = s.get_conversation(cid)
    assert conv["customer_id"] == "001"
    assert conv["stage"] == "INTENSIVE"
    assert conv["outcome"] == "OPENED"
    assert conv["dest"] == "whatsapp:+60"

def test_add_messages_and_get_with_messages(tmp_path):
    s = make_store(tmp_path)
    cid = s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms", "whatsapp:+60")
    s.add_message(cid, "out", "whatsapp", "Salam", twilio_sid="SM1")
    s.add_message(cid, "in", "whatsapp", "ok", twilio_sid="SM2")
    full = s.get_with_messages(cid)
    assert len(full["messages"]) == 2
    assert full["messages"][0]["direction"] == "out"
    assert full["messages"][1]["body"] == "ok"

def test_latest_open_by_dest(tmp_path):
    s = make_store(tmp_path)
    s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms", "whatsapp:+60")
    cid2 = s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms", "whatsapp:+60")
    assert s.latest_open_by_dest("whatsapp:+60")["id"] == cid2
    assert s.latest_open_by_dest("whatsapp:+99") is None

def test_latest_open_by_dest_matches_any_member(tmp_path):
    s = make_store(tmp_path)
    cid = s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms",
                                "whatsapp:+A, whatsapp:+B, whatsapp:+C")
    assert s.latest_open_by_dest("whatsapp:+B")["id"] == cid  # a broadcast member replies
    assert s.latest_open_by_dest("whatsapp:+Z") is None

def test_update_conversation_and_message_exists(tmp_path):
    s = make_store(tmp_path)
    cid = s.create_conversation("001", "whatsapp", 10, "SOFT_REMINDER", "FRIENDLY", "ms", "whatsapp:+60")
    s.update_conversation(cid, detected_intent="HARDSHIP", outcome="RESTRUCTURE_OFFERED", tone="FRIENDLY")
    conv = s.get_conversation(cid)
    assert conv["detected_intent"] == "HARDSHIP"
    assert conv["outcome"] == "RESTRUCTURE_OFFERED"
    s.add_message(cid, "in", "whatsapp", "hi", twilio_sid="SMX")
    assert s.message_exists("SMX") is True
    assert s.message_exists("NOPE") is False


def test_create_and_get_ptp(tmp_path):
    s = make_store(tmp_path)
    pid = s.create_ptp("001", "conv1", "2026-07-10", 500.0, "bot")
    p = s.get_ptp(pid)
    assert p["customer_id"] == "001"
    assert p["conversation_id"] == "conv1"
    assert p["promise_date"] == "2026-07-10"
    assert p["amount"] == 500.0
    assert p["status"] == "ACTIVE"
    assert p["source"] == "bot"
    assert s.get_ptp("missing") is None


def test_list_ptps_filters_by_customer(tmp_path):
    s = make_store(tmp_path)
    s.create_ptp("001", None, "2026-07-10", None, "manual")
    s.create_ptp("002", None, "2026-07-11", 200.0, "bot")
    assert len(s.list_ptps()) == 2
    only = s.list_ptps(customer_id="002")
    assert len(only) == 1
    assert only[0]["customer_id"] == "002"


def test_update_ptp_allowlist(tmp_path):
    s = make_store(tmp_path)
    pid = s.create_ptp("001", None, "2026-07-10", 500.0, "bot")
    s.update_ptp(pid, status="KEPT", promise_date="2026-07-12", amount=250.0, customer_id="HACK")
    p = s.get_ptp(pid)
    assert p["status"] == "KEPT"
    assert p["promise_date"] == "2026-07-12"
    assert p["amount"] == 250.0
    assert p["customer_id"] == "001"  # not in allowlist, unchanged


def test_active_ptp_for_returns_active_future(tmp_path):
    s = make_store(tmp_path)
    pid = s.create_ptp("001", None, "2026-07-10", None, "bot")
    active = s.active_ptp_for("001", today="2026-07-06")
    assert active["id"] == pid
    assert s.active_ptp_for("002", today="2026-07-06") is None


def test_active_ptp_for_lazy_breaks_past_due(tmp_path):
    s = make_store(tmp_path)
    pid = s.create_ptp("001", None, "2026-07-05", None, "bot")
    assert s.active_ptp_for("001", today="2026-07-06") is None
    assert s.get_ptp(pid)["status"] == "BROKEN"  # lazily transitioned on read


def test_active_ptp_for_ignores_settled_statuses(tmp_path):
    s = make_store(tmp_path)
    for status in ("KEPT", "CANCELLED", "BROKEN"):
        pid = s.create_ptp("001", None, "2026-07-10", None, "manual")
        s.update_ptp(pid, status=status)
    assert s.active_ptp_for("001", today="2026-07-06") is None


def test_mark_broken_ptps_sweeps_only_past_due(tmp_path):
    s = make_store(tmp_path)
    past = s.create_ptp("001", None, "2026-07-01", None, "bot")
    future = s.create_ptp("002", None, "2026-07-10", None, "bot")
    kept = s.create_ptp("003", None, "2026-07-01", None, "manual")
    s.update_ptp(kept, status="KEPT")
    assert s.mark_broken_ptps(today="2026-07-06") == 1
    assert s.get_ptp(past)["status"] == "BROKEN"
    assert s.get_ptp(future)["status"] == "ACTIVE"
    assert s.get_ptp(kept)["status"] == "KEPT"


def test_outreach_summary_contacted_and_replied(tmp_path):
    s = make_store(tmp_path)
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


def test_outreach_summary_uses_latest_conversation(tmp_path):
    s = make_store(tmp_path)
    old = s.create_conversation("001", "sms", 45, "INTENSIVE", "FIRM", "ms", "+601")
    s.add_message(old, "out", "sms", "Peringatan", twilio_sid="SM1")
    new = s.create_conversation("001", "whatsapp", 45, "INTENSIVE", "FIRM", "ms", "whatsapp:+60")
    s.add_message(new, "out", "whatsapp", "Salam", twilio_sid="SM2")
    s.update_conversation(new, detected_intent="HARDSHIP", outcome="RESTRUCTURE_OFFERED", tone="FRIENDLY")
    summary = s.outreach_summary()
    assert summary["001"]["last_channel"] == "whatsapp"
    assert summary["001"]["last_outcome"] == "RESTRUCTURE_OFFERED"
