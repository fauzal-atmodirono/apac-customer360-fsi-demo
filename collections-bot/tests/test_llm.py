import pytest
from llm import parse_json_block

def test_parse_plain_json():
    assert parse_json_block('{"intent": "AGREE", "language": "en", "reply": "ok"}')["intent"] == "AGREE"

def test_parse_fenced_json_with_prose():
    raw = 'Sure!\n```json\n{"intent": "HARDSHIP", "language": "ms", "reply": "baik"}\n```\nthanks'
    out = parse_json_block(raw)
    assert out["intent"] == "HARDSHIP"
    assert out["reply"] == "baik"

def test_parse_raises_when_no_json():
    with pytest.raises(ValueError):
        parse_json_block("no json here")
