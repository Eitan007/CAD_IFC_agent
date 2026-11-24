"""Server-side STEP/STP to GLB conversion using Open Cascade."""
from __future__ import annotations

import asyncio
from pathlib import Path


class StepPreviewError(RuntimeError):
    """A STEP file could not become a browser-friendly 3D model."""


def _read_step_shape(step_path: Path):
    try:
        from OCP.IFSelect import IFSelect_RetDone  # noqa: PLC0415
        from OCP.STEPControl import STEPControl_Reader  # noqa: PLC0415
    except ImportError as exc:
        raise StepPreviewError(
            "STEP preview engine is not installed. Install cadquery-ocp."
        ) from exc

    if not step_path.is_file():
        raise FileNotFoundError(str(step_path))

    reader = STEPControl_Reader()
    if reader.ReadFile(str(step_path)) != IFSelect_RetDone:
        raise StepPreviewError("This STEP/STP file could not be read.")
    reader.TransferRoots()
    shape = reader.OneShape()
    if shape.IsNull():
        raise StepPreviewError("This STEP/STP file does not contain a 3D shape.")
    return shape


def read_step_shape(step_path: Path):
    """Load a STEP shape for lightweight metadata extraction."""
    return _read_step_shape(step_path)


def convert_step_file_to_glb(step_path: Path, glb_out: Path) -> None:
    """Tessellate a STEP/STP solid and save it as a GLB browser model."""
    import numpy as np  # noqa: PLC0415
    import trimesh  # noqa: PLC0415
    from OCP.BRep import BRep_Tool  # noqa: PLC0415
    from OCP.BRepMesh import BRepMesh_IncrementalMesh  # noqa: PLC0415
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED  # noqa: PLC0415
    from OCP.TopExp import TopExp_Explorer  # noqa: PLC0415
    from OCP.TopLoc import TopLoc_Location  # noqa: PLC0415
    from OCP.TopoDS import TopoDS  # noqa: PLC0415

    shape = _read_step_shape(step_path)
    # 0.1 mm is a good balance: smooth enough for CAD, small enough for the web.
    BRepMesh_IncrementalMesh(shape, 0.1, False, 0.5, True)

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face(explorer.Current())
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, location)
        if triangulation is not None:
            offset = len(vertices)
            transform = location.Transformation()
            for index in range(1, triangulation.NbNodes() + 1):
                point = triangulation.Node(index).Transformed(transform)
                vertices.append((point.X(), point.Y(), point.Z()))
            for index in range(1, triangulation.NbTriangles() + 1):
                a, b, c = triangulation.Triangle(index).Get()
                if face.Orientation() == TopAbs_REVERSED:
                    b, c = c, b
                faces.append((offset + a - 1, offset + b - 1, offset + c - 1))
        explorer.Next()

    if not vertices or not faces:
        raise StepPreviewError("This STEP/STP file has no visible 3D surfaces.")

    mesh = trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=np.float64),
        faces=np.asarray(faces, dtype=np.int64),
        process=False,
    )
    mesh.remove_unreferenced_vertices()
    glb_out.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(glb_out), file_type="glb")


async def run_step_glb_export(step_path: Path, glb_out: Path) -> None:
    """Run Open Cascade conversion outside FastAPI's event loop."""
    await asyncio.to_thread(convert_step_file_to_glb, step_path, glb_out)
