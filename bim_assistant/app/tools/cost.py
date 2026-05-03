"""
app/tools/cost.py
Deterministic cost estimation tool.

Prices are configurable via a JSON cost database (data/cost_db.json)
and fall back to reasonable industry defaults.
The LLM never participates in this calculation.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

from app.storage.database import get_session
from app.storage.repository import get_material_summary, get_all_elements
from app.normalization.schema import CostEstimate

logger = logging.getLogger(__name__)

# Default cost rates in USD/m³ by material keyword
DEFAULT_COST_DB: dict[str, float] = {
    "concrete": 120.0,
    "reinforced concrete": 180.0,
    "steel": 1_200.0,
    "timber": 350.0,
    "wood": 350.0,
    "glass": 800.0,
    "brick": 200.0,
    "masonry": 150.0,
    "aluminium": 2_500.0,
    "aluminum": 2_500.0,
    "gypsum": 60.0,
    "plasterboard": 60.0,
    "insulation": 80.0,
    "unknown": 100.0,  # fallback
}

# Labour multiplier on top of material cost
LABOUR_MULTIPLIER = 1.4

# Contingency
CONTINGENCY_PCT = 0.10


def _load_cost_db(path: Optional[Path] = None) -> dict[str, float]:
    if path is None:
        path = Path("data/cost_db.json")
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception as exc:
            logger.warning("Failed to load cost DB from %s: %s", path, exc)
    return DEFAULT_COST_DB


def _match_cost(material: str, cost_db: dict[str, float]) -> float:
    """Fuzzy-match a material name to a cost rate."""
    mat_lower = material.lower()
    # Exact match first
    if mat_lower in cost_db:
        return cost_db[mat_lower]
    # Substring match
    for key, rate in cost_db.items():
        if key in mat_lower or mat_lower in key:
            return rate
    return cost_db.get("unknown", 100.0)


async def tool_estimate_cost(project_id: str, cost_db_path: Optional[str] = None) -> dict:
    """
    Estimate total construction cost for a project.

    Calculation:
      material_cost = sum(volume_m3 * rate_per_m3) per material
      total = material_cost * LABOUR_MULTIPLIER * (1 + CONTINGENCY_PCT)

    Returns a CostEstimate dict.
    """
    cost_db = _load_cost_db(Path(cost_db_path) if cost_db_path else None)

    async with get_session() as session:
        mat_summary = await get_material_summary(project_id, session)

    if not mat_summary:
        return CostEstimate(
            project_id=project_id,
            total_cost_usd=0.0,
            breakdown={},
            assumptions=["No material data found for this project."],
        ).model_dump()

    breakdown: dict[str, float] = {}
    assumptions: list[str] = [
        f"Labour multiplier: {LABOUR_MULTIPLIER}x on material cost",
        f"Contingency: {int(CONTINGENCY_PCT * 100)}%",
        "Unit rates in USD/m³ from cost database",
    ]

    for row in mat_summary:
        material = row["material"] or "unknown"
        volume = float(row["total_volume"] or 0)
        rate = _match_cost(material, cost_db)
        mat_cost = volume * rate * LABOUR_MULTIPLIER
        breakdown[material] = round(mat_cost, 2)

    subtotal = sum(breakdown.values())
    contingency = subtotal * CONTINGENCY_PCT
    total = subtotal + contingency

    return CostEstimate(
        project_id=project_id,
        total_cost_usd=round(total, 2),
        breakdown={**breakdown, "_contingency": round(contingency, 2)},
        assumptions=assumptions,
    ).model_dump()
