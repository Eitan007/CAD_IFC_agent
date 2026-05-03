"""
app/normalization/schema.py
Unified internal representation for BIM elements.
All layers exchange these models — never raw IFC objects.
"""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid


class BoundingBox(BaseModel):
    min_x: float = 0.0
    min_y: float = 0.0
    min_z: float = 0.0
    max_x: float = 0.0
    max_y: float = 0.0
    max_z: float = 0.0


class BuildingElement(BaseModel):
    """Normalised representation of a single BIM element."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ifc_guid: Optional[str] = None          # original IFC GlobalId
    type: str                               # wall | slab | door | beam | column …
    name: Optional[str] = None
    description: Optional[str] = None

    # Geometry / derived
    volume: Optional[float] = None          # m³
    area: Optional[float] = None            # m²
    length: Optional[float] = None          # m
    bounding_box: Optional[BoundingBox] = None

    # Material
    material: Optional[str] = None
    material_volume: Optional[float] = None  # m³ of the primary material

    # Location
    storey: Optional[str] = None            # "Level 1", "Basement"
    room: Optional[str] = None
    located_in: Optional[str] = None        # parent space/zone id

    # Relationships (ids of related elements)
    connected_to: list[str] = Field(default_factory=list)
    contains: list[str] = Field(default_factory=list)
    contained_by: Optional[str] = None

    # Raw properties blob for anything not explicitly mapped
    properties: dict[str, Any] = Field(default_factory=dict)

    # Source provenance
    source_file: Optional[str] = None
    project_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "wall_001",
                "type": "wall",
                "material": "concrete",
                "volume": 2.5,
                "area": 12.0,
                "connected_to": ["slab_01"],
                "located_in": "room_12",
                "storey": "Level 1",
                "properties": {"fire_rating": "REI 120", "load_bearing": True},
            }
        }


class BuildingModel(BaseModel):
    """Top-level container returned after parsing a file."""
    project_id: str
    source_file: str
    element_count: int
    elements: list[BuildingElement]
    parse_warnings: list[str] = Field(default_factory=list)


class MaterialQuantity(BaseModel):
    material: str
    total_volume: float         # m³
    total_area: Optional[float] = None  # m²
    element_count: int
    element_types: list[str]


class CostEstimate(BaseModel):
    project_id: str
    total_cost_usd: float
    breakdown: dict[str, float]  # material → cost_usd
    assumptions: list[str]


class ScheduleTask(BaseModel):
    task_id: str
    name: str
    element_types: list[str]
    duration_days: int
    depends_on: list[str] = Field(default_factory=list)
    start_day: Optional[int] = None
    end_day: Optional[int] = None


class ComplianceIssue(BaseModel):
    rule_id: str
    severity: str               # "error" | "warning" | "info"
    element_id: Optional[str]
    message: str
    suggestion: Optional[str] = None


class ComplianceReport(BaseModel):
    project_id: str
    rule_set: str
    passed: bool
    issues: list[ComplianceIssue]
