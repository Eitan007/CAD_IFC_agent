"""
app/storage/repository.py
All database CRUD operations.
Supports Postgres (SQLAlchemy) and Neo4j (async driver); routing via DB_BACKEND.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.normalization.schema import BuildingElement, BuildingModel
from app.storage.models import Element, Project
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Neo4j relationship types exposed for traversal / tooling
GRAPH_REL_TYPES = frozenset({"CONNECTS_TO", "LOCATED_IN", "CONTAINED_BY", "ON_STOREY"})
MAX_GRAPH_DEPTH = 10


def utcnow():
    return datetime.now(timezone.utc)


def _building_element_to_neo4j_props(elem: BuildingElement) -> dict[str, Any]:
    """Flatten BuildingElement into Neo4j property map (handles incomplete IFC data)."""
    bbox = elem.bounding_box
    # Neo4j allows only primitives or arrays thereof — nested IFC property maps → JSON string
    props: dict[str, Any] = {
        "id": elem.id,
        "project_id": elem.project_id or "",
        "type": elem.type or "unknown",
        "connected_to": [x for x in (elem.connected_to or []) if x],
        "contains": [x for x in (elem.contains or []) if x],
        "properties_json": json.dumps(elem.properties or {}, default=str),
    }
    optional = {
        "ifc_guid": elem.ifc_guid,
        "name": elem.name,
        "description": elem.description,
        "volume": elem.volume,
        "area": elem.area,
        "length": elem.length,
        "bbox_min_x": bbox.min_x if bbox else None,
        "bbox_min_y": bbox.min_y if bbox else None,
        "bbox_min_z": bbox.min_z if bbox else None,
        "bbox_max_x": bbox.max_x if bbox else None,
        "bbox_max_y": bbox.max_y if bbox else None,
        "bbox_max_z": bbox.max_z if bbox else None,
        "material": elem.material,
        "material_volume": elem.material_volume,
        "storey": elem.storey,
        "room": elem.room,
        "located_in": elem.located_in,
        "contained_by": elem.contained_by,
    }
    for k, v in optional.items():
        if v is not None:
            props[k] = v
    props.setdefault("created_at", utcnow().isoformat())
    return props


def _neo4j_element_node_to_model(props: dict[str, Any]) -> Element:
    """Build detached SQLAlchemy Element from Neo4j node properties (read-only use)."""
    def _get(k: str, default=None):
        return props[k] if k in props and props[k] is not None else default

    connected = _get("connected_to")
    contains = _get("contains")
    raw_props = _get("properties_json")
    if raw_props is None:
        raw_props = _get("properties", {})
    if isinstance(raw_props, str):
        try:
            raw_props = json.loads(raw_props)
        except json.JSONDecodeError:
            raw_props = {}
    return Element(
        id=str(props["id"]),
        project_id=str(_get("project_id", "")),
        ifc_guid=_get("ifc_guid"),
        type=str(_get("type", "unknown")),
        name=_get("name"),
        description=_get("description"),
        volume=_get("volume"),
        area=_get("area"),
        length=_get("length"),
        bbox_min_x=_get("bbox_min_x"),
        bbox_min_y=_get("bbox_min_y"),
        bbox_min_z=_get("bbox_min_z"),
        bbox_max_x=_get("bbox_max_x"),
        bbox_max_y=_get("bbox_max_y"),
        bbox_max_z=_get("bbox_max_z"),
        material=_get("material"),
        material_volume=_get("material_volume"),
        storey=_get("storey"),
        room=_get("room"),
        located_in=_get("located_in"),
        contained_by=_get("contained_by"),
        connected_to=list(connected) if isinstance(connected, list) else [],
        contains=list(contains) if isinstance(contains, list) else [],
        properties=dict(raw_props) if isinstance(raw_props, dict) else {},
    )


def _neo4j_project_node_to_model(props: dict[str, Any]) -> Project:
    pw = props.get("parse_warnings")
    if pw is None:
        pw = []
    elif isinstance(pw, str):
        try:
            pw = json.loads(pw)
        except json.JSONDecodeError:
            pw = []
    created = props.get("created_at")
    updated = props.get("updated_at")
    return Project(
        id=str(props["id"]),
        source_file=str(props.get("source_file", "")),
        status=str(props.get("status", "pending")),
        created_at=_parse_dt(created) if created else utcnow(),
        updated_at=_parse_dt(updated) if updated else utcnow(),
        parse_warnings=list(pw),
        element_count=int(props.get("element_count", 0)),
    )


def _parse_dt(val: Any) -> datetime:
    if isinstance(val, datetime):
        return val
    if val is None:
        return utcnow()
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except ValueError:
        return utcnow()


async def _neo4j_save_building_model_tx(tx, model: BuildingModel) -> None:
    warnings = model.parse_warnings or []
    await tx.run(
        """
        MERGE (p:Project {id: $id})
        ON CREATE SET p.created_at = datetime()
        SET p.source_file = $source_file,
            p.status = $status,
            p.element_count = $element_count,
            p.parse_warnings = $parse_warnings,
            p.updated_at = datetime()
        """,
        id=model.project_id,
        source_file=model.source_file,
        status="processed",
        element_count=model.element_count,
        parse_warnings=warnings,
    )

    pid = model.project_id
    for elem in model.elements:
        props = _building_element_to_neo4j_props(elem)
        await tx.run(
            """
            MERGE (e:Element {id: $id})
            SET e += $props
            MERGE (pr:Project {id: $pid})
            MERGE (e)-[:IN_PROJECT]->(pr)
            """,
            id=elem.id,
            props=props,
            pid=pid,
        )

    for elem in model.elements:
        eid = elem.id
        for tid in elem.connected_to or []:
            if not tid:
                continue
            await tx.run(
                """
                MATCH (a:Element {id: $aid, project_id: $pid})
                MATCH (b:Element {id: $bid, project_id: $pid})
                MERGE (a)-[:CONNECTS_TO]->(b)
                """,
                aid=eid,
                bid=str(tid),
                pid=pid,
            )

        lid = elem.located_in
        if lid:
            await tx.run(
                """
                MATCH (a:Element {id: $aid, project_id: $pid})
                MATCH (b:Element {id: $bid, project_id: $pid})
                MERGE (a)-[:LOCATED_IN]->(b)
                """,
                aid=eid,
                bid=str(lid),
                pid=pid,
            )

        cid = elem.contained_by
        if cid:
            await tx.run(
                """
                MATCH (a:Element {id: $aid, project_id: $pid})
                MATCH (b:Element {id: $bid, project_id: $pid})
                MERGE (a)-[:CONTAINED_BY]->(b)
                """,
                aid=eid,
                bid=str(cid),
                pid=pid,
            )

        storey = elem.storey
        if storey:
            await tx.run(
                """
                MATCH (e:Element {id: $eid, project_id: $pid})
                MERGE (s:Storey {project_id: $pid, name: $storey})
                MERGE (e)-[:ON_STOREY]->(s)
                """,
                eid=eid,
                pid=pid,
                storey=str(storey),
            )


# ── Write ───────────────────────────────────────────────────────────────────


async def save_building_model(model: BuildingModel, session: AsyncSession | Any) -> None:
    """Persist all elements of a BuildingModel (single Neo4j transaction)."""
    if settings.db_backend == "postgres":
        assert isinstance(session, AsyncSession)
        project = Project(
            id=model.project_id,
            source_file=model.source_file,
            status="processed",
            element_count=model.element_count,
            parse_warnings=model.parse_warnings,
        )
        await session.merge(project)

        BATCH = 500
        for i in range(0, len(model.elements), BATCH):
            batch = model.elements[i : i + BATCH]
            for elem in batch:
                db_elem = _schema_to_db(elem)
                await session.merge(db_elem)

        logger.info("Saved %d elements for project %s", model.element_count, model.project_id)
        return

    await session.execute_write(_neo4j_save_building_model_tx, model)
    logger.info("Saved %d elements for project %s (Neo4j)", model.element_count, model.project_id)


def _schema_to_db(elem: BuildingElement) -> Element:
    bbox = elem.bounding_box
    return Element(
        id=elem.id,
        project_id=elem.project_id or "",
        ifc_guid=elem.ifc_guid,
        type=elem.type,
        name=elem.name,
        description=elem.description,
        volume=elem.volume,
        area=elem.area,
        length=elem.length,
        bbox_min_x=bbox.min_x if bbox else None,
        bbox_min_y=bbox.min_y if bbox else None,
        bbox_min_z=bbox.min_z if bbox else None,
        bbox_max_x=bbox.max_x if bbox else None,
        bbox_max_y=bbox.max_y if bbox else None,
        bbox_max_z=bbox.max_z if bbox else None,
        material=elem.material,
        material_volume=elem.material_volume,
        storey=elem.storey,
        room=elem.room,
        located_in=elem.located_in,
        contained_by=elem.contained_by,
        connected_to=elem.connected_to,
        contains=elem.contains,
        properties=elem.properties,
    )


# ── Read ────────────────────────────────────────────────────────────────────


async def get_elements_by_type(
    project_id: str,
    element_type: str,
    session: AsyncSession | Any,
) -> list[Element]:
    if settings.db_backend == "postgres":
        assert isinstance(session, AsyncSession)
        result = await session.execute(
            select(Element).where(
                Element.project_id == project_id,
                Element.type == element_type,
            )
        )
        return result.scalars().all()

    res = await session.run(
        """
        MATCH (e:Element {project_id: $pid, type: $etype})
        RETURN e ORDER BY e.id
        """,
        pid=project_id,
        etype=element_type,
    )
    out: list[Element] = []
    async for record in res:
        node = record["e"]
        out.append(_neo4j_element_node_to_model(dict(node)))
    return out


async def get_all_elements(
    project_id: str,
    session: AsyncSession | Any,
    limit: int = 10_000,
) -> list[Element]:
    if settings.db_backend == "postgres":
        assert isinstance(session, AsyncSession)
        result = await session.execute(
            select(Element)
            .where(Element.project_id == project_id)
            .limit(limit)
        )
        return result.scalars().all()

    res = await session.run(
        """
        MATCH (e:Element {project_id: $pid})
        RETURN e ORDER BY e.id
        LIMIT $lim
        """,
        pid=project_id,
        lim=int(limit),
    )
    out: list[Element] = []
    async for record in res:
        out.append(_neo4j_element_node_to_model(dict(record["e"])))
    return out


async def get_material_summary(
    project_id: str,
    session: AsyncSession | Any,
) -> list[dict]:
    if settings.db_backend == "postgres":
        assert isinstance(session, AsyncSession)
        result = await session.execute(
            select(
                Element.material,
                func.sum(Element.volume).label("total_volume"),
                func.sum(Element.area).label("total_area"),
                func.count(Element.id).label("element_count"),
            )
            .where(Element.project_id == project_id, Element.material.isnot(None))
            .group_by(Element.material)
        )
        return [row._asdict() for row in result.all()]

    res = await session.run(
        """
        MATCH (e:Element {project_id: $pid})
        WHERE e.material IS NOT NULL AND e.material <> ''
        RETURN e.material AS material,
               sum(coalesce(e.volume, 0)) AS total_volume,
               sum(coalesce(e.area, 0)) AS total_area,
               count(e) AS element_count
        """,
        pid=project_id,
    )
    rows: list[dict] = []
    async for record in res:
        rows.append({
            "material": record["material"],
            "total_volume": float(record["total_volume"] or 0),
            "total_area": float(record["total_area"] or 0),
            "element_count": int(record["element_count"] or 0),
        })
    return rows


async def get_element_by_id(
    element_id: str,
    session: AsyncSession | Any,
) -> Optional[Element]:
    if settings.db_backend == "postgres":
        assert isinstance(session, AsyncSession)
        result = await session.execute(
            select(Element).where(Element.id == element_id)
        )
        return result.scalar_one_or_none()

    res = await session.run(
        "MATCH (e:Element {id: $eid}) RETURN e LIMIT 1",
        eid=element_id,
    )
    record = await res.single()
    if record is None:
        return None
    return _neo4j_element_node_to_model(dict(record["e"]))


async def get_project(
    project_id: str,
    session: AsyncSession | Any,
) -> Optional[Project]:
    if settings.db_backend == "postgres":
        assert isinstance(session, AsyncSession)
        result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    res = await session.run(
        "MATCH (p:Project {id: $pid}) RETURN p LIMIT 1",
        pid=project_id,
    )
    record = await res.single()
    if record is None:
        return None
    return _neo4j_project_node_to_model(dict(record["p"]))


async def list_projects(session: AsyncSession | Any) -> list[Project]:
    if settings.db_backend == "postgres":
        assert isinstance(session, AsyncSession)
        result = await session.execute(select(Project).order_by(Project.created_at.desc()))
        return result.scalars().all()

    res = await session.run(
        """
        MATCH (p:Project)
        RETURN p ORDER BY p.id DESC
        """
    )
    out: list[Project] = []
    async for record in res:
        out.append(_neo4j_project_node_to_model(dict(record["p"])))
    return out


def _postgres_neighbors(
    elem: Element,
    relationship_type: str,
    by_id: dict[str, Element],
) -> list[str]:
    """Adjacency from relational columns / JSON lists."""
    nids: list[str] = []
    if relationship_type == "CONNECTS_TO":
        nids.extend(x for x in (elem.connected_to or []) if x)
    elif relationship_type == "LOCATED_IN":
        if elem.located_in:
            nids.append(elem.located_in)
    elif relationship_type == "CONTAINED_BY":
        if elem.contained_by:
            nids.append(elem.contained_by)
    elif relationship_type == "ON_STOREY":
        if elem.storey:
            sn = elem.storey
            nids.extend(
                o.id for o in by_id.values()
                if o.storey == sn and o.id != elem.id
            )
    return nids


async def graph_traverse(
    project_id: str,
    start_element_id: str,
    relationship_type: str,
    depth: int,
    session: AsyncSession | Any,
) -> list[Element]:
    """
    Elements reachable from ``start_element_id`` within ``depth`` hops
    following only edges of ``relationship_type``.
    """
    if relationship_type not in GRAPH_REL_TYPES:
        raise ValueError(
            f"relationship_type must be one of {sorted(GRAPH_REL_TYPES)}"
        )
    d = max(1, min(int(depth), MAX_GRAPH_DEPTH))

    if settings.db_backend == "postgres":
        assert isinstance(session, AsyncSession)
        all_rows = await get_all_elements(project_id, session, limit=50_000)
        by_id = {e.id: e for e in all_rows}
        start = by_id.get(start_element_id)
        if start is None:
            return []

        seen: set[str] = set()
        frontier = [start_element_id]
        seen.add(start_element_id)
        for _ in range(d):
            next_front: list[str] = []
            for nid in frontier:
                el = by_id.get(nid)
                if el is None:
                    continue
                for nb in _postgres_neighbors(el, relationship_type, by_id):
                    if nb not in by_id:
                        continue
                    if nb not in seen:
                        seen.add(nb)
                        next_front.append(nb)
            frontier = next_front
            if not frontier:
                break
        return [by_id[i] for i in sorted(seen) if i in by_id]

    found: dict[str, Element] = {}

    if relationship_type == "ON_STOREY":
        res = await session.run(
            """
            MATCH (start:Element {id: $sid, project_id: $pid})-[:ON_STOREY]->(s:Storey)
            MATCH (o:Element)-[:ON_STOREY]->(s)
            WHERE o.project_id = $pid
            RETURN DISTINCT o
            """,
            sid=start_element_id,
            pid=project_id,
        )
        async for record in res:
            el = _neo4j_element_node_to_model(dict(record["o"]))
            found[el.id] = el
    else:
        rel = relationship_type
        res = await session.run(
            f"""
            MATCH (start:Element {{id: $sid, project_id: $pid}})
            MATCH path = (start)-[:{rel}*1..{d}]-(o:Element)
            WHERE o.project_id = $pid
            RETURN DISTINCT o
            """,
            sid=start_element_id,
            pid=project_id,
        )
        async for record in res:
            el = _neo4j_element_node_to_model(dict(record["o"]))
            found[el.id] = el

    inc_start = await session.run(
        """
        MATCH (s:Element {id: $sid, project_id: $pid})
        RETURN s LIMIT 1
        """,
        sid=start_element_id,
        pid=project_id,
    )
    sr = await inc_start.single()
    if sr:
        el = _neo4j_element_node_to_model(dict(sr["s"]))
        found.setdefault(el.id, el)

    return list(found.values())
