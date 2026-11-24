"""
scripts/seed_db.py
Initialise the database schema. Run once before first use.

- Postgres: tables via SQLAlchemy metadata (from init_db).
- Neo4j: constraints + indexes via ensure_neo4j_constraints (also run at API startup).
"""
import asyncio
import sys
import os
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import get_settings
from app.storage.database import init_db, get_session
from app.storage.repository import get_project, save_building_model
from app.ingestion.pipeline import run_ingestion_pipeline
from app.services.project_jobs import (
    SAMPLE_PROJECT_ID,
    SAMPLE_STEP_PROJECT_ID,
    SAMPLE_THREADED_STEP_PROJECT_ID,
    processed_glb_path,
    processed_json_path,
    upload_root,
)


async def seed_sample_model(project_id: str, source_path: Path):
    settings = get_settings()
    if not source_path.is_file():
        print(f"Sample file not found at {source_path}. Skipping {project_id}.")
        return

    dest_dir = upload_root(project_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_source = dest_dir / source_path.name
    if not dest_source.exists():
        shutil.copyfile(source_path, dest_source)

    demo_glb = source_path.with_suffix(".glb")
    if demo_glb.is_file() and not processed_glb_path(project_id).exists():
        processed_glb_path(project_id).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(demo_glb, processed_glb_path(project_id))

    # Check if already in DB
    async with get_session() as session:
        proj = await get_project(project_id, session)

    proc_json = processed_json_path(project_id)
    if proj is not None and proc_json.exists():
        print(f"Sample model '{project_id}' is already seeded in {settings.db_backend} and JSON exists.")
        return

    print(f"Parsing and pre-building knowledge graph for sample model '{project_id}'...")
    model = await run_ingestion_pipeline(dest_source, project_id=project_id)

    async with get_session() as session:
        await save_building_model(model, session)

    proc_json.parent.mkdir(parents=True, exist_ok=True)
    proc_json.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    print(f"Sample model seeded successfully! ({model.element_count} elements in knowledge graph)")


async def main():
    settings = get_settings()
    print(f"Initialising database (DB_BACKEND={settings.db_backend})...")
    await init_db()
    if settings.db_backend == "neo4j":
        print(
            "Neo4j schema: constraints/indexes applied "
            "(unique Element.id, Project.id; indexes on Element.project_id and Element.type)."
        )
    repo_root = Path(__file__).resolve().parents[2]
    ifc_source = repo_root / "BasicHouse.ifc"
    if not ifc_source.is_file():
        ifc_source = Path(__file__).resolve().parents[1] / "BasicHouse.ifc"
    await seed_sample_model(SAMPLE_PROJECT_ID, ifc_source)
    await seed_sample_model(
        SAMPLE_STEP_PROJECT_ID,
        Path(__file__).resolve().parents[1] / "samples" / "HexBolt.step",
    )
    await seed_sample_model(
        SAMPLE_THREADED_STEP_PROJECT_ID,
        Path(__file__).resolve().parents[1] / "samples" / "ThreadedHexBolt.step",
    )
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
