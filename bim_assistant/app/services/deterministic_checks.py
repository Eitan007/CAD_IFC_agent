"""Small, repeatable checks around the model-processing workflow."""
from __future__ import annotations

from pathlib import Path
from typing import Any

SUPPORTED_FORMATS = {"ifc", "step", "stp"}
STEP_FORMATS = {"step", "stp"}


def source_format_for_path(path: Path | None) -> str:
    """Return the source format name used by prompts, checks, and telemetry."""
    if path is None:
        return "unknown"
    suffix = path.suffix.lower().lstrip(".")
    return suffix if suffix in SUPPORTED_FORMATS else "unknown"


def source_data_contract(source_format: str) -> str:
    """Explain, in plain language, what the deterministic pipeline can know."""
    if source_format == "ifc":
        return "IFC: structured BIM data is available when it was present in the source file."
    if source_format in STEP_FORMATS:
        return "STEP/STP: CAD geometry is available; dimensions, threads, materials, and standards are unknown unless the source explicitly supplies them."
    return "Unknown source format: no data assumptions are allowed."


def build_pipeline_checks(
    source_format: str,
    *,
    graph_ready: bool,
    preview_status: str | None,
    element_count: int | None,
) -> list[dict[str, Any]]:
    """Return deterministic, inspectable checks for a processed project."""
    supported = source_format in SUPPORTED_FORMATS
    checks: list[dict[str, Any]] = [
        {
            "id": "supported_source",
            "name": "Supported source file",
            "passed": supported,
            "detail": f"Detected {source_format.upper() if source_format != 'unknown' else 'an unknown format'}.",
        },
        {
            "id": "source_data_boundary",
            "name": "Correct data boundary",
            "passed": supported,
            "detail": source_data_contract(source_format),
        },
        {
            "id": "structured_model_ready",
            "name": "Structured model ready",
            "passed": graph_ready,
            "detail": (
                f"{element_count or 0} extracted element(s) are ready for deterministic tools."
                if graph_ready
                else "The processing pipeline has not finished yet."
            ),
        },
    ]

    if source_format in STEP_FORMATS:
        ready = preview_status == "ready"
        checks.append(
            {
                "id": "cad_preview_ready",
                "name": "Browser 3D preview ready",
                "passed": ready,
                "detail": "GLB preview is ready." if ready else "The CAD-to-GLB preview is still pending or failed.",
            }
        )
    return checks
