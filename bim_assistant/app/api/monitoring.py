"""Local monitoring and deterministic evaluation endpoints."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.evaluation import score_answer, score_sample_files
from app.services.monitoring import monitoring_summary

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


class AnswerEvaluationRequest(BaseModel):
    source_format: str = Field(pattern="^(ifc|step|stp)$")
    answer: str = Field(min_length=1, max_length=8000)


@router.get("/summary")
async def get_monitoring_summary():
    return monitoring_summary()


@router.get("/evaluations/samples")
async def get_sample_evaluations():
    samples_dir = Path(__file__).resolve().parents[2] / "samples"
    return score_sample_files([samples_dir / "HexBolt.step", samples_dir / "ThreadedHexBolt.step"])


@router.post("/evaluations/answer")
async def evaluate_answer(body: AnswerEvaluationRequest):
    return score_answer(body.source_format, body.answer)
