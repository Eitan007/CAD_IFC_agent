"""
app/tools/compliance.py
Deterministic compliance checking tool.

Rule sets are pure Python — no LLM. Add new rule sets by subclassing
BaseRuleSet and registering in RULE_SET_REGISTRY.
"""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import Optional

from app.storage.database import get_session
from app.storage.repository import get_all_elements
from app.normalization.schema import ComplianceIssue, ComplianceReport
from app.storage.models import Element

logger = logging.getLogger(__name__)


class BaseRuleSet(ABC):
    name: str = "base"

    @abstractmethod
    def check(self, elements: list[Element]) -> list[ComplianceIssue]:
        ...


class EuroCode2RuleSet(BaseRuleSet):
    """Simplified Eurocode 2 checks (concrete structures)."""
    name = "eurocode2"

    MIN_WALL_THICKNESS_M = 0.12
    MIN_SLAB_THICKNESS_M = 0.10

    def check(self, elements: list[Element]) -> list[ComplianceIssue]:
        issues: list[ComplianceIssue] = []
        for elem in elements:
            if elem.type == "wall" and elem.volume is not None and elem.area is not None:
                if elem.area > 0:
                    thickness = elem.volume / elem.area
                    if thickness < self.MIN_WALL_THICKNESS_M:
                        issues.append(ComplianceIssue(
                            rule_id="EC2-W01",
                            severity="error",
                            element_id=elem.id,
                            message=(
                                f"Wall {elem.name or elem.id} thickness ~{thickness:.3f}m "
                                f"is below Eurocode 2 minimum {self.MIN_WALL_THICKNESS_M}m"
                            ),
                            suggestion="Increase wall thickness or use higher-grade concrete.",
                        ))
        return issues


class FireSafetyRuleSet(BaseRuleSet):
    """Simplified fire-safety checks based on material fire ratings."""
    name = "fire_safety"

    NON_COMBUSTIBLE = {"concrete", "steel", "masonry", "brick", "glass"}
    REQUIRES_RATING = {"timber", "wood", "insulation", "plasterboard", "gypsum"}

    def check(self, elements: list[Element]) -> list[ComplianceIssue]:
        issues: list[ComplianceIssue] = []
        for elem in elements:
            if elem.type in ("wall", "slab", "beam", "column"):
                mat = (elem.material or "").lower()
                if any(m in mat for m in self.REQUIRES_RATING):
                    fire_rating = (elem.properties or {}).get("fire_rating") or (
                        (elem.properties or {}).get("Pset_WallCommon", {}) or {}
                    ).get("FireRating")
                    if not fire_rating:
                        issues.append(ComplianceIssue(
                            rule_id="FIRE-01",
                            severity="warning",
                            element_id=elem.id,
                            message=(
                                f"{elem.type.title()} {elem.name or elem.id} uses combustible "
                                f"material '{mat}' without a fire rating property."
                            ),
                            suggestion="Add Pset_WallCommon.FireRating or Pset_SlabCommon.FireRating.",
                        ))
        return issues


class SpaceMinAreaRuleSet(BaseRuleSet):
    """Check minimum habitable room area (simplified BR Part M / local codes)."""
    name = "space_area"

    MIN_HABITABLE_M2 = 7.5

    def check(self, elements: list[Element]) -> list[ComplianceIssue]:
        issues: list[ComplianceIssue] = []
        for elem in elements:
            if elem.type == "space" and elem.area is not None:
                if 0 < elem.area < self.MIN_HABITABLE_M2:
                    issues.append(ComplianceIssue(
                        rule_id="SPACE-01",
                        severity="warning",
                        element_id=elem.id,
                        message=(
                            f"Space {elem.name or elem.id} area {elem.area:.2f}m² "
                            f"is below minimum habitable {self.MIN_HABITABLE_M2}m²"
                        ),
                        suggestion="Verify space classification; non-habitable spaces may be exempt.",
                    ))
        return issues


RULE_SET_REGISTRY: dict[str, BaseRuleSet] = {
    "eurocode2": EuroCode2RuleSet(),
    "fire_safety": FireSafetyRuleSet(),
    "space_area": SpaceMinAreaRuleSet(),
}


async def tool_check_compliance(
    project_id: str,
    rule_set: str = "fire_safety",
) -> dict:
    """
    Run a compliance rule set against all elements.

    Args:
        project_id: Target project.
        rule_set: One of 'eurocode2', 'fire_safety', 'space_area'.

    Returns:
        ComplianceReport dict.
    """
    checker = RULE_SET_REGISTRY.get(rule_set.lower())
    if checker is None:
        available = list(RULE_SET_REGISTRY.keys())
        return ComplianceReport(
            project_id=project_id,
            rule_set=rule_set,
            passed=False,
            issues=[ComplianceIssue(
                rule_id="SYSTEM",
                severity="error",
                element_id=None,
                message=f"Unknown rule set '{rule_set}'. Available: {available}",
            )],
        ).model_dump()

    async with get_session() as session:
        elements = await get_all_elements(project_id, session)

    issues = checker.check(elements)
    passed = not any(i.severity == "error" for i in issues)

    logger.info(
        "Compliance check '%s': %d issues (%s) for project %s",
        rule_set, len(issues), "PASS" if passed else "FAIL", project_id,
    )

    return ComplianceReport(
        project_id=project_id,
        rule_set=rule_set,
        passed=passed,
        issues=issues,
    ).model_dump()
