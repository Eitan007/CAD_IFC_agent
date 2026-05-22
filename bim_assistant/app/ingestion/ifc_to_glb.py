"""
Server-side IFC → GLB export for browser viewing.
Uses IfcOpenShell geometry tessellation + trimesh Scene export (per-product node names = express IDs).
"""
from __future__ import annotations

import asyncio
import logging
import multiprocessing
from pathlib import Path

logger = logging.getLogger(__name__)


def _geom_settings():  # lazy import
    import ifcopenshell.geom as geom  # noqa: PLC0415

    s = geom.settings()
    s.set(s.USE_WORLD_COORDS, True)
    return s


def _mesh_from_shape(shape) -> "object | None":
    import numpy as np  # noqa: PLC0415
    import trimesh  # noqa: PLC0415

    try:
        g = shape.geometry
        v = getattr(g, "verts", None)
        f = getattr(g, "faces", None)
        if not v or not f:
            return None
        arr_v = np.asarray(v, dtype=np.float64).reshape(-1, 3)
        arr_f = np.asarray(f, dtype=np.int64).reshape(-1, 3)
        if arr_v.size == 0 or arr_f.size == 0:
            return None
        return trimesh.Trimesh(vertices=arr_v, faces=arr_f, process=False)
    except Exception as exc:
        logger.debug("IFC→GLB: skip shape (%s)", exc)
        return None


def _scene_via_products(model, settings) -> "object | None":
    import ifcopenshell.geom as geom  # noqa: PLC0415
    import trimesh  # noqa: PLC0415

    scene = trimesh.Scene()
    count = 0
    for product in model.by_type("IfcProduct"):
        if not getattr(product, "Representation", None):
            continue
        try:
            shape = geom.create_shape(settings, product)
            mesh = _mesh_from_shape(shape)
            if mesh is None:
                continue
            scene.add_geometry(mesh, node_name=str(product.id()))
            count += 1
        except Exception:
            continue
    return scene if count else None


def _scene_via_iterator(model, settings) -> "object | None":
    import ifcopenshell.geom as geom  # noqa: PLC0415
    import trimesh  # noqa: PLC0415

    iterator = None
    try:
        iterator = geom.iterator(settings, model, multiprocessing.cpu_count())
    except TypeError:
        try:
            iterator = geom.iterator(settings, model)
        except Exception as exc:
            logger.debug("IFC→GLB: iterator unavailable (%s)", exc)
            return None

    if iterator is None or not iterator.initialize():
        return None

    scene = trimesh.Scene()
    idx = 0
    while True:
        shape = iterator.get()
        mesh = _mesh_from_shape(shape)
        if mesh is not None:
            express_id = getattr(shape, "id", None)
            node_name = str(express_id) if express_id is not None else f"mesh_{idx}"
            scene.add_geometry(mesh, node_name=node_name)
            idx += 1
        if not iterator.next():
            break
    return scene if idx else None


def convert_ifc_file_to_glb(ifc_path: Path, glb_out: Path) -> None:
    """
    Tessellates IFC geometry into a GLB scene (nodes named by IFC express ID when possible).
    Raises RuntimeError when no meshes could be generated.
    """
    import ifcopenshell  # noqa: PLC0415

    if not ifc_path.is_file():
        raise FileNotFoundError(str(ifc_path))

    glb_out = Path(glb_out)
    model = ifcopenshell.open(str(ifc_path))
    settings = _geom_settings()

    scene = _scene_via_iterator(model, settings)
    if scene is None:
        logger.info("IFC→GLB: iterator empty, falling back to products (%s)", ifc_path)
        scene = _scene_via_products(model, settings)

    if scene is None:
        raise RuntimeError(f"No tessellated geometry for {ifc_path}")

    glb_out.parent.mkdir(parents=True, exist_ok=True)
    scene.export(str(glb_out))


def glb_derivative_path(ifc_path: Path) -> Path:
    """Same directory as IFC, stem preserved, `.glb` suffix."""
    return Path(ifc_path).with_suffix(".glb")


def project_glb_path(processed_dir: Path, project_id: str) -> Path:
    """Canonical GLB location under processed_dir."""
    return processed_dir / f"{project_id}.glb"


def resolve_source_ifc_path(source_file_str: str) -> Path | None:
    """Return path only when the ingest source is an IFC on disk."""
    p = Path(source_file_str)
    try:
        p = p.resolve()
    except OSError:
        return None
    if p.suffix.lower() != ".ifc":
        return None
    if not p.is_file():
        return None
    return p


async def run_ifc_glb_export(ifc_path: Path, glb_out: Path) -> None:
    """Runs conversion in a thread pool."""
    await asyncio.to_thread(convert_ifc_file_to_glb, ifc_path, glb_out)
