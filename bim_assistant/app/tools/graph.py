"""
app/tools/graph.py
Graph traversal queries (Neo4j-native traversal; Postgres uses column/list adjacency).
"""
from __future__ import annotations

from app.storage.database import get_session
from app.storage.repository import graph_traverse


async def tool_graph_traverse(
    project_id: str,
    start_element_id: str,
    relationship_type: str,
    depth: int = 2,
) -> dict:
    """Walk the building graph from an element up to ``depth`` hops."""
    try:
        async with get_session() as session:
            rows = await graph_traverse(
                project_id=project_id,
                start_element_id=start_element_id,
                relationship_type=relationship_type,
                depth=depth,
                session=session,
            )
    except ValueError as exc:
        return {"error": str(exc), "elements": []}

    elements = [
        {
            "id": r.id,
            "type": r.type,
            "name": r.name,
            "material": r.material,
            "volume": r.volume,
            "area": r.area,
            "storey": r.storey,
            "room": r.room,
            "located_in": r.located_in,
            "contained_by": r.contained_by,
            "connected_to": r.connected_to,
        }
        for r in rows
    ]
    return {
        "project_id": project_id,
        "start_element_id": start_element_id,
        "relationship_type": relationship_type,
        "depth": depth,
        "element_count": len(elements),
        "elements": elements,
    }
