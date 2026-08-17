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
from app.services.project_jobs import SAMPLE_PROJECT_ID, processed_json_path, upload_root


async def seed_sample_model():
    settings = get_settings()
    # Check if BasicHouse.ifc exists in repo root
    repo_root = Path(__file__).resolve().parents[2]
    ifc_path = repo_root / "BasicHouse.ifc"
    if not ifc_path.is_file():
        ifc_path = Path(__file__).resolve().parents[1] / "BasicHouse.ifc"

    if not ifc_path.is_file():
        print(f"BasicHouse.ifc not found at {ifc_path}. Skipping sample model seeding.")
        return

    dest_dir = upload_root(SAMPLE_PROJECT_ID)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_ifc = dest_dir / "BasicHouse.ifc"
    if not dest_ifc.exists():
        shutil.copyfile(ifc_path, dest_ifc)

    # Check if already in DB
    async with get_session() as session:
        proj = await get_project(SAMPLE_PROJECT_ID, session)

    proc_json = processed_json_path(SAMPLE_PROJECT_ID)
    if proj is not None and proc_json.exists():
        print(f"Sample model '{SAMPLE_PROJECT_ID}' is already seeded in {settings.db_backend} and JSON exists.")
        return

    print(f"Parsing and pre-building knowledge graph for sample model '{SAMPLE_PROJECT_ID}'...")
    model = await run_ingestion_pipeline(dest_ifc, project_id=SAMPLE_PROJECT_ID)

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
    await seed_sample_model()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
