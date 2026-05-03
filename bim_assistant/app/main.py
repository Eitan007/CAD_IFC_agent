"""
app/main.py
FastAPI application entrypoint.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import upload, process, query, tasks, projects
from app.storage.database import init_db
from app.utils.logging import configure_logging

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.processed_dir, exist_ok=True)
    await init_db()
    yield
    # teardown (close pools, etc.) goes here


app = FastAPI(
    title="BIM/CAD AI Assistant",
    description="AI-powered BIM assistant: IFC/STEP parsing, structured storage, LLM tool-calling.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router,  prefix="/upload",  tags=["Ingestion"])
app.include_router(process.router, prefix="/process", tags=["Processing"])
app.include_router(query.router,   prefix="/query",   tags=["Agent"])
app.include_router(tasks.router,   prefix="/tasks",   tags=["Workflows"])
app.include_router(projects.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
