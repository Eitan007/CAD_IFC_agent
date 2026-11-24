"""Build the tiny STEP bolt demo and its checked-in GLB preview."""
from __future__ import annotations

import math
from pathlib import Path

from OCP.BRep import BRep_Builder
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeWire
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec

from app.ingestion.step_to_glb import convert_step_file_to_glb


def make_bolt():
    """Make a simple hex-head bolt: shaft + six-sided head."""
    shaft = BRepPrimAPI_MakeCylinder(3, 28).Shape()

    polygon = BRepBuilderAPI_MakePolygon()
    for index in range(6):
        angle = math.tau * index / 6
        polygon.Add(gp_Pnt(7 * math.cos(angle), 7 * math.sin(angle), 28))
    polygon.Close()
    head_face = BRepBuilderAPI_MakeFace(polygon.Wire()).Face()
    head = BRepPrimAPI_MakePrism(head_face, gp_Vec(0, 0, 6)).Shape()

    bolt = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(bolt)
    builder.Add(bolt, shaft)
    builder.Add(bolt, head)
    return bolt


def make_threaded_bolt():
    """Make a second bolt with visible helical thread-ridge geometry."""
    bolt = make_bolt()
    builder = BRep_Builder()

    # A small round profile follows a helix: this is real spiral geometry, not a label.
    radius, start_z, threaded_length, turns = 3.15, 1.0, 24.5, 13
    segments = turns * 24
    spine_points = BRepBuilderAPI_MakePolygon()
    for index in range(segments + 1):
        fraction = index / segments
        angle = math.tau * turns * fraction
        spine_points.Add(gp_Pnt(radius * math.cos(angle), radius * math.sin(angle), start_z + threaded_length * fraction))
    spine = spine_points.Wire()

    first = gp_Pnt(radius, 0, start_z)
    tangent = gp_Dir(0, radius * math.tau * turns / threaded_length, 1)
    profile_edge = BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(first, tangent), 0.32)).Edge()
    profile = BRepBuilderAPI_MakeWire(profile_edge).Wire()
    thread_ridge = BRepOffsetAPI_MakePipe(spine, profile).Shape()
    builder.Add(bolt, thread_ridge)
    return bolt


def write_step(shape, step_path: Path, glb_path: Path) -> None:
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    if writer.Write(str(step_path)) != 1:
        raise RuntimeError(f"Could not write {step_path.name}.")
    convert_step_file_to_glb(step_path, glb_path)


def main() -> None:
    samples = Path(__file__).resolve().parents[1] / "samples"
    samples.mkdir(parents=True, exist_ok=True)
    plain_step = samples / "HexBolt.step"
    plain_glb = samples / "HexBolt.glb"
    threaded_step = samples / "ThreadedHexBolt.step"
    threaded_glb = samples / "ThreadedHexBolt.glb"

    write_step(make_bolt(), plain_step, plain_glb)
    write_step(make_threaded_bolt(), threaded_step, threaded_glb)
    print(f"Created {plain_step}, {plain_glb}, {threaded_step}, and {threaded_glb}")


if __name__ == "__main__":
    main()
