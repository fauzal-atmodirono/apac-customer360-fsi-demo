"""Gemini wrapper + tolerant JSON extraction for the collections bot."""
import json
import logging
import re
import time

logger = logging.getLogger(__name__)

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
    def __init__(self, model: str, api_key: str = "", project: str = "", location: str = "global",
                 client=None, max_attempts: int = 3, backoff: float = 0.6):
        self._model = model
        self._api_key = api_key
        self._project = project
        self._location = location
        self._client = client  # injectable for tests / pre-built client
        self._max_attempts = max(1, max_attempts)
        self._backoff = backoff

    def _ensure_client(self):
        if self._client is None:
            from google import genai  # lazy so tests need no SDK/creds
            if self._api_key:
                self._client = genai.Client(api_key=self._api_key)
            else:
                self._client = genai.Client(vertexai=True, project=self._project, location=self._location)
        return self._client

    def generate(self, system: str, user: str) -> str:
        """Call Gemini, retrying transient failures (timeouts, 5xx, empty replies).

        A single blip previously degraded the whole turn — dropping, e.g., a
        debtor's stated promise-to-pay date. Retry with linear backoff so a
        transient failure doesn't silently lose the classification.
        """
        from google.genai import types
        client = self._ensure_client()
        last_err: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                resp = client.models.generate_content(
                    model=self._model,
                    contents=user,
                    config=types.GenerateContentConfig(system_instruction=system, temperature=0.4),
                )
                text = (resp.text or "").strip()
                if not text:
                    raise ValueError("empty response from model")
                return text
            except Exception as e:  # noqa: BLE001 - any SDK error is a retryable transient
                last_err = e
                logger.warning("Gemini generate attempt %d/%d failed: %r",
                               attempt, self._max_attempts, e)
                if attempt < self._max_attempts:
                    time.sleep(self._backoff * attempt)
        raise LLMError(str(last_err)) from last_err
