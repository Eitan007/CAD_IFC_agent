import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from app.config import get_settings
from app.storage.database import Base
from app.storage.models import Element, Project
from app.storage.repository import (
    get_material_element_types,
    get_element_counts,
    graph_traverse,
)

settings = get_settings()


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"


@pytest_asyncio.fixture
async def async_session():
    # Force backend setting to postgres for testing the SQL code paths on SQLite
    orig_backend = settings.db_backend
    settings.db_backend = "postgres"

    # Set up in-memory SQLite database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    # Teardown
    await engine.dispose()
    settings.db_backend = orig_backend


@pytest.mark.asyncio
async def test_repository_aggregates(async_session):
    # Seed project
    project = Project(
        id="p1",
        source_file="test.ifc",
        status="processed",
        element_count=3,
    )
    async_session.add(project)
    await async_session.commit()

    # Seed elements
    e1 = Element(
        id="e1",
        project_id="p1",
        type="wall",
        material="concrete",
        volume=10.0,
        area=5.0,
    )
    e2 = Element(
        id="e2",
        project_id="p1",
        type="wall",
        material="concrete",
        volume=12.0,
        area=6.0,
    )
    e3 = Element(
        id="e3",
        project_id="p1",
        type="slab",
        material="steel",
        volume=2.0,
        area=4.0,
    )
    async_session.add_all([e1, e2, e3])
    await async_session.commit()

    # Test material-type mappings
    mappings = await get_material_element_types("p1", async_session)
    assert len(mappings) == 2
    concrete_mapping = next(m for m in mappings if m["material"] == "concrete")
    assert concrete_mapping["type"] == "wall"

    # Test element counts
    counts = await get_element_counts("p1", async_session)
    assert counts == {"wall": 2, "slab": 1}


@pytest.mark.asyncio
async def test_repository_graph_traverse_fallback(async_session):
    # Seed project
    project = Project(
        id="p2",
        source_file="test.ifc",
        status="processed",
        element_count=3,
    )
    async_session.add(project)
    await async_session.commit()

    # Seed elements with connectivity
    e1 = Element(
        id="e1",
        project_id="p2",
        type="wall",
        material="concrete",
        connected_to=["e2"],
    )
    e2 = Element(
        id="e2",
        project_id="p2",
        type="slab",
        material="concrete",
        connected_to=["e3"],
    )
    e3 = Element(
        id="e3",
        project_id="p2",
        type="column",
        material="steel",
        connected_to=[],
    )
    async_session.add_all([e1, e2, e3])
    await async_session.commit()

    # Test graph traversal (SQLite fallback runs BFS)
    traversed = await graph_traverse("p2", "e1", "CONNECTS_TO", depth=2, session=async_session)
    assert len(traversed) == 3
    ids = {el.id for el in traversed}
    assert ids == {"e1", "e2", "e3"}


@pytest.mark.asyncio
async def test_neo4j_save_building_model_tx():
    from unittest.mock import AsyncMock, MagicMock
    from app.storage.repository import _neo4j_save_building_model_tx
    from app.normalization.schema import BuildingModel, BuildingElement

    tx = MagicMock()
    tx.run = AsyncMock()

    e1 = BuildingElement(
        id="elem1",
        type="wall",
        material="concrete",
        connected_to=["elem2"],
    )
    e2 = BuildingElement(
        id="elem2",
        type="slab",
        material="steel",
        connected_to=["elem1"],
    )

    model = BuildingModel(
        project_id="proj123",
        source_file="test_file.ifc",
        element_count=2,
        elements=[e1, e2],
    )

    await _neo4j_save_building_model_tx(tx, model)

    # Verify project merge was run
    tx.run.assert_any_call(
        """
        MERGE (p:Project {id: $id})
        ON CREATE SET p.created_at = datetime()
        SET p.source_file = $source_file,
            p.status = $status,
            p.element_count = $element_count,
            p.parse_warnings = $parse_warnings,
            p.updated_at = datetime()
        """,
        id="proj123",
        source_file="test_file.ifc",
        status="processed",
        element_count=2,
        parse_warnings=[],
    )

    # Verify node batch was run
    called_node_queries = [
        call for call in tx.run.call_args_list
        if "UNWIND $batch AS row" in call[0][0] and "MERGE (e:Element {id: row.id})" in call[0][0]
    ]
    assert len(called_node_queries) == 1
    node_batch_arg = called_node_queries[0][1]["batch"]
    assert len(node_batch_arg) == 2
    assert node_batch_arg[0]["id"] == "elem1"
    assert node_batch_arg[1]["id"] == "elem2"

    # Verify relationships batch was run
    called_rel_queries = [
        call for call in tx.run.call_args_list
        if "UNWIND $batch AS row" in call[0][0] and "CONNECTS_TO" in call[0][0]
    ]
    assert len(called_rel_queries) == 1
    rel_batch_arg = called_rel_queries[0][1]["batch"]
    assert len(rel_batch_arg) == 2  # elem1 -> elem2, and elem2 -> elem1

