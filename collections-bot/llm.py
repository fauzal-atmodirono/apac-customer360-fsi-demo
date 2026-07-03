"""Gemini wrapper + tolerant JSON extraction for the collections bot."""
import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


class LLMError(Exception):
    pass


def parse_json_block(text: str) -> dict:
    """Extract the first JSON object from model output (fenced or bare)."""
    if text:
        m = _FENCE_RE.search(text)
        if m:
            return json.loads(m.group(1))
        m = _OBJ_RE.search(text)
        if m:
            return json.loads(m.group(0))
    raise ValueError("no JSON object found in model output")


class Gemini:
    def __init__(self, model: str, api_key: str = ""):
        self._model = model
        self._api_key = api_key
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from google import genai  # imported lazily so tests need no SDK/creds
            # api_key set -> Gemini Developer API; empty -> Vertex via ADC/env.
            self._client = genai.Client(api_key=self._api_key) if self._api_key else genai.Client()
        return self._client

    def generate(self, system: str, user: str) -> str:
        try:
            from google.genai import types
            client = self._ensure_client()
            resp = client.models.generate_content(
                model=self._model,
                contents=user,
                config=types.GenerateContentConfig(system_instruction=system, temperature=0.4),
            )
            return resp.text or ""
        except Exception as e:  # noqa: BLE001 - surface a single wrapped error to the engine
            raise LLMError(str(e)) from e
