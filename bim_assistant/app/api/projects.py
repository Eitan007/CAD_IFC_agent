"""
Maps legacy behaviours (upload folder / processed JSON / LLM query) to the frontend contract.
"""
from __future__ import annotations

import gzip
import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.agent.agent import run_agent
from app.config import get_settings
from app.services import project_jobs
from app.services.deterministic_checks import build_pipeline_checks, source_format_for_path
from app.services.project_jobs import processed_glb_path
from app.storage.database import get_session
from app.storage.repository import get_project

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["Projects"])

settings = get_settings()

MAX_UPLOAD_BYTES = 500 * 1024 * 1024
ALLOWED_UPLOAD_SUFFIXES = {".ifc", ".step", ".stp"}


class UploadProjectResponse(BaseModel):
    project_id: str = Field(description="Use as project scope for viewer, pipeline, and chat")


class ProcessEnqueueResponse(BaseModel):
    status: str


class PipelineStatusResponse(BaseModel):
    status: str
    project_id: str
    element_count: int | None = None
    error: str | None = None
    graph_ready: bool = False
    json_ready: bool = False
    source_format: str | None = None
    preview_status: str | None = None
    preview_error: str | None = None
    checks: list[dict] = Field(default_factory=list)


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    selected_element: str | None = None
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=12)


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
    if project_id in {
        project_jobs.SAMPLE_PROJECT_ID,
        project_jobs.SAMPLE_STEP_PROJECT_ID,
        project_jobs.SAMPLE_THREADED_STEP_PROJECT_ID,
    }:
        # Check standard upload dir or repo root fallback
        root = project_jobs.upload_root(project_id)
        if root.exists():
            files = list(root.iterdir())
            if files:
                return files[0]
        sample_path = project_jobs.bundled_sample_path(project_id)
        if sample_path is not None:
            return sample_path

    root = project_jobs.upload_root(project_id)
    if not root.exists():
        raise HTTPException(status_code=404, detail="Project upload not found.")
    files = list(root.iterdir())
    if not files:
        raise HTTPException(status_code=400, detail="No uploaded file on disk.")
    return files[0]


def _validate_upload_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="Only .ifc, .step, and .stp uploads are supported.",
        )
    return suffix


@router.post("/upload", response_model=UploadProjectResponse)
async def upload_project(file: UploadFile = File(...)):
    """Accept one IFC, STEP, or STP model and return its project id."""
    _validate_upload_filename(file.filename or "")

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
                if total > MAX_UPLOAD_BYTES:
                    dest_path.unlink(missing_ok=True)
                    shutil.rmtree(dest_dir, ignore_errors=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum size ({MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        shutil.rmtree(dest_dir, ignore_errors=True)
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    await project_jobs.mark_upload_received(project_id)
    return UploadProjectResponse(project_id=project_id)


@router.put("/{project_id}/upload", response_model=UploadProjectResponse)
async def upload_project_with_id(
    project_id: str,
    request: Request,
    x_filename: str = Header(default="model", alias="X-Filename"),
    content_encoding: str | None = Header(default=None, alias="Content-Encoding"),
):
    """
    Accept raw or gzip-compressed IFC, STEP, or STP bytes for a client-assigned project id.
    Used for local preview + background sync.
    """
    _validate_upload_filename(x_filename)

    dest_dir = Path(settings.upload_dir) / project_id
    if dest_dir.exists():
        shutil.rmtree(dest_dir, ignore_errors=True)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(x_filename).name
    dest_path = dest_dir / safe_name

    body = await request.body()
    if content_encoding and content_encoding.lower() == "gzip":
        try:
            body = gzip.decompress(body)
        except OSError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid gzip body: {exc}") from exc

    if len(body) > MAX_UPLOAD_BYTES:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size ({MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
        )

    try:
        dest_path.write_bytes(body)
    except Exception as exc:
        shutil.rmtree(dest_dir, ignore_errors=True)
        logger.exception("Upload failed project_id=%s", project_id)
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    await project_jobs.mark_upload_received(project_id)
    return UploadProjectResponse(project_id=project_id)


@router.post("/{project_id}/process", response_model=ProcessEnqueueResponse)
async def enqueue_process(project_id: str, background_tasks: BackgroundTasks):
    """Trigger async parse → persist pipeline."""
    _find_uploaded_file(project_id)

    job = await project_jobs.get_job(project_id)
    st = job.get("status")

    if job.get("graph_ready") and job.get("json_ready"):
        return ProcessEnqueueResponse(status="completed")

    proc = project_jobs.processed_json_path(project_id)
    if proc.exists() and st not in ("processing", "queued") and job.get("graph_ready"):
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
    try:
        source_format = _find_uploaded_file(project_id).suffix.lower().lstrip(".") or None
    except HTTPException:
        source_format = None

    return PipelineStatusResponse(
        status=status,
        project_id=project_id,
        element_count=info.get("element_count"),
        error=info.get("error"),
        graph_ready=bool(info.get("graph_ready")),
        json_ready=bool(info.get("json_ready")),
        source_format=source_format,
        preview_status=info.get("preview_status"),
        preview_error=info.get("preview_error"),
        checks=build_pipeline_checks(
            source_format or "unknown",
            graph_ready=bool(info.get("graph_ready")),
            preview_status=info.get("preview_status"),
            element_count=info.get("element_count"),
        ),
    )


@router.post("/{project_id}/chat", response_model=ChatResponse)
async def project_chat(project_id: str, body: ChatRequest):
    job = await project_jobs.get_job(project_id)
    graph_ready = bool(job.get("graph_ready"))
    if not graph_ready:
        proc = project_jobs.processed_json_path(project_id)
        if proc.exists():
            graph_ready = True

    async with get_session() as session:
        project = await get_project(project_id, session)
    if not graph_ready and project is None:
        raise HTTPException(
            status_code=404,
            detail="Knowledge graph not ready yet — wait for Neo4j ingest.",
        )

    parts: list[str] = []
    if body.selected_element:
        parts.append(f"[Selected model element id: {body.selected_element}]")
    parts.append(body.message)
    full_query = "\n".join(parts)
    try:
        source_format = source_format_for_path(_find_uploaded_file(project_id))
    except HTTPException:
        source_format = "unknown"

    result = await run_agent(
        query=full_query,
        project_id=project_id,
        source_format=source_format,
        conversation_history=[message.model_dump() for message in body.history],
    )
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


@router.get("/{project_id}/ifc")
async def download_ifc(project_id: str):
    """Stream the uploaded source model for immediate browser use."""
    path = _find_uploaded_file(project_id)
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=path.name,
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


@router.get("/{project_id}/glb")
async def download_glb(project_id: str):
    """Stream tessellated GLB for in-browser 3D viewer."""
    path = processed_glb_path(project_id)
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="GLB not available yet — wait for pipeline completion.",
        )
    return FileResponse(
        path,
        media_type="model/gltf-binary",
        filename=f"{project_id}.glb",
    )
