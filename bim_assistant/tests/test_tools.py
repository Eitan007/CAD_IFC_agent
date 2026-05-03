"""
tests/test_tools.py
Unit tests for deterministic tool functions.
Uses in-memory SQLite (via SQLAlchemy) to avoid requiring a running Postgres.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.normalization.schema import BuildingElement, BuildingModel
from app.tools.cost import _match_cost, DEFAULT_COST_DB
from app.tools.schedule import tool_generate_schedule, PACKAGE_NAMES
from app.tools.compliance import EuroCode2RuleSet, FireSafetyRuleSet
from app.storage.models import Element


# ── Cost tool tests ──────────────────────────────────────────────────────────

def test_match_cost_exact():
    assert _match_cost("concrete", DEFAULT_COST_DB) == 120.0


def test_match_cost_fuzzy():
    # "reinforced concrete slab" should match "reinforced concrete"
    assert _match_cost("reinforced concrete slab", DEFAULT_COST_DB) == 180.0


def test_match_cost_fallback():
    assert _match_cost("unobtainium", DEFAULT_COST_DB) == DEFAULT_COST_DB["unknown"]


# ── Compliance tool tests ────────────────────────────────────────────────────

def _make_element(**kwargs) -> Element:
    defaults = dict(
        id="test-01",
        project_id="proj-1",
        type="wall",
        material="concrete",
        volume=2.4,
        area=12.0,
        properties={},
        connected_to=[],
        contains=[],
    )
    defaults.update(kwargs)
    e = Element()
    for k, v in defaults.items():
        setattr(e, k, v)
    return e


def test_eurocode2_wall_pass():
    # 2.4m³ / 12m² = 0.2m thick — above 0.12m minimum
    elem = _make_element(type="wall", volume=2.4, area=12.0)
    checker = EuroCode2RuleSet()
    issues = checker.check([elem])
    assert len(issues) == 0


def test_eurocode2_wall_fail():
    # 0.6m³ / 12m² = 0.05m thick — below minimum
    elem = _make_element(type="wall", volume=0.6, area=12.0, material="concrete")
    checker = EuroCode2RuleSet()
    issues = checker.check([elem])
    assert len(issues) == 1
    assert issues[0].rule_id == "EC2-W01"
    assert issues[0].severity == "error"


def test_fire_safety_combustible_no_rating():
    elem = _make_element(type="wall", material="timber", properties={})
    checker = FireSafetyRuleSet()
    issues = checker.check([elem])
    assert any(i.rule_id == "FIRE-01" for i in issues)


def test_fire_safety_combustible_with_rating():
    elem = _make_element(
        type="wall",
        material="timber",
        properties={"fire_rating": "REI 60"},
    )
    checker = FireSafetyRuleSet()
    issues = checker.check([elem])
    # No issues — rating is present
    assert len(issues) == 0


def test_fire_safety_non_combustible():
    elem = _make_element(type="column", material="steel", properties={})
    checker = FireSafetyRuleSet()
    issues = checker.check([elem])
    assert len(issues) == 0


# ── Schema tests ─────────────────────────────────────────────────────────────

def test_building_element_defaults():
    elem = BuildingElement(type="wall")
    assert elem.connected_to == []
    assert elem.contains == []
    assert elem.properties == {}
    assert elem.id is not None


def test_building_model_serialisation():
    elem = BuildingElement(
        type="slab",
        material="concrete",
        volume=5.2,
        project_id="p1",
    )
    model = BuildingModel(
        project_id="p1",
        source_file="test.ifc",
        element_count=1,
        elements=[elem],
    )
    data = model.model_dump()
    assert data["element_count"] == 1
    assert data["elements"][0]["type"] == "slab"
