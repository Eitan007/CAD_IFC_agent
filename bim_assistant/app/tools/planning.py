"""
Construction planning tools (BOQ, lookahead, exports, plan vs actual).

Deterministic; builds on IFC-derived element data and the existing schedule generator.
"""
from __future__ import annotations

import csv
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.config import get_settings
from app.normalization.schema import BillOfQuantitiesLine, ConstructionObjectSchema, ConstructionTaskSchema
from app.services.planning_store import load_context
from app.storage.database import get_session
from app.storage.repository import get_all_elements
from app.tools.compliance import tool_check_compliance
from app.tools.cost import tool_estimate_cost
from app.tools.schedule import PACKAGE_NAMES, tool_generate_schedule

logger = logging.getLogger(__name__)
settings = get_settings()

# Rough CSI MasterFormat division hints for BOQ / reporting
_ELEMENT_CSI_HINT: dict[str, str] = {
    "wall": "04",
    "slab": "03",
    "column": "03",
    "beam": "03",
    "stair": "03",
    "roof": "07",
    "door": "08",
    "window": "08",
    "space": "09",
    "furniture": "12",
    "generic_element": "00",
}

_NAME_TO_PACKAGE_KEY: dict[str, str] = {v: k for k, v in PACKAGE_NAMES.items()}

_PACKAGE_CREW: dict[str, tuple[str, int]] = {
    "excavation": ("CREW_SITE", 6),
    "foundations": ("CREW_CONCRETE", 8),
    "structural_frame": ("CREW_STEEL", 10),
    "concrete_works": ("CREW_CONCRETE", 8),
    "masonry": ("CREW_MASON", 6),
    "roofing": ("CREW_ENVELOPE", 5),
    "windows_doors": ("CREW_GLAZING", 4),
    "mep_rough": ("CREW_MEP", 6),
    "insulation": ("CREW_ENVELOPE", 4),
    "finishes": ("CREW_FINISHER", 8),
    "mep_finish": ("CREW_MEP", 4),
}


def _boq_unit_for_type(element_type: str) -> str:
    floors = {"slab", "roof"}
    linear = {"wall", "beam"}
    if element_type in ("door", "window", "column", "stair"):
        return "ea"
    if element_type in floors:
        return "m2"
    if element_type in linear:
        return "m3"
    return "m3"


async def tool_generate_boq(project_id: str) -> dict[str, Any]:
    """Bill of quantities from stored elements (grouped type + material)."""
    async with get_session() as session:
        elems = await get_all_elements(project_id, session)

    groups: dict[tuple[str, str | None], list[Any]] = defaultdict(list)
    for e in elems:
        key = (e.type or "unknown", e.material)
        groups[key].append(e)

    lines: list[dict] = []
    for (etype, material), els in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1] or "")):
        unit = _boq_unit_for_type(etype)
        count = len(els)
        if unit == "ea":
            qty = float(count)
        elif unit == "m2":
            qty = sum(float(e.area or 0) for e in els)
        else:
            qty = sum(float(e.volume or e.material_volume or 0) for e in els)

        desc = f"{etype.replace('_', ' ').title()} — {material or 'unspecified'}"
        code = f"BOQ-{etype.upper()[:4]}-{hash((etype, material)) % 10_000:04d}"
        csi = _ELEMENT_CSI_HINT.get(etype, "00")

        lines.append(
            BillOfQuantitiesLine(
                item_code=code,
                description=desc,
                quantity=round(qty, 4),
                unit=unit,
                element_type=etype,
                material=material,
                csi_division=csi,
                element_count=count,
            ).model_dump()
        )

    lines.sort(key=lambda r: (r.get("csi_division") or "", r["description"]))
    return {
        "project_id": project_id,
        "line_count": len(lines),
        "lines": lines,
        "cos_sample": [
            ConstructionObjectSchema(
                object=row["element_type"],
                id=row["item_code"],
                location=None,
                quantity=row["quantity"],
                unit=row["unit"],
                dependencies=[],
                meta={"material": row.get("material"), "csi": row.get("csi_division")},
            ).model_dump()
            for row in lines[:15]
        ],
    }


async def tool_planning_schedule_views(
    project_id: str,
    lookahead_from_day: int = 0,
    lookahead_horizon_days: int = 21,
) -> dict[str, Any]:
    """Full deterministic schedule plus milestones and lookahead window."""
    tasks_raw = await tool_generate_schedule(project_id)
    cts_tasks = [
        ConstructionTaskSchema(
            task=t["name"],
            task_id=t["task_id"],
            duration=t.get("duration_days"),
            resources=[],  # filled in resource_loading tool
            constraints=[],
            depends_on=list(t.get("depends_on") or []),
            start_day=t.get("start_day"),
            end_day=t.get("end_day"),
        ).model_dump()
        for t in tasks_raw
    ]

    milestones = []
    for t in tasks_raw:
        ed = t.get("end_day")
        if ed is None:
            continue
        milestones.append({
            "milestone_id": f"M-{t['task_id']}",
            "name": f"Complete: {t['name']}",
            "day": ed,
            "linked_task_id": t["task_id"],
        })

    horizon = max(1, min(int(lookahead_horizon_days), 365))
    start = int(lookahead_from_day)
    lookahead = [
        t for t in tasks_raw
        if t.get("start_day") is not None
        and start <= int(t["start_day"]) < start + horizon
    ]

    return {
        "project_id": project_id,
        "lookahead_from_day": start,
        "lookahead_horizon_days": horizon,
        "tasks": tasks_raw,
        "cts_tasks": cts_tasks,
        "milestones": milestones,
        "lookahead_tasks": lookahead,
        "critical_path_hint": (
            "Longest chain follows package dependencies in the deterministic model; "
            "import to P6/MS Project for full CPM."
        ),
    }


async def tool_resource_loading_sheet(project_id: str) -> dict[str, Any]:
    """Rough labour-hours by crew from package durations (schedule-derived)."""
    tasks_raw = await tool_generate_schedule(project_id)
    rows = []
    hours_per_day = 8.0
    for t in tasks_raw:
        tid = t.get("task_id", "")
        name = str(t.get("name", ""))
        days = int(t.get("duration_days") or 1)
        internal = _NAME_TO_PACKAGE_KEY.get(name)
        crew, headcount = _PACKAGE_CREW.get(internal or "", ("CREW_GENERAL", 4))
        crew_hours = days * hours_per_day * headcount
        rows.append({
            "task_id": tid,
            "work_package": name,
            "crew_code": crew,
            "headcount_assumed": headcount,
            "duration_days": days,
            "crew_hours": round(crew_hours, 2),
            "notes": "Headcount defaults; replace with company norms.",
        })

    total_hours = sum(r["crew_hours"] for r in rows)
    return {
        "project_id": project_id,
        "total_crew_hours": round(total_hours, 2),
        "rows": rows,
    }


def _build_xer_skeleton(tasks_raw: list[dict]) -> str:
    """
    Minimal Primavera-style text skeleton (tab-separated tables).
    Not a full P6 exchange; sufficient for manual review or custom importers.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H.%M.%S")
    lines = [
        f"ERMHDR\t16.2.0.0\t{now}\tbim_assistant\tPlanningExport\tProj\tUTF-8\t1\t0",
        "%T\tCALENDAR",
        "%F\tclndr_id\tclndr_name\tdefault_flag",
        "%R\t1\tStandard\tY",
        "%T\tPROJWBS",
        "%F\twbs_id\tproj_id\tparent_wbs_id\tseq_num\twbs_name",
        "%R\t1\t1\t\t1\tProject Root",
        "%T\tTASK",
        "%F\ttask_id\tproj_id\twbs_id\tclndr_id\ttask_name\ttarget_drtn_hr_cnt\tphys_complete_pct",
    ]
    pred_lines: list[str] = ["%T\tTASKPRED", "%F\ttask_pred_id\ttask_id\tpred_task_id\tpred_type\tlag_hr_cnt"]
    pred_seq = 1
    id_map: dict[str, int] = {}
    for i, t in enumerate(tasks_raw):
        tid = 1000 + i
        key = t.get("task_id") or str(i)
        id_map[str(key)] = tid
        name = str(t.get("name", "")).replace("\t", " ")
        days = int(t.get("duration_days") or 1)
        hrs = max(days * 8, 8)
        lines.append(f"%R\t{tid}\t1\t1\t1\t{name}\t{hrs}\t0.0")
        for dep in t.get("depends_on") or []:
            pred = id_map.get(str(dep))
            if pred is None:
                continue
            pred_lines.append(f"%R\t{pred_seq}\t{tid}\t{pred}\tPR\t0")
            pred_seq += 1
    lines.extend(pred_lines)
    return "\n".join(lines) + "\n"


async def tool_export_schedule_files(project_id: str) -> dict[str, Any]:
    """Write XER skeleton + CSV schedule next to processed data; return paths."""
    tasks_raw = await tool_generate_schedule(project_id)
    export_root = Path(settings.exports_dir) / project_id
    export_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    xer_path = export_root / f"schedule_{stamp}.xer"
    csv_path = export_root / f"schedule_{stamp}.csv"

    xer_path.write_text(_build_xer_skeleton(tasks_raw), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["task_id", "name", "duration_days", "start_day", "end_day", "depends_on"])
        for t in tasks_raw:
            w.writerow([
                t.get("task_id"),
                t.get("name"),
                t.get("duration_days"),
                t.get("start_day"),
                t.get("end_day"),
                ";".join(t.get("depends_on") or []),
            ])

    return {
        "project_id": project_id,
        "xer_path": str(xer_path),
        "csv_path": str(csv_path),
        "task_count": len(tasks_raw),
        "note": "XER is a simplified skeleton for exchange workflows; validate in P6 before production use.",
    }


def _severity_rank(sev: str) -> int:
    return {"error": 3, "warning": 2, "info": 1}.get(sev, 0)


async def tool_risk_and_schedule_signals(project_id: str) -> dict[str, Any]:
    """Deterministic risk flags from model + compliance + schedule + optional actuals."""
    schedule = await tool_generate_schedule(project_id)
    cost = await tool_estimate_cost(project_id)
    fire = await tool_check_compliance(project_id=project_id, rule_set="fire_safety")
    space = await tool_check_compliance(project_id=project_id, rule_set="space_area")
    ctx = load_context(project_id)

    total_days = max((t.get("end_day") or 0) for t in schedule) if schedule else 0
    risks: list[dict] = []
    if total_days > 550:
        risks.append({
            "id": "R-DUR",
            "severity": "warning",
            "title": "Long programme horizon",
            "detail": f"Deterministic schedule spans ~{total_days} days; sanity-check durations and logic.",
        })

    fc = 0
    for i in fire.get("issues", []):
        sev = i.get("severity") if isinstance(i, dict) else getattr(i, "severity", None)
        if sev == "error":
            fc += 1
    if fc:
        risks.append({
            "id": "R-COMPL-FIRE",
            "severity": "error",
            "title": "Fire / combustible findings",
            "detail": f"{fc} fire_safety issues require review.",
        })

    sc = 0
    for i in space.get("issues", []):
        sev = i.get("severity") if isinstance(i, dict) else getattr(i, "severity", None)
        if sev == "error":
            sc += 1
    if sc:
        risks.append({
            "id": "R-COMPL-SPACE",
            "severity": "warning",
            "title": "Space / area checks",
            "detail": f"{sc} space_area issues flagged.",
        })

    total_cost = float(cost.get("total_cost_usd") or 0)
    if total_cost > 25_000_000:
        risks.append({
            "id": "R-COST",
            "severity": "info",
            "title": "High roll-up cost",
            "detail": f"Estimated USD {total_cost:,.0f} — validate rates and scope.",
        })

    delays = []
    actuals = ctx.get("actual_progress") or {}
    if isinstance(actuals, dict):
        for tid, ap in actuals.items():
            if not isinstance(ap, dict):
                continue
            delay_days = ap.get("delay_days")
            if delay_days and int(delay_days) > 0:
                delays.append({
                    "task_id": tid,
                    "delay_days": int(delay_days),
                    "note": ap.get("note") or "",
                })
    if delays:
        risks.append({
            "id": "R-DELAY",
            "severity": "error",
            "title": "Reported site delays",
            "detail": f"{len(delays)} tasks show positive delay_days in planning context.",
            "evidence": delays[:10],
        })

    risks.sort(key=lambda r: _severity_rank(r.get("severity", "")), reverse=True)
    return {
        "project_id": project_id,
        "total_schedule_days": total_days,
        "estimated_total_cost_usd": total_cost,
        "risks": risks,
        "compliance_issue_counts": {
            "fire_safety": len(fire.get("issues", [])),
            "space_area": len(space.get("issues", [])),
        },
    }


async def tool_plan_vs_actual(project_id: str) -> dict[str, Any]:
    """Compare baseline schedule snapshot (optional) and recorded actual_progress."""
    ctx = load_context(project_id)
    baseline = ctx.get("baseline_task_snapshot")
    actuals = ctx.get("actual_progress") or {}
    current = await tool_generate_schedule(project_id)

    if not isinstance(actuals, dict):
        actuals = {}

    rows = []
    by_id = {t.get("task_id"): t for t in current}
    for tid, t in by_id.items():
        ap = actuals.get(tid, {})
        pct = None
        delay_days = None
        if isinstance(ap, dict):
            pct = ap.get("percent_complete")
            delay_days = ap.get("delay_days")
        base_end = None
        if isinstance(baseline, list):
            for b in baseline:
                if isinstance(b, dict) and b.get("task_id") == tid:
                    base_end = b.get("end_day")
                    break
        aligned = None
        if base_end is not None and t.get("end_day") is not None:
            aligned = int(t["end_day"]) - int(base_end)
        rows.append({
            "task_id": tid,
            "name": t.get("name"),
            "planned_end_day": t.get("end_day"),
            "baseline_end_day": base_end,
            "delta_vs_baseline_end": aligned,
            "reported_percent_complete": pct,
            "reported_delay_days": delay_days,
        })

    return {
        "project_id": project_id,
        "has_baseline_snapshot": bool(baseline),
        "tasks_compared": len(rows),
        "rows": rows,
        "site_notes_count": len(ctx.get("site_notes") or []),
    }


async def tool_lessons_learned_draft(project_id: str) -> dict[str, Any]:
    """Structured lessons template: pulls risks, notes, and open compliance themes."""
    risk_pkg = await tool_risk_and_schedule_signals(project_id)
    ctx = load_context(project_id)
    notes = ctx.get("site_notes") or []
    bullets: list[str] = []
    for r in risk_pkg.get("risks", [])[:8]:
        bullets.append(f"[{r.get('severity', 'info').upper()}] {r.get('title')}: {r.get('detail')}")
    for n in notes[-10:]:
        if isinstance(n, str) and n.strip():
            bullets.append(f"[SITE] {n.strip()}")

    lessons = {
        "project_id": project_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": {
            "schedule_execution": bullets[:5],
            "quality_and_compliance": bullets[5:10],
            "commercial": [
                f"Cost roll-up (deterministic): USD {risk_pkg.get('estimated_total_cost_usd', 0):,.0f}"
            ],
        },
        "follow_ups": [
            "Re-baseline in P6/MSP after major design changes.",
            "Record delay reasons in planning context for automated delay reports.",
        ],
    }
    return lessons


_HEAVY_QUERY_PAT = re.compile(
    r"(optimize|critical path|risk analysis|what-?if|delay analysis|scenario|dependency chain)",
    re.IGNORECASE,
)
_FAST_QUERY_PAT = re.compile(
    r"(\bhow many\b|element count|list walls|quick summary|extract counts)",
    re.IGNORECASE,
)


def select_llm_model(query: str) -> str:
    """Heuristic model routing: reasoning vs default vs fast extraction."""
    s = get_settings()
    if _HEAVY_QUERY_PAT.search(query) and (s.llm_model_reasoning or "").strip():
        return s.llm_model_reasoning.strip()
    if _FAST_QUERY_PAT.search(query) and (s.llm_model_fast or "").strip():
        return s.llm_model_fast.strip()
    return s.llm_model


async def tool_get_site_planning_context(project_id: str) -> dict[str, Any]:
    """Expose JSON planning context (actuals, notes, location) for the agent observe step."""
    return {"project_id": project_id, **load_context(project_id)}


def append_agent_audit(record: dict[str, Any]) -> None:
    """Append one JSON line for decision/tool trace (SRS audit)."""
    path = Path(settings.agent_audit_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, default=str)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
