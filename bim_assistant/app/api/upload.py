"""
app/api/upload.py
POST /upload — Accept CAD file upload, store it, return file_id.
"""
import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter()
settings = get_settings()

ALLOWED_EXTENSIONS = {".ifc", ".step", ".stp", ".dwg", ".dxf", ".rvt"}


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    size_bytes: int
    format: str
    message: str


@router.post("", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a CAD file (IFC, STEP, DWG, DXF, RVT).
    Returns a file_id to use with /process.
    """
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{suffix}'. Allowed: {ALLOWED_EXTENSIONS}",
        )

    file_id = str(uuid.uuid4())
    dest_dir = Path(settings.upload_dir) / file_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / file.filename

    # Stream to disk
    with dest_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    size = dest_path.stat().st_size
    return UploadResponse(
        file_id=file_id,
        filename=file.filename,
        size_bytes=size,
        format=suffix.lstrip("."),
        message="File uploaded successfully. Call /process to parse it.",
    )
