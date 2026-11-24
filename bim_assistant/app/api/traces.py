"""
app/api/traces.py
GET /traces — download the recorded agent trace log (OTLP-shaped JSON Lines,
one span per line: agent.run root spans, per-iteration LLM spans, per-tool
spans) for evaluation or upload into an external trace-eval tool.
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from app.observability import TRACE_FILE

router = APIRouter()


@router.get("")
async def get_traces():
    """Download the full trace log as newline-delimited JSON spans."""
    if not TRACE_FILE.exists():
        return JSONResponse({"spans": []})
    return FileResponse(TRACE_FILE, media_type="application/x-ndjson", filename="traces.jsonl")
