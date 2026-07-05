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
