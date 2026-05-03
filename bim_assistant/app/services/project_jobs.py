"""
In-memory pipeline job state for /api/projects/*/process async flow.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.ingestion.pipeline import run_ingestion_pipeline
from app.storage.database import get_session
from app.storage.repository import save_building_model

logger = logging.getLogger(__name__)

_lock = asyncio.Lock()
_jobs: dict[str, dict[str, Any]] = {}


async def merge_job(project_id: str, **fields: Any) -> None:
    async with _lock:
        cur = dict(_jobs.get(project_id, {}))
        cur.update(fields)
        _jobs[project_id] = cur


async def get_job(project_id: str) -> dict[str, Any]:
    async with _lock:
        return dict(_jobs.get(project_id, {}))


async def execute_pipeline_job(project_id: str) -> None:
    settings = get_settings()
    await merge_job(project_id, status="processing", error=None)

    upload_dir = Path(settings.upload_dir) / project_id
    if not upload_dir.exists():
        await merge_job(project_id, status="failed", error="Upload not found.")
        return

    candidates = list(upload_dir.iterdir())
    if not candidates:
        await merge_job(project_id, status="failed", error="Upload directory empty.")
        return

    input_path = candidates[0]

    try:
        model = await run_ingestion_pipeline(input_path, project_id=project_id)
        async with get_session() as session:
            await save_building_model(model, session)

        processed_path = Path(settings.processed_dir) / f"{project_id}.json"
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        processed_path.write_text(model.model_dump_json(indent=2))

        await merge_job(
            project_id,
            status="completed",
            element_count=model.element_count,
            error=None,
        )
        logger.info("Pipeline completed project_id=%s elements=%s", project_id, model.element_count)
    except Exception as exc:
        logger.exception("Pipeline failed project_id=%s", project_id)
        await merge_job(project_id, status="failed", error=str(exc))


def processed_json_path(project_id: str) -> Path:
    return Path(get_settings().processed_dir) / f"{project_id}.json"


def upload_root(project_id: str) -> Path:
    return Path(get_settings().upload_dir) / project_id


async def resolve_pipeline_status(project_id: str) -> dict[str, Any]:
    settings = get_settings()
    job = await get_job(project_id)

    upload_dir = Path(settings.upload_dir) / project_id
    if not upload_dir.exists():
        return {}

    status = job.get("status")
    if status in ("queued", "processing", "failed"):
        out = {"status": status, "project_id": project_id}
        if job.get("error"):
            out["error"] = job["error"]
        if job.get("element_count") is not None:
            out["element_count"] = job["element_count"]
        return out

    if status == "completed":
        out = {"status": "completed", "project_id": project_id}
        if job.get("element_count") is not None:
            out["element_count"] = job["element_count"]
        return out

    proc = processed_json_path(project_id)
    if proc.exists():
        return {"status": "completed", "project_id": project_id}

    return {"status": "idle", "project_id": project_id}
