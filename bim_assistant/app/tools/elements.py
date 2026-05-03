"""
app/tools/elements.py
Deterministic query tools — element retrieval.
These functions contain NO LLM logic. They query the DB and return
structured data that the agent layer formats for the user.
"""
from __future__ import annotations
from typing import Optional
from app.storage.database import get_session
from app.storage.repository import (
    get_elements_by_type,
    get_all_elements,
    get_element_by_id,
    get_material_summary,
)


async def tool_get_elements(project_id: str, element_type: Optional[str] = None) -> list[dict]:
    """
    Return all elements of a given type (or all elements if type is None).
    Maps to: get_elements(type) in the spec.
    """
    async with get_session() as session:
        if element_type:
            rows = await get_elements_by_type(project_id, element_type.lower(), session)
        else:
            rows = await get_all_elements(project_id, session)

    return [
        {
            "id": r.id,
            "type": r.type,
            "name": r.name,
            "material": r.material,
            "volume": r.volume,
            "area": r.area,
            "storey": r.storey,
            "room": r.room,
            "connected_to": r.connected_to,
        }
        for r in rows
    ]


async def tool_get_element_detail(project_id: str, element_id: str) -> Optional[dict]:
    """Return full detail of a single element including all properties."""
    async with get_session() as session:
        elem = await get_element_by_id(element_id, session)
    if elem is None or elem.project_id != project_id:
        return None
    return {
        "id": elem.id,
        "ifc_guid": elem.ifc_guid,
        "type": elem.type,
        "name": elem.name,
        "description": elem.description,
        "material": elem.material,
        "volume": elem.volume,
        "area": elem.area,
        "length": elem.length,
        "storey": elem.storey,
        "room": elem.room,
        "located_in": elem.located_in,
        "connected_to": elem.connected_to,
        "bounding_box": {
            "min": [elem.bbox_min_x, elem.bbox_min_y, elem.bbox_min_z],
            "max": [elem.bbox_max_x, elem.bbox_max_y, elem.bbox_max_z],
        } if elem.bbox_min_x is not None else None,
        "properties": elem.properties,
    }
