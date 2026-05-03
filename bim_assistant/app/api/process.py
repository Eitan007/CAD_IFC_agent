"""
app/api/process.py
POST /process — Trigger parse → normalise → store pipeline for an uploaded file.
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.config import get_settings
from app.ingestion.pipeline import run_ingestion_pipeline
from app.storage.database import get_session
from app.storage.repository import save_building_model

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


class ProcessRequest(BaseModel):
    file_id: str


class ProcessResponse(BaseModel):
    project_id: str
    file_id: str
    status: str
    element_count: int
    warnings: list[str]
    message: str


@router.post("", response_model=ProcessResponse)
async def process_file(request: ProcessRequest, background_tasks: BackgroundTasks):
    """
    Parse and store a previously uploaded CAD file.
    """
    file_id = request.file_id
    upload_dir = Path(settings.upload_dir) / file_id

    if not upload_dir.exists():
        raise HTTPException(status_code=404, detail=f"File ID '{file_id}' not found.")

    # Find the uploaded file
    candidates = list(upload_dir.iterdir())
    if not candidates:
        raise HTTPException(status_code=400, detail="Upload directory is empty.")
    input_path = candidates[0]

    try:
        model = await run_ingestion_pipeline(input_path, project_id=file_id)
    except Exception as exc:
        logger.exception("Pipeline failed for file_id=%s", file_id)
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}")

    # Save to DB
    async with get_session() as session:
        await save_building_model(model, session)

    # Save processed JSON for inspection
    processed_path = Path(settings.processed_dir) / f"{file_id}.json"
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    processed_path.write_text(model.model_dump_json(indent=2))

    return ProcessResponse(
        project_id=model.project_id,
        file_id=file_id,
        status="processed",
        element_count=model.element_count,
        warnings=model.parse_warnings[:20],  # cap warnings in response
        message=f"Parsed {model.element_count} elements. Ready for queries.",
    )
