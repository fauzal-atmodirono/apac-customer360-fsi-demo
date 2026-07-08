import pytest
from llm import parse_json_block, Gemini, LLMError

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


class _FakeResp:
    def __init__(self, text):
        self.text = text

class _FakeClient:
    """Stands in for genai.Client; `behaviors` is a per-call list of either an
    Exception to raise or a string to return as resp.text."""
    def __init__(self, behaviors):
        self._behaviors = list(behaviors)
        self.calls = 0
        self.models = self  # so client.models.generate_content(...) resolves here

    def generate_content(self, **kwargs):
        self.calls += 1
        b = self._behaviors.pop(0)
        if isinstance(b, Exception):
            raise b
        return _FakeResp(b)


def test_generate_retries_transient_failure_then_succeeds():
    client = _FakeClient([RuntimeError("503 transient"), '{"intent":"AGREE"}'])
    g = Gemini("m", client=client, max_attempts=3, backoff=0)
    assert g.generate("sys", "user") == '{"intent":"AGREE"}'
    assert client.calls == 2  # first failed, retried, second succeeded

def test_generate_raises_llmerror_after_exhausting_retries():
    client = _FakeClient([RuntimeError("boom")] * 3)
    g = Gemini("m", client=client, max_attempts=3, backoff=0)
    with pytest.raises(LLMError):
        g.generate("sys", "user")
    assert client.calls == 3

def test_generate_retries_empty_response():
    # An empty/whitespace response is a transient failure mode worth retrying,
    # not a valid answer to hand to the JSON parser.
    client = _FakeClient(["", "   ", '{"intent":"OTHER"}'])
    g = Gemini("m", client=client, max_attempts=3, backoff=0)
    assert g.generate("sys", "user") == '{"intent":"OTHER"}'
    assert client.calls == 3
