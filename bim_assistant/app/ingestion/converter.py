"""
app/ingestion/converter.py
Converts native CAD formats (DWG, RVT, etc.) to IFC or STEP.

Strategy:
- RVT (Revit): call IfcOpenShell's Revit exporter or IFC export CLI if available
- DWG: use FreeCAD's Python API (if installed) or ODA File Converter (commercial)
- STEP: pass-through to STEP parser
- IFC: pass-through directly to ifc_parser

In a production environment you would add vendor-specific adapters here.
This module is intentionally thin — converters are swappable.
"""
from __future__ import annotations
import logging
import subprocess
import shutil
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FileFormat(str, Enum):
    IFC = "ifc"
    STEP = "step"
    STP = "stp"
    DWG = "dwg"
    DXF = "dxf"
    RVT = "rvt"
    UNKNOWN = "unknown"


def detect_format(file_path: Path) -> FileFormat:
    suffix = file_path.suffix.lower().lstrip(".")
    try:
        return FileFormat(suffix)
    except ValueError:
        return FileFormat.UNKNOWN


class ConversionResult:
    def __init__(self, output_path: Path, format: FileFormat, warnings: list[str] = None):
        self.output_path = output_path
        self.format = format
        self.warnings = warnings or []

    @property
    def success(self) -> bool:
        return self.output_path.exists()


def convert_to_ifc(
    input_path: Path,
    output_dir: Path,
    project_id: Optional[str] = None,
) -> ConversionResult:
    """
    Convert any supported CAD file to IFC.
    Returns the IFC path (may be the same file if already IFC).
    """
    fmt = detect_format(input_path)
    warnings: list[str] = []

    if fmt == FileFormat.IFC:
        logger.info("File is already IFC — no conversion needed.")
        return ConversionResult(input_path, FileFormat.IFC)

    output_dir.mkdir(parents=True, exist_ok=True)
    ifc_out = output_dir / f"{project_id or input_path.stem}.ifc"

    if fmt == FileFormat.RVT:
        result = _convert_rvt_to_ifc(input_path, ifc_out, warnings)
    elif fmt in (FileFormat.DWG, FileFormat.DXF):
        result = _convert_dwg_to_ifc(input_path, ifc_out, warnings)
    elif fmt in (FileFormat.STEP, FileFormat.STP):
        # STEP doesn't convert to IFC cleanly; return as-is for STEP parser
        logger.info("STEP file detected — skipping IFC conversion, will use STEP parser.")
        return ConversionResult(input_path, FileFormat.STEP, warnings)
    else:
        warnings.append(f"Unsupported format '{fmt}' — attempting pass-through.")
        return ConversionResult(input_path, fmt, warnings)

    return result


def _convert_rvt_to_ifc(
    input_path: Path, output_path: Path, warnings: list[str]
) -> ConversionResult:
    """
    Convert Revit (.rvt) to IFC.

    Production options:
    1. Revit IFC export via Dynamo script (Windows only)
    2. IfcOpenShell IFC-SPF writer (partial geometry)
    3. Third-party service (BIMcollab, Speckle, etc.)

    This implementation tries a subprocess call to 'revit_ifc_export' CLI
    (a placeholder — replace with your actual converter path).
    """
    revit_cli = shutil.which("revit_ifc_export")
    if revit_cli:
        try:
            subprocess.run(
                [revit_cli, str(input_path), str(output_path)],
                check=True, timeout=300,
                capture_output=True,
            )
            return ConversionResult(output_path, FileFormat.IFC, warnings)
        except subprocess.CalledProcessError as exc:
            warnings.append(f"Revit CLI conversion failed: {exc.stderr.decode()}")
    else:
        warnings.append(
            "No Revit CLI found. Install the Revit IFC export CLI or "
            "export to IFC manually from within Revit."
        )

    # Fallback: copy as-is and warn
    shutil.copy(input_path, output_path.with_suffix(".rvt"))
    return ConversionResult(
        output_path.with_suffix(".rvt"),
        FileFormat.RVT,
        warnings + ["Conversion skipped — returning original file."],
    )


def _convert_dwg_to_ifc(
    input_path: Path, output_path: Path, warnings: list[str]
) -> ConversionResult:
    """
    Convert DWG/DXF to IFC via FreeCAD Python API.

    FreeCAD must be installed and its lib directory on PYTHONPATH.
    See: https://wiki.freecad.org/Embedding_FreeCAD
    """
    try:
        import FreeCAD  # type: ignore
        import importIFC  # type: ignore   # FreeCAD IFC exporter

        doc = FreeCAD.openDocument(str(input_path))
        importIFC.export(doc.Objects, str(output_path))
        doc.close()
        return ConversionResult(output_path, FileFormat.IFC, warnings)

    except ImportError:
        warnings.append(
            "FreeCAD Python bindings not found. "
            "Install FreeCAD and add its lib dir to PYTHONPATH."
        )
    except Exception as exc:
        warnings.append(f"FreeCAD conversion error: {exc}")

    # Fallback: return original
    shutil.copy(input_path, output_path.with_suffix(".dwg"))
    return ConversionResult(
        output_path.with_suffix(".dwg"),
        FileFormat.DWG,
        warnings + ["DWG conversion skipped — returning original file."],
    )


def convert_step_to_elements(step_path: Path) -> list[dict]:
    """
    Parse a STEP file via PythonOCC (OpenCascade bindings).
    Returns a list of raw shape dicts (type, volume, bbox).
    Requires: conda install -c conda-forge pythonocc-core
    """
    try:
        from OCC.Core.STEPControl import STEPControl_Reader  # type: ignore
        from OCC.Core.BRep import BRep_Builder  # type: ignore
        from OCC.Core.BRepGProp import brepgprop_VolumeProperties  # type: ignore
        from OCC.Core.GProp import GProp_GProps  # type: ignore
        from OCC.Core.IFSelect import IFSelect_RetDone  # type: ignore

        reader = STEPControl_Reader()
        status = reader.ReadFile(str(step_path))
        if status != IFSelect_RetDone:
            raise RuntimeError(f"STEP reader error: status={status}")

        reader.TransferRoots()
        shape = reader.OneShape()

        # Basic volume extraction
        props = GProp_GProps()
        brepgprop_VolumeProperties(shape, props)
        volume = props.Mass()

        return [{"type": "step_solid", "volume": volume, "source": str(step_path)}]

    except ImportError:
        logger.warning(
            "PythonOCC not installed — STEP geometry extraction disabled. "
            "Install with: conda install -c conda-forge pythonocc-core"
        )
        return []
    except Exception as exc:
        logger.error("STEP parsing failed: %s", exc)
        return []
