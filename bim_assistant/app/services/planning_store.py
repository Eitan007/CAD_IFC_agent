"""
JSON-backed store for construction planning context (site reality, actuals).
Avoids DB migrations; optional Neo4j/Postgres extension later.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_CONTEXT: dict[str, Any] = {
    "actual_progress": {},
    "site_notes": [],
    "location": {"label": "", "lat": None, "lon": None},
    "baseline_task_snapshot": None,
}


def _path(project_id: str) -> Path:
    settings = get_settings()
    root = Path(settings.planning_data_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{project_id}.json"


def load_context(project_id: str) -> dict[str, Any]:
    p = _path(project_id)
    if not p.exists():
        return json.loads(json.dumps(DEFAULT_CONTEXT))
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        out = {**DEFAULT_CONTEXT, **data}
        if not isinstance(out.get("actual_progress"), dict):
            out["actual_progress"] = {}
        if not isinstance(out.get("site_notes"), list):
            out["site_notes"] = []
        if not isinstance(out.get("location"), dict):
            out["location"] = {"label": "", "lat": None, "lon": None}
        return out
    except Exception as exc:
        logger.warning("Failed to load planning context for %s: %s", project_id, exc)
        return json.loads(json.dumps(DEFAULT_CONTEXT))


def save_context(project_id: str, data: dict[str, Any]) -> None:
    p = _path(project_id)
    merged = {**load_context(project_id), **data}
    p.write_text(json.dumps(merged, indent=2), encoding="utf-8")
