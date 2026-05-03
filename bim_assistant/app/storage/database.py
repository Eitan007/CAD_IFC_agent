"""
app/storage/database.py
Database connection management.

Supports two backends controlled by DB_BACKEND env var:
  - "postgres" (default): async SQLAlchemy + asyncpg
  - "neo4j": neo4j.AsyncGraphDatabase (async driver)

Callers use ``get_session()`` for both backends; it yields ``AsyncSession``
(Postgres) or ``neo4j.AsyncSession`` (Neo4j) depending on configuration.
"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── PostgreSQL ──────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None

# ── Neo4j ───────────────────────────────────────────────────────────────────

_neo4j_driver: Any = None  # neo4j.AsyncDriver when DB_BACKEND=neo4j


async def _init_neo4j_async() -> None:
    global _neo4j_driver
    from neo4j import AsyncGraphDatabase  # type: ignore

    _neo4j_driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    await _neo4j_driver.verify_connectivity()


async def init_db():
    global _engine, _session_factory
    if settings.db_backend == "postgres":
        _engine = create_async_engine(
            settings.postgres_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
        )
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("PostgreSQL connected and schema created.")
    elif settings.db_backend == "neo4j":
        await _init_neo4j_async()
        await ensure_neo4j_constraints()
        logger.info("Neo4j connected.")
    else:
        raise ValueError(f"Unknown DB_BACKEND: {settings.db_backend}")


@asynccontextmanager
async def _postgres_session() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_neo4j_session() -> AsyncGenerator[Any, None]:
    """Yield an async Neo4j session (use with ``async with``)."""
    if _neo4j_driver is None:
        raise RuntimeError("Neo4j not initialised. Call init_db() first with DB_BACKEND=neo4j.")
    async with _neo4j_driver.session() as session:
        yield session


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession | Any, None]:
    """
    Database session for the active backend.

    * ``DB_BACKEND=postgres`` → SQLAlchemy ``AsyncSession`` (commits on success).
    * ``DB_BACKEND=neo4j`` → ``neo4j.AsyncSession`` (no implicit SQLAlchemy commit).
    """
    if settings.db_backend == "postgres":
        async with _postgres_session() as session:
            yield session
    elif settings.db_backend == "neo4j":
        async with get_neo4j_session() as session:
            yield session
    else:
        raise ValueError(f"Unknown DB_BACKEND: {settings.db_backend}")


NEO4J_SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT element_id_unique IF NOT EXISTS FOR (e:Element) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT project_id_unique IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE",
    "CREATE INDEX element_project_id IF NOT EXISTS FOR (e:Element) ON (e.project_id)",
    "CREATE INDEX element_type_idx IF NOT EXISTS FOR (e:Element) ON (e.type)",
]


async def ensure_neo4j_constraints() -> None:
    """Create Neo4j constraints and indexes (safe to run repeatedly)."""
    if _neo4j_driver is None:
        return
    async with _neo4j_driver.session() as session:
        for cypher in NEO4J_SCHEMA_STATEMENTS:
            await session.run(cypher)
