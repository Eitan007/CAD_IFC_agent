"""
SRS-aligned project API: /api/projects/*

Maps legacy behaviours (upload folder / processed JSON / LLM query) to the frontend contract.
"""
from __future__ import annotations

import json
import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.agent.agent import run_agent
from app.config import get_settings
from app.services import project_jobs
from app.storage.database import get_session
from app.storage.repository import get_project

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["Projects"])

settings = get_settings()

MAX_IFC_BYTES = 500 * 1024 * 1024
ALLOWED_UPLOAD_SUFFIX = ".ifc"


class UploadProjectResponse(BaseModel):
    project_id: str = Field(description="Use as project scope for viewer, pipeline, and chat")


class ProcessEnqueueResponse(BaseModel):
    status: str


class PipelineStatusResponse(BaseModel):
    status: str
    project_id: str
    element_count: int | None = None
    error: str | None = None


class ChatRequest(BaseModel):
    message: str
    selected_element: str | None = None


class GraphRef(BaseModel):
    kind: str
    detail: str | None = None


class ChatResponse(BaseModel):
    answer: str
    project_id: str
    explanation: str
    references: list[GraphRef]
    tool_calls: list[dict]
    iterations: int
    warning: str | None = None


def _find_uploaded_file(project_id: str) -> Path:
    root = project_jobs.upload_root(project_id)
    if not root.exists():
        raise HTTPException(status_code=404, detail="Project upload not found.")
    files = list(root.iterdir())
    if not files:
        raise HTTPException(status_code=400, detail="No uploaded file on disk.")
    return files[0]


@router.post("/upload", response_model=UploadProjectResponse)
async def upload_project(file: UploadFile = File(...)):
    """Accept a single .ifc file; returns project_id."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix != ALLOWED_UPLOAD_SUFFIX:
        raise HTTPException(
            status_code=400,
            detail=f"Only {ALLOWED_UPLOAD_SUFFIX} uploads are supported.",
        )

    project_id = str(uuid.uuid4())
    dest_dir = Path(settings.upload_dir) / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename).name
    dest_path = dest_dir / safe_name

    total = 0
    chunk_size = 1024 * 1024
    try:
        with dest_path.open("wb") as out:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_IFC_BYTES:
                    dest_path.unlink(missing_ok=True)
                    shutil.rmtree(dest_dir, ignore_errors=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum size ({MAX_IFC_BYTES // (1024 * 1024)} MB).",
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        shutil.rmtree(dest_dir, ignore_errors=True)
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    return UploadProjectResponse(project_id=project_id)


@router.post("/{project_id}/process", response_model=ProcessEnqueueResponse)
async def enqueue_process(project_id: str, background_tasks: BackgroundTasks):
    """Trigger async parse → persist pipeline."""
    _find_uploaded_file(project_id)

    job = await project_jobs.get_job(project_id)
    st = job.get("status")

    proc = project_jobs.processed_json_path(project_id)
    if proc.exists() and st not in ("processing", "queued"):
        return ProcessEnqueueResponse(status="completed")

    if st == "processing":
        raise HTTPException(status_code=409, detail="Pipeline already running.")
    if st == "queued":
        raise HTTPException(status_code=409, detail="Pipeline already queued.")

    await project_jobs.merge_job(project_id, status="queued", error=None)
    background_tasks.add_task(project_jobs.execute_pipeline_job, project_id)
    return ProcessEnqueueResponse(status="queued")


@router.get("/{project_id}/status", response_model=PipelineStatusResponse)
async def pipeline_status(project_id: str):
    info = await project_jobs.resolve_pipeline_status(project_id)
    if not info:
        raise HTTPException(status_code=404, detail="Unknown project_id.")

    status = info["status"]
    return PipelineStatusResponse(
        status=status,
        project_id=project_id,
        element_count=info.get("element_count"),
        error=info.get("error"),
    )


@router.post("/{project_id}/chat", response_model=ChatResponse)
async def project_chat(project_id: str, body: ChatRequest):
    async with get_session() as session:
        project = await get_project(project_id, session)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not processed yet — wait for pipeline completion.",
        )

    parts: list[str] = []
    if body.selected_element:
        parts.append(f"[Selected IFC element id: {body.selected_element}]")
    parts.append(body.message)
    full_query = "\n".join(parts)

    result = await run_agent(query=full_query, project_id=project_id)
    tool_calls = result["tool_calls"]

    references = [
        GraphRef(kind="tool_trace", detail=tc.get("tool"))
        for tc in tool_calls
        if tc.get("tool")
    ]

    answer = result["answer"]
    return ChatResponse(
        answer=answer,
        project_id=project_id,
        explanation=answer,
        references=references,
        tool_calls=tool_calls,
        iterations=result["iterations"],
        warning=result.get("warning"),
    )


@router.get("/{project_id}/model")
async def project_model(project_id: str):
    """Return processed BuildingModel JSON (metadata graph)."""
    path = project_jobs.processed_json_path(project_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Processed model not available yet.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("Corrupt processed JSON for %s: %s", project_id, exc)
        raise HTTPException(status_code=500, detail="Stored model JSON is invalid.") from exc


@router.get("/{project_id}/ifc")
async def download_ifc(project_id: str):
    """Stream original IFC file for in-browser viewers."""
    path = _find_uploaded_file(project_id)
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=path.name,
    )
