"""
app/api/tasks.py
POST /tasks — Run a predefined workflow directly (no LLM involved).
Useful for batch pipelines where you don't need a conversational interface.
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from app.tools.quantities import tool_get_material_quantities, tool_get_element_counts
from app.tools.cost import tool_estimate_cost
from app.tools.schedule import tool_generate_schedule
from app.tools.compliance import tool_check_compliance
from app.storage.database import get_session
from app.storage.repository import get_project

logger = logging.getLogger(__name__)
router = APIRouter()

AVAILABLE_TASKS = {
    "material_quantities",
    "element_counts",
    "cost_estimation",
    "construction_schedule",
    "compliance_fire_safety",
    "compliance_eurocode2",
    "compliance_space_area",
}


class TaskRequest(BaseModel):
    task: str
    project_id: str


class TaskResponse(BaseModel):
    task: str
    project_id: str
    result: Any


@router.post("", response_model=TaskResponse)
async def run_task(request: TaskRequest):
    """
    Run a predefined deterministic workflow.

    Available tasks:
    - material_quantities
    - element_counts
    - cost_estimation
    - construction_schedule
    - compliance_fire_safety
    - compliance_eurocode2
    - compliance_space_area
    """
    if request.task not in AVAILABLE_TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task '{request.task}'. Available: {sorted(AVAILABLE_TASKS)}",
        )

    async with get_session() as session:
        project = await get_project(request.project_id, session)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{request.project_id}' not found.")

    pid = request.project_id
    task_dispatch = {
        "material_quantities": lambda: tool_get_material_quantities(pid),
        "element_counts": lambda: tool_get_element_counts(pid),
        "cost_estimation": lambda: tool_estimate_cost(pid),
        "construction_schedule": lambda: tool_generate_schedule(pid),
        "compliance_fire_safety": lambda: tool_check_compliance(pid, "fire_safety"),
        "compliance_eurocode2": lambda: tool_check_compliance(pid, "eurocode2"),
        "compliance_space_area": lambda: tool_check_compliance(pid, "space_area"),
    }

    result = await task_dispatch[request.task]()

    return TaskResponse(
        task=request.task,
        project_id=pid,
        result=result,
    )


@router.get("/available")
async def list_tasks():
    """List all available predefined tasks."""
    return {"tasks": sorted(AVAILABLE_TASKS)}
