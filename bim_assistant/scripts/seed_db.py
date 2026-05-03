"""
scripts/seed_db.py
Initialise the database schema. Run once before first use.

- Postgres: tables via SQLAlchemy metadata (from init_db).
- Neo4j: constraints + indexes via ensure_neo4j_constraints (also run at API startup).
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import get_settings
from app.storage.database import init_db


async def main():
    settings = get_settings()
    print(f"Initialising database (DB_BACKEND={settings.db_backend})...")
    await init_db()
    if settings.db_backend == "neo4j":
        print(
            "Neo4j schema: constraints/indexes applied "
            "(unique Element.id, Project.id; indexes on Element.project_id and Element.type)."
        )
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
