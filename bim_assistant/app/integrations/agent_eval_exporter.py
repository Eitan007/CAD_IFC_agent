"""
app/integrations/agent_eval_exporter.py
Pushes finished agent traces into the separate AGENT_EVAL app in real time.

AGENT_EVAL ("LLM Eval Studio", a sibling project) exposes an `agent_trace`
evaluation type at POST /api/v1/datasets + POST /api/v1/runs. Each dataset
item must be shaped {"trace": {"spans": [...]}}. Dataset creation doesn't
validate item shape; run creation validates trace.spans is a list, per item,
via the plugin resolved from the dataset's evaluation_type.

NOTE: AGENT_EVAL's current scorer (FakeEvaluationEngine) is a stub that
hardcodes all 5 agent_trace metrics to 1.0 regardless of span content — this
exporter's job is correct plumbing (real traces, right shape, pushed live),
not meaningful scores. Real scoring is a separate follow-up in AGENT_EVAL.

This SpanExporter buffers spans by trace_id — export() runs on the
BatchSpanProcessor's own worker thread, so a blocking HTTP call here is
safe and never blocks the FastAPI event loop handling the user's /query
request (which has already returned by the time a push happens). When the
root "agent.run" span for a trace_id is seen, the whole trace is complete:
build one dataset + one run and push them, then drop the buffer for that
trace_id.
"""
from __future__ import annotations

import logging
import os
import threading
import uuid
from typing import Any

import requests
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from app.observability import _span_to_dict

logger = logging.getLogger(__name__)

AGENT_EVAL_URL = os.getenv("AGENT_EVAL_URL", "http://localhost:8000")
ENABLE_AGENT_EVAL_PUSH = os.getenv("ENABLE_AGENT_EVAL_PUSH", "true").lower() == "true"
_REQUEST_TIMEOUT = 5.0


def _span_to_eval_dict(span: ReadableSpan) -> dict[str, Any]:
    d = _span_to_dict(span)
    duration_ms = None
    if d["start_time"] and d["end_time"]:
        duration_ms = (d["end_time"] - d["start_time"]) / 1_000_000
    return {
        "name": d["name"],
        "duration_ms": duration_ms,
        "status": "error" if d["status"] == "ERROR" else "ok",
        "attributes": d["attributes"],
    }


class AgentEvalSpanExporter(SpanExporter):
    """Buffers spans per trace; on trace completion, pushes a dataset+run to AGENT_EVAL."""

    def __init__(self, agent_eval_url: str = AGENT_EVAL_URL, enabled: bool = ENABLE_AGENT_EVAL_PUSH):
        self._agent_eval_url = agent_eval_url.rstrip("/")
        self._enabled = enabled
        self._lock = threading.Lock()
        self._buffers: dict[str, list[dict]] = {}

    def export(self, spans) -> SpanExportResult:
        if not self._enabled:
            return SpanExportResult.SUCCESS

        for span in spans:
            trace_id = format(span.get_span_context().trace_id, "032x")

            with self._lock:
                self._buffers.setdefault(trace_id, []).append(_span_to_eval_dict(span))

            if span.name == "agent.run" and span.parent is None:
                self._flush_trace(trace_id, span)

        return SpanExportResult.SUCCESS

    def _flush_trace(self, trace_id: str, root_span: ReadableSpan) -> None:
        with self._lock:
            spans = self._buffers.pop(trace_id, [])

        root_attrs = dict(root_span.attributes or {})
        dataset_id = f"bim-assistant-{trace_id}-{uuid.uuid4().hex[:8]}"
        dataset_payload = {
            "id": dataset_id,
            "name": f"bim_assistant trace {trace_id[:12]}",
            "evaluation_type": "agent_trace",
            "description": "Auto-pushed from bim_assistant's live agent trace",
            "metadata": {"source": "bim_assistant", "trace_id": trace_id},
            "items": [
                {
                    "id": trace_id,
                    "input_data": {"trace": {"spans": spans}},
                    "expected_output": None,
                    "metadata": {
                        "project_id": root_attrs.get("bim.project_id"),
                        "query": root_attrs.get("bim.query"),
                        "answer": root_attrs.get("bim.answer"),
                    },
                }
            ],
        }

        try:
            resp = requests.post(
                f"{self._agent_eval_url}/api/v1/datasets",
                json=dataset_payload,
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()

            run_resp = requests.post(
                f"{self._agent_eval_url}/api/v1/runs",
                json={"dataset_id": dataset_id, "config": {"provider": "bim-assistant"}},
                timeout=_REQUEST_TIMEOUT,
            )
            run_resp.raise_for_status()
            logger.info(
                "Pushed trace %s to AGENT_EVAL as dataset %s (run status: %s)",
                trace_id, dataset_id, run_resp.json().get("status"),
            )
        except requests.RequestException as exc:
            logger.warning(
                "Failed to push trace %s to AGENT_EVAL at %s: %s", trace_id, self._agent_eval_url, exc
            )

    def shutdown(self) -> None:
        pass
