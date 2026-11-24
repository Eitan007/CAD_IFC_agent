"""
app/observability.py
OpenTelemetry / OpenInference tracing for the LLM agent.

Emits one OTLP span per Anthropic `messages.create` call (via OpenInference's
AnthropicInstrumentor) plus one manual child span per deterministic tool
dispatch, all nested under a root "agent.run" span (see app/agent/agent.py).
That gives a full agent trace: query -> plan (LLM spans) -> tool calls
(tool spans) -> answer.

Spans are always written as OTLP-shaped JSON Lines to
`data/traces/traces.jsonl` (one span per line) so a trace file exists with
zero external services. Set OTEL_EXPORTER_OTLP_ENDPOINT to also ship spans
to a real collector (Phoenix, Jaeger, LangSmith-compatible OTLP receiver, …).
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

TRACE_FILE = Path(os.getenv("TRACE_LOG_PATH", "./data/traces/traces.jsonl"))

_configured = False
_lock = threading.Lock()


class JSONLFileExporter(SpanExporter):
    """Writes each finished span as one OTLP-shaped JSON line to disk."""

    def __init__(self, path: Path):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file_lock = threading.Lock()

    def export(self, spans) -> SpanExportResult:
        with self._file_lock, self._path.open("a") as f:
            for span in spans:
                f.write(json.dumps(_span_to_dict(span), default=str) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


def _span_to_dict(span: ReadableSpan) -> dict:
    ctx = span.get_span_context()
    parent = span.parent
    return {
        "name": span.name,
        "trace_id": format(ctx.trace_id, "032x"),
        "span_id": format(ctx.span_id, "016x"),
        "parent_span_id": format(parent.span_id, "016x") if parent else None,
        "start_time": span.start_time,
        "end_time": span.end_time,
        "status": span.status.status_code.name,
        "attributes": dict(span.attributes or {}),
        "events": [
            {"name": e.name, "attributes": dict(e.attributes or {}), "timestamp": e.timestamp}
            for e in span.events
        ],
    }


def configure_tracing() -> None:
    """Idempotently set up the OTel tracer provider + Anthropic auto-instrumentation."""
    global _configured
    with _lock:
        if _configured:
            return

        provider = TracerProvider(
            resource=Resource.create({"service.name": "bim-assistant-agent"})
        )
        provider.add_span_processor(SimpleSpanProcessor(JSONLFileExporter(TRACE_FILE)))

        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

        from app.integrations.agent_eval_exporter import AgentEvalSpanExporter
        provider.add_span_processor(
            BatchSpanProcessor(AgentEvalSpanExporter(), schedule_delay_millis=1000)
        )

        trace.set_tracer_provider(provider)

        from openinference.instrumentation.anthropic import AnthropicInstrumentor
        AnthropicInstrumentor().instrument(tracer_provider=provider)

        _configured = True


def get_tracer():
    return trace.get_tracer("bim_assistant.agent")
