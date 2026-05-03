"""
app/tools/quantities.py
Deterministic material quantity extraction.
"""
from __future__ import annotations
from app.storage.database import get_session
from app.storage.repository import get_material_summary, get_elements_by_type, get_all_elements
from app.normalization.schema import MaterialQuantity


async def tool_get_material_quantities(project_id: str) -> list[dict]:
    """
    Aggregate material quantities across the whole project.
    Returns: [{material, total_volume, total_area, element_count, element_types}]
    """
    async with get_session() as session:
        summary = await get_material_summary(project_id, session)

    # Also collect which element types use each material
    async with get_session() as session:
        all_elems = await get_all_elements(project_id, session)

    mat_types: dict[str, set[str]] = {}
    for e in all_elems:
        if e.material:
            mat_types.setdefault(e.material, set()).add(e.type)

    results = []
    for row in summary:
        mat = row["material"]
        results.append(
            MaterialQuantity(
                material=mat or "unknown",
                total_volume=round(float(row["total_volume"] or 0), 4),
                total_area=round(float(row["total_area"] or 0), 4) if row["total_area"] else None,
                element_count=int(row["element_count"]),
                element_types=sorted(mat_types.get(mat, [])),
            ).model_dump()
        )

    # Sort by total volume descending
    results.sort(key=lambda x: x["total_volume"], reverse=True)
    return results


async def tool_get_element_counts(project_id: str) -> dict[str, int]:
    """
    Return a count of each element type in the project.
    Useful for quick overview queries.
    """
    async with get_session() as session:
        all_elems = await get_all_elements(project_id, session)

    counts: dict[str, int] = {}
    for e in all_elems:
        counts[e.type] = counts.get(e.type, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))
