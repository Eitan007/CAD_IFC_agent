"""
In-memory pipeline job state for /api/projects/*/process async flow.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.ingestion.ifc_to_glb import project_glb_path, run_ifc_glb_export
from app.ingestion.pipeline import run_ingestion_pipeline
from app.storage.database import get_session
from app.storage.repository import save_building_model

logger = logging.getLogger(__name__)

SAMPLE_PROJECT_ID = "sample-basichouse"

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


async def _export_glb_background(project_id: str, input_path: Path) -> None:
    """Optional server-side GLB; does not block chat or IFC viewer."""
    settings = get_settings()
    if input_path.suffix.lower() != ".ifc":
        return
    glb_path = project_glb_path(Path(settings.processed_dir), project_id)
    try:
        await run_ifc_glb_export(input_path, glb_path)
        await merge_job(project_id, glb_ready=True)
        logger.info("GLB ready (background) project_id=%s", project_id)
    except Exception as exc:
        logger.warning("GLB background export failed project_id=%s: %s", project_id, exc)


async def execute_pipeline_job(project_id: str) -> None:
    settings = get_settings()
    await merge_job(project_id, status="processing", error=None, graph_ready=False, json_ready=False)

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

        await merge_job(
            project_id,
            status="graph_ready",
            graph_ready=True,
            element_count=model.element_count,
            error=None,
        )
        logger.info(
            "Neo4j ready — chat unlocked project_id=%s elements=%s",
            project_id,
            model.element_count,
        )

        try:
            processed_path = Path(settings.processed_dir) / f"{project_id}.json"
            processed_path.parent.mkdir(parents=True, exist_ok=True)
            processed_path.write_text(model.model_dump_json(indent=2))
            await merge_job(project_id, json_ready=True, status="completed")
            logger.info("JSON ready project_id=%s", project_id)
        except Exception as exc:
            logger.warning("JSON write failed project_id=%s: %s", project_id, exc)
            # Chat stays available; filters wait for JSON retry / manual fix.

        # asyncio.create_task(_export_glb_background(project_id, input_path))

    except Exception as exc:
        logger.exception("Pipeline failed project_id=%s", project_id)
        await merge_job(project_id, status="failed", error=str(exc))


def processed_json_path(project_id: str) -> Path:
    return Path(get_settings().processed_dir) / f"{project_id}.json"


def processed_glb_path(project_id: str) -> Path:
    return project_glb_path(Path(get_settings().processed_dir), project_id)


def upload_root(project_id: str) -> Path:
    return Path(get_settings().upload_dir) / project_id


def _build_status_payload(project_id: str, job: dict[str, Any]) -> dict[str, Any]:
    json_ready = bool(job.get("json_ready")) or processed_json_path(project_id).exists()
    graph_ready = bool(job.get("graph_ready"))
    status = job.get("status") or "received"

    if graph_ready and status == "processing":
        status = "graph_ready"
    if json_ready and graph_ready and status not in ("failed",):
        status = "completed"

    out: dict[str, Any] = {
        "status": status,
        "project_id": project_id,
        "graph_ready": graph_ready,
        "json_ready": json_ready,
    }
    if job.get("element_count") is not None:
        out["element_count"] = job["element_count"]
    if job.get("error"):
        out["error"] = job["error"]
    return out


async def resolve_pipeline_status(project_id: str) -> dict[str, Any]:
    settings = get_settings()
    job = await get_job(project_id)

    if job:
        return _build_status_payload(project_id, job)

    proc = processed_json_path(project_id)
    if proc.exists():
        return {
            "status": "completed",
            "project_id": project_id,
            "graph_ready": True,
            "json_ready": True,
        }

    upload_dir = Path(settings.upload_dir) / project_id
    if not upload_dir.exists():
        return {}

    return {"status": "received", "project_id": project_id, "graph_ready": False, "json_ready": False}


async def mark_upload_received(project_id: str) -> None:
    await merge_job(
        project_id,
        status="received",
        graph_ready=False,
        json_ready=False,
        error=None,
    )
