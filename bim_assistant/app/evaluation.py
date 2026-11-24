"""Deterministic evaluation helpers for source-aware agent answers."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.services.deterministic_checks import STEP_FORMATS, source_format_for_path

_STEP_FACT_TERMS = ("thread pitch", "thread class", "iso", "din", "material grade")
_UNKNOWN_WORDS = ("unknown", "not supplied", "not provided", "not available", "cannot tell", "can't tell", "does not")


def _unsupported_step_claims(answer: str) -> list[str]:
    """Find affirmative STEP-only facts that raw geometry cannot prove."""
    claims: list[str] = []
    for sentence in re.split(r"[.!?\n]+", answer.lower()):
        if any(term in sentence for term in _STEP_FACT_TERMS) and not any(word in sentence for word in _UNKNOWN_WORDS):
            claims.append(sentence.strip()[:160])
    return claims


def score_answer(source_format: str, answer: str) -> dict[str, Any]:
    """Score a concrete answer using transparent, repeatable rules out of 100."""
    normalized_format = source_format.lower()
    checks: list[dict[str, Any]] = []

    if normalized_format in STEP_FORMATS:
        source_words = ("step", "stp", "cad", "geometry")
        knows_source = any(word in answer.lower() for word in source_words)
        claims = _unsupported_step_claims(answer)
        checks.extend(
            [
                {
                    "name": "Names the CAD/geometry context",
                    "passed": knows_source,
                    "points": 40 if knows_source else 0,
                },
                {
                    "name": "Does not invent missing STEP properties",
                    "passed": not claims,
                    "points": 60 if not claims else 0,
                    "detail": claims[0] if claims else None,
                },
            ]
        )
    else:
        has_answer = bool(answer.strip())
        checks.append(
            {"name": "Returns a non-empty answer", "passed": has_answer, "points": 100 if has_answer else 0}
        )

    return {
        "source_format": normalized_format,
        "score": sum(check["points"] for check in checks),
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
    }


def score_sample_files(sample_paths: list[Path]) -> dict[str, Any]:
    """Score real bundled demo files and their preview sidecars on disk."""
    cases: list[dict[str, Any]] = []
    for path in sample_paths:
        source_format = source_format_for_path(path)
        preview = path.with_suffix(".glb")
        checks = [
            {"name": "Source file exists", "passed": path.is_file() and path.stat().st_size > 0},
            {
                "name": "CAD preview exists",
                "passed": source_format not in STEP_FORMATS or (preview.is_file() and preview.stat().st_size > 0),
            },
        ]
        score = round(sum(100 for check in checks if check["passed"]) / len(checks))
        cases.append({"name": path.name, "score": score, "passed": all(check["passed"] for check in checks), "checks": checks})
    return {"cases": cases, "average_score": round(sum(case["score"] for case in cases) / len(cases)) if cases else 0}
