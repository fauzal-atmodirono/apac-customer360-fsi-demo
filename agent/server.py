"""FastAPI wrapper exposing the ADK 'Ask the data' agent as a simple /chat endpoint
for the Next.js webapp. Runs the ADK Runner and returns {answer, sql, chart, rows, session_id}."""
import json
import re
import uuid

from fastapi import FastAPI
from pydantic import BaseModel
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent import root_agent

APP_NAME = "c360-ask"

app = FastAPI(title="Customer 360 — Ask the data agent")
_sessions = InMemorySessionService()
_runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=_sessions)
_known: set[str] = set()

# Matches the ```chart { ... } ``` block the agent appends to its answer.
_CHART_RE = re.compile(r"```chart\s*(\{.*?\})\s*```", re.DOTALL)


class ChatIn(BaseModel):
    message: str
    session_id: str | None = None


def _extract_rows(resp):
    """Pull the result rows out of the BigQuery execute_sql tool response (shape varies)."""
    if isinstance(resp, list):
        return resp if resp and isinstance(resp[0], dict) else None
    if isinstance(resp, dict):
        for key in ("rows", "result", "results", "data"):
            v = resp.get(key)
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
        # Fallback: first list-of-dicts value anywhere in the response.
        for v in resp.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return None


def _extract_chart(text: str):
    """Split a ```chart {json}``` block off the answer → (clean_text, spec|None)."""
    m = _CHART_RE.search(text or "")
    if not m:
        return (text or "").strip(), None
    spec = None
    try:
        spec = json.loads(m.group(1))
    except Exception:
        spec = None
    cleaned = ((text[:m.start()] + text[m.end():]) if text else "").strip()
    return cleaned, spec


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/chat")
async def chat(inp: ChatIn):
    session_id = inp.session_id or uuid.uuid4().hex
    user_id = "webapp"
    if session_id not in _known:
        await _sessions.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
        _known.add(session_id)

    content = types.Content(role="user", parts=[types.Part(text=inp.message)])
    answer, sql, rows = "", None, None
    async for event in _runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        for part in (event.content.parts if event.content and event.content.parts else []):
            fc = getattr(part, "function_call", None)
            if fc and fc.name and "sql" in fc.name.lower():
                q = (fc.args or {}).get("query")
                if q:
                    sql = q
            fr = getattr(part, "function_response", None)
            if fr and fr.name and "sql" in fr.name.lower():
                extracted = _extract_rows(getattr(fr, "response", None))
                if extracted:
                    rows = extracted
        if event.is_final_response() and event.content and event.content.parts:
            answer = "".join(p.text or "" for p in event.content.parts)

    answer, chart = _extract_chart(answer)
    return {"answer": answer, "sql": sql, "chart": chart, "rows": rows or [], "session_id": session_id}
