"""
app/api/query.py
POST /query — Send a natural-language query to the LLM agent.
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent.agent import run_agent
from app.storage.database import get_session
from app.storage.repository import get_project

logger = logging.getLogger(__name__)
router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    project_id: str
    max_iterations: int = 8


class QueryResponse(BaseModel):
    answer: str
    project_id: str
    tool_calls: list[dict]
    iterations: int
    warning: str | None = None


@router.post("", response_model=QueryResponse)
async def query_agent(request: QueryRequest):
    """
    Send a natural-language query to the LLM agent.
    The agent will call deterministic tools to answer.
    """
    # Verify project exists
    async with get_session() as session:
        project = await get_project(request.project_id, session)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{request.project_id}' not found. Upload and process a file first.",
        )

    result = await run_agent(
        query=request.query,
        project_id=request.project_id,
        max_iterations=request.max_iterations,
    )

    return QueryResponse(
        answer=result["answer"],
        project_id=request.project_id,
        tool_calls=result["tool_calls"],
        iterations=result["iterations"],
        warning=result.get("warning"),
    )
