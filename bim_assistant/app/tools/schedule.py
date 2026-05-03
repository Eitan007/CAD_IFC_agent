"""
app/tools/schedule.py
Deterministic construction schedule generator.

Uses a simple dependency graph + duration model based on element counts.
In production, swap out with a proper CPM/PERT library (e.g. python-gantt).
No LLM involvement.
"""
from __future__ import annotations
import logging
from typing import Optional

from app.storage.database import get_session
from app.storage.repository import get_all_elements
from app.normalization.schema import ScheduleTask

logger = logging.getLogger(__name__)

# Base duration in days per unit count for each work package
# (element_count / RATE = days, minimum 1 day)
DURATION_RATES: dict[str, float] = {
    "excavation": 50,       # 50 elements per day equivalent
    "foundations": 20,
    "structural_frame": 15,
    "concrete_works": 10,
    "masonry": 8,
    "roofing": 12,
    "windows_doors": 25,
    "mep_rough": 20,
    "insulation": 30,
    "finishes": 20,
    "mep_finish": 25,
}

# Map element types to work packages
ELEMENT_TO_PACKAGE: dict[str, str] = {
    "slab": "concrete_works",
    "wall": "masonry",
    "column": "structural_frame",
    "beam": "structural_frame",
    "door": "windows_doors",
    "window": "windows_doors",
    "stair": "concrete_works",
    "roof": "roofing",
    "space": "finishes",
    "furniture": "finishes",
    "generic_element": "mep_rough",
}

# Dependency graph: package → list of packages it depends on
DEPENDENCIES: dict[str, list[str]] = {
    "excavation": [],
    "foundations": ["excavation"],
    "structural_frame": ["foundations"],
    "concrete_works": ["structural_frame"],
    "masonry": ["structural_frame"],
    "roofing": ["structural_frame", "masonry"],
    "windows_doors": ["masonry"],
    "mep_rough": ["structural_frame"],
    "insulation": ["masonry", "roofing"],
    "finishes": ["insulation", "windows_doors", "mep_rough"],
    "mep_finish": ["finishes"],
}

PACKAGE_NAMES: dict[str, str] = {
    "excavation": "Site preparation & excavation",
    "foundations": "Foundation works",
    "structural_frame": "Structural frame (columns, beams)",
    "concrete_works": "Concrete works (slabs, stairs)",
    "masonry": "Masonry & wall construction",
    "roofing": "Roofing",
    "windows_doors": "Windows & doors installation",
    "mep_rough": "MEP rough-in",
    "insulation": "Insulation & weatherproofing",
    "finishes": "Interior finishes & fixtures",
    "mep_finish": "MEP commissioning & finishing",
}


def _compute_early_start(
    package: str,
    tasks: dict[str, ScheduleTask],
    memo: dict[str, int],
) -> int:
    if package in memo:
        return memo[package]
    deps = DEPENDENCIES.get(package, [])
    if not deps:
        memo[package] = 0
        return 0
    start = max(
        _compute_early_start(dep, tasks, memo) + (tasks[dep].duration_days if dep in tasks else 0)
        for dep in deps
    )
    memo[package] = start
    return start


async def tool_generate_schedule(project_id: str) -> list[dict]:
    """
    Generate a construction schedule as an ordered list of tasks.
    Returns list of ScheduleTask dicts with start_day and end_day.
    """
    async with get_session() as session:
        all_elems = await get_all_elements(project_id, session)

    # Count elements per work package
    package_counts: dict[str, int] = {pkg: 0 for pkg in DURATION_RATES}
    for elem in all_elems:
        pkg = ELEMENT_TO_PACKAGE.get(elem.type)
        if pkg:
            package_counts[pkg] = package_counts.get(pkg, 0) + 1

    # Always include excavation and foundations even with no elements
    package_counts.setdefault("excavation", 1)
    package_counts.setdefault("foundations", 1)

    # Build tasks with durations
    tasks: dict[str, ScheduleTask] = {}
    for i, (pkg, name) in enumerate(PACKAGE_NAMES.items()):
        count = package_counts.get(pkg, 0)
        rate = DURATION_RATES.get(pkg, 20)
        duration = max(1, int(count / rate) if count > 0 else 5)

        tasks[pkg] = ScheduleTask(
            task_id=f"T{i+1:02d}",
            name=name,
            element_types=[k for k, v in ELEMENT_TO_PACKAGE.items() if v == pkg],
            duration_days=duration,
            depends_on=[
                tasks[dep].task_id
                for dep in DEPENDENCIES.get(pkg, [])
                if dep in tasks
            ],
        )

    # Forward-pass: compute start/end days
    memo: dict[str, int] = {}
    for pkg, task in tasks.items():
        start = _compute_early_start(pkg, tasks, memo)
        task.start_day = start
        task.end_day = start + task.duration_days

    # Sort by start day
    result = sorted(tasks.values(), key=lambda t: t.start_day or 0)

    total_days = max(t.end_day for t in result if t.end_day)
    logger.info(
        "Generated schedule: %d tasks, total %d days (project=%s)",
        len(result), total_days, project_id,
    )

    return [t.model_dump() for t in result]
