"""
Shared ingestion pipeline used by /process and /api/projects/*/process.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.config import get_settings
from app.ingestion.converter import convert_to_ifc, detect_format, FileFormat
from app.ingestion.ifc_parser import parse_ifc
from app.ingestion.converter import convert_step_to_elements
from app.normalization.schema import BuildingModel, BuildingElement

logger = logging.getLogger(__name__)


async def run_ingestion_pipeline(input_path: Path, project_id: str) -> BuildingModel:
    """
    Full ingestion pipeline:
    1. Detect format
    2. Convert if needed
    3. Parse
    4. Return BuildingModel
    """
    processed_dir = Path(get_settings().processed_dir)
    fmt = detect_format(input_path)

    if fmt == FileFormat.IFC:
        logger.info("Direct IFC parse: %s", input_path)
        return parse_ifc(input_path, project_id=project_id)

    if fmt in (FileFormat.STEP, FileFormat.STP):
        logger.info("STEP parse: %s", input_path)
        raw_elements = convert_step_to_elements(input_path)
        elements = [
            BuildingElement(
                type=e.get("type", "step_solid"),
                volume=e.get("volume"),
                source_file=str(input_path),
                project_id=project_id,
            )
            for e in raw_elements
        ]
        return BuildingModel(
            project_id=project_id,
            source_file=str(input_path),
            element_count=len(elements),
            elements=elements,
            parse_warnings=["STEP geometry parsed without semantic element types."],
        )

    logger.info("Native CAD: converting %s → IFC", input_path)
    result = convert_to_ifc(input_path, processed_dir, project_id=project_id)
    if result.format == FileFormat.IFC and result.output_path.exists():
        model = parse_ifc(result.output_path, project_id=project_id)
        model.parse_warnings.extend(result.warnings)
        return model

    return BuildingModel(
        project_id=project_id,
        source_file=str(input_path),
        element_count=0,
        elements=[],
        parse_warnings=result.warnings
        + [
            f"Could not convert {input_path.suffix} to IFC. "
            "Install the required converter and retry."
        ],
    )
