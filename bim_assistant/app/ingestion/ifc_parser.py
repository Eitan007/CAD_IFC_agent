"""
app/ingestion/ifc_parser.py
Parses IFC files using IfcOpenShell and produces BuildingElement objects.

Design decisions:
- Every field access is wrapped in a safe getter — real-world IFC files
  frequently have null, missing, or malformed properties.
- Geometry extraction is best-effort; missing geometry emits a warning
  rather than crashing the pipeline.
- The parser never returns raw IfcOpenShell objects upstream.
"""
from __future__ import annotations
import logging
import uuid
from pathlib import Path
from typing import Optional

try:
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.element as ifc_util
    import ifcopenshell.util.unit as ifc_unit
    IFC_AVAILABLE = True
except ImportError:
    IFC_AVAILABLE = False
    logging.warning("IfcOpenShell not installed — IFC parsing disabled.")

from app.normalization.schema import BuildingElement, BuildingModel, BoundingBox

logger = logging.getLogger(__name__)

# Map IFC class names → friendly type labels
IFC_TYPE_MAP: dict[str, str] = {
    "IfcWall": "wall",
    "IfcWallStandardCase": "wall",
    "IfcSlab": "slab",
    "IfcBeam": "beam",
    "IfcColumn": "column",
    "IfcDoor": "door",
    "IfcWindow": "window",
    "IfcStair": "stair",
    "IfcRoof": "roof",
    "IfcSpace": "space",
    "IfcBuildingStorey": "storey",
    "IfcBuilding": "building",
    "IfcFurnishingElement": "furniture",
    "IfcBuildingElementProxy": "generic_element",
}

GEOMETRY_SETTINGS = None


def _get_geom_settings():
    """Lazy-init geometry settings (thread-safe, expensive)."""
    global GEOMETRY_SETTINGS
    if GEOMETRY_SETTINGS is None and IFC_AVAILABLE:
        s = ifcopenshell.geom.settings()
        s.set(s.USE_WORLD_COORDS, True)
        GEOMETRY_SETTINGS = s
    return GEOMETRY_SETTINGS


def _safe(obj, *attrs, default=None):
    """
    Safely traverse a chain of attributes.
    Example: _safe(product, "HasAssociations", 0, "RelatingMaterial", "Name")
    """
    try:
        val = obj
        for attr in attrs:
            if val is None:
                return default
            if isinstance(attr, int):
                val = val[attr] if hasattr(val, "__getitem__") else default
            else:
                val = getattr(val, attr, default)
        return val if val is not None else default
    except Exception:
        return default


def _extract_material(product) -> Optional[str]:
    """Best-effort material extraction from IFC associations."""
    try:
        for association in _safe(product, "HasAssociations") or []:
            if association.is_a("IfcRelAssociatesMaterial"):
                relating = association.RelatingMaterial
                if relating is None:
                    continue
                if relating.is_a("IfcMaterial"):
                    return relating.Name
                if relating.is_a("IfcMaterialLayerSetUsage"):
                    layers = _safe(relating, "ForLayerSet", "MaterialLayers") or []
                    if layers:
                        return _safe(layers[0], "Material", "Name", default="unknown")
                if relating.is_a("IfcMaterialList"):
                    materials = _safe(relating, "Materials") or []
                    if materials:
                        return materials[0].Name
    except Exception as exc:
        logger.debug("Material extraction failed: %s", exc)
    return None


def _extract_storey(product, ifc_file) -> Optional[str]:
    """Walk containment tree upward to find the building storey."""
    try:
        for rel in _safe(product, "ContainedInStructure") or []:
            container = _safe(rel, "RelatingStructure")
            if container and container.is_a("IfcBuildingStorey"):
                return _safe(container, "Name", default="unknown_storey")
    except Exception:
        pass
    return None


def _extract_connected_ids(product) -> list[str]:
    """Return GUIDs of elements directly connected to this product."""
    connected = []
    try:
        for rel in _safe(product, "ConnectedTo") or []:
            related = _safe(rel, "RelatedElement")
            if related:
                connected.append(_safe(related, "GlobalId", default=str(uuid.uuid4())))
    except Exception:
        pass
    return connected


def _compute_geometry(product, ifc_file) -> tuple[Optional[float], Optional[float], Optional[BoundingBox]]:
    """
    Attempt to compute volume, area, and bounding box via IfcOpenShell geometry.
    Returns (volume, area, bbox) — any can be None on failure.
    """
    volume = area = None
    bbox = None
    settings = _get_geom_settings()
    if settings is None:
        return volume, area, bbox

    try:
        shape = ifcopenshell.geom.create_shape(settings, product)
        verts = shape.geometry.verts
        if verts:
            xs = verts[0::3]
            ys = verts[1::3]
            zs = verts[2::3]
            bbox = BoundingBox(
                min_x=min(xs), min_y=min(ys), min_z=min(zs),
                max_x=max(xs), max_y=max(ys), max_z=max(zs),
            )
            # Rough bounding-box volume as fallback
            volume = (bbox.max_x - bbox.min_x) * (bbox.max_y - bbox.min_y) * (bbox.max_z - bbox.min_z)
    except Exception as exc:
        logger.debug("Geometry extraction skipped for %s: %s", _safe(product, "GlobalId"), exc)

    # Prefer Qto-derived quantities when available
    try:
        psets = ifc_util.get_psets(product)
        for qset_name, props in psets.items():
            if "Qto" in qset_name or "BaseQuantities" in qset_name:
                volume = float(props.get("NetVolume") or props.get("GrossVolume") or volume or 0) or None
                area = float(props.get("NetSideArea") or props.get("GrossArea") or area or 0) or None
    except Exception:
        pass

    return volume, area, bbox


def parse_ifc(file_path: str | Path, project_id: Optional[str] = None) -> BuildingModel:
    """
    Parse an IFC file into a BuildingModel.

    Args:
        file_path: Path to the .ifc file.
        project_id: Optional project identifier; generated if not provided.

    Returns:
        BuildingModel with all extracted elements.

    Raises:
        RuntimeError: If IfcOpenShell is not installed.
        FileNotFoundError: If the file doesn't exist.
    """
    if not IFC_AVAILABLE:
        raise RuntimeError(
            "IfcOpenShell is not installed. Install via: "
            "conda install -c conda-forge ifcopenshell"
        )

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"IFC file not found: {file_path}")

    project_id = project_id or str(uuid.uuid4())
    warnings: list[str] = []

    logger.info("Parsing IFC file: %s (project=%s)", file_path, project_id)

    try:
        ifc_file = ifcopenshell.open(str(file_path))
    except Exception as exc:
        raise RuntimeError(f"Failed to open IFC file: {exc}") from exc

    elements: list[BuildingElement] = []
    processed_types = set(IFC_TYPE_MAP.keys())

    for ifc_type, friendly_type in IFC_TYPE_MAP.items():
        products = ifc_file.by_type(ifc_type)
        logger.debug("Processing %d %s elements", len(products), ifc_type)

        for product in products:
            try:
                guid = _safe(product, "GlobalId", default=str(uuid.uuid4()))
                name = _safe(product, "Name")
                desc = _safe(product, "Description")
                material = _extract_material(product)
                storey = _extract_storey(product, ifc_file)
                connected = _extract_connected_ids(product)
                volume, area, bbox = _compute_geometry(product, ifc_file)

                # Collect all Pset properties into the blob
                raw_props: dict = {}
                try:
                    raw_props = ifc_util.get_psets(product)
                except Exception:
                    pass

                elem = BuildingElement(
                    id=guid,
                    ifc_guid=guid,
                    type=friendly_type,
                    name=name,
                    description=desc,
                    material=material,
                    volume=volume,
                    area=area,
                    bounding_box=bbox,
                    storey=storey,
                    connected_to=connected,
                    properties=raw_props,
                    source_file=str(file_path),
                    project_id=project_id,
                )
                elements.append(elem)

            except Exception as exc:
                guid_str = _safe(product, "GlobalId", default="unknown")
                msg = f"Skipped element {ifc_type}/{guid_str}: {exc}"
                logger.warning(msg)
                warnings.append(msg)

    logger.info(
        "IFC parse complete: %d elements, %d warnings (project=%s)",
        len(elements), len(warnings), project_id,
    )

    return BuildingModel(
        project_id=project_id,
        source_file=str(file_path),
        element_count=len(elements),
        elements=elements,
        parse_warnings=warnings,
    )
