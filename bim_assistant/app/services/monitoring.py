"""Read the local trace log into safe, dashboard-friendly monitoring data."""
from __future__ import annotations

import json
from collections import Counter
from typing import Any

from app.observability import TRACE_FILE


def _duration_ms(span: dict[str, Any]) -> float:
    start = span.get("start_time")
    end = span.get("end_time")
    if not isinstance(start, int) or not isinstance(end, int) or end < start:
        return 0.0
    return round((end - start) / 1_000_000, 1)


def _read_spans(limit: int = 500) -> list[dict[str, Any]]:
    if not TRACE_FILE.is_file():
        return []
    spans: list[dict[str, Any]] = []
    try:
        with TRACE_FILE.open(encoding="utf-8") as trace_file:
            for line in trace_file:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    spans.append(item)
    except OSError:
        return []
    return spans[-limit:]


def monitoring_summary() -> dict[str, Any]:
    """Summarise actual recorded traces; no made-up scores are returned."""
    spans = _read_spans()
    runs = [span for span in spans if span.get("name") == "agent.run"]
    errors = [span for span in runs if span.get("status") == "ERROR"]
    durations = [_duration_ms(span) for span in runs]
    tool_count = sum(1 for span in spans if str(span.get("name", "")).startswith("tool."))

    recent_runs: list[dict[str, Any]] = []
    for span in reversed(runs[-12:]):
        attrs = span.get("attributes") or {}
        recent_runs.append(
            {
                "trace_id": span.get("trace_id"),
                "query": str(attrs.get("bim.query", ""))[:160],
                "source_format": attrs.get("bim.source_format", "unknown"),
                "duration_ms": _duration_ms(span),
                "status": span.get("status", "UNSET"),
                "tool_calls": int(attrs.get("bim.tool_call_count", 0) or 0),
            }
        )

    formats = Counter(
        str((span.get("attributes") or {}).get("bim.source_format", "unknown"))
        for span in runs
    )
    return {
        "agent_runs": len(runs),
        "failed_runs": len(errors),
        "error_rate": round((len(errors) / len(runs) * 100) if runs else 0.0, 1),
        "average_duration_ms": round(sum(durations) / len(durations), 1) if durations else 0.0,
        "tool_calls": tool_count,
        "formats": dict(formats),
        "recent_runs": recent_runs,
    }
