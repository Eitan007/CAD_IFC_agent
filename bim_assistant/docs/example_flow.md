# Example Tool-Calling Flow

This document traces a complete example of an agent handling the query:

> "How much concrete is used, what will it cost, and does it pass fire safety?"

---

## Input

```json
POST /query
{
  "query": "How much concrete is used, what will it cost, and does it pass fire safety?",
  "project_id": "abc-123"
}
```

---

## Agent Iteration 1 — Parallel tool calls

The LLM identifies three sub-questions and calls three tools in one turn:

```
Tool call 1: get_material_quantities(project_id="abc-123")
Tool call 2: estimate_cost(project_id="abc-123")
Tool call 3: check_compliance(project_id="abc-123", rule_set="fire_safety")
```

**Tool 1 result** (`get_material_quantities`):
```json
[
  {"material": "concrete", "total_volume": 142.5, "total_area": 890.0, "element_count": 48, "element_types": ["wall", "slab", "column"]},
  {"material": "steel",    "total_volume": 12.3,  "total_area": null,  "element_count": 22, "element_types": ["beam", "column"]},
  {"material": "timber",   "total_volume": 8.7,   "total_area": 210.0, "element_count": 31, "element_types": ["wall", "furniture"]}
]
```

**Tool 2 result** (`estimate_cost`):
```json
{
  "project_id": "abc-123",
  "total_cost_usd": 52840.00,
  "breakdown": {
    "concrete": 23940.00,
    "steel": 20412.00,
    "_contingency": 4804.00
  },
  "assumptions": [
    "Labour multiplier: 1.4x on material cost",
    "Contingency: 10%",
    "Unit rates in USD/m³ from cost database"
  ]
}
```

**Tool 3 result** (`check_compliance`):
```json
{
  "project_id": "abc-123",
  "rule_set": "fire_safety",
  "passed": false,
  "issues": [
    {
      "rule_id": "FIRE-01",
      "severity": "warning",
      "element_id": "wall-timber-007",
      "message": "Wall 'W-007' uses combustible material 'timber' without a fire rating property.",
      "suggestion": "Add Pset_WallCommon.FireRating."
    }
  ]
}
```

---

## Agent Iteration 2 — Synthesis (end_turn)

The LLM synthesises the three results into a final answer:

```
The building uses 142.5 m³ of concrete across 48 elements (walls, slabs, and columns).

Estimated total construction cost is $52,840 USD:
  - Concrete works: $23,940
  - Steel works: $20,412
  - Contingency (10%): $4,804
  (Includes a 1.4× labour multiplier; unit rates from the cost database.)

Fire safety check: WARNINGS (1 issue)
  - Wall W-007 uses timber without a declared fire rating.
    Recommendation: Add Pset_WallCommon.FireRating to all timber walls
    to comply with fire safety requirements.

All concrete and steel elements passed fire safety checks.
```

---

## Trace summary

| Iteration | Tools called | Reason |
|-----------|-------------|--------|
| 1 | `get_material_quantities`, `estimate_cost`, `check_compliance` | All three questions require independent data |
| 2 | — | `end_turn` — synthesis only |

**Total LLM calls: 2**
**Total tool calls: 3**
**Raw IFC data seen by LLM: none**

---

## Another example — drill-down query

> "Show me all timber walls and their fire ratings"

```
Iteration 1: get_elements(project_id="abc-123", element_type="wall")
  → returns 48 walls with material field

Iteration 2: get_element_detail(project_id="abc-123", element_id="wall-timber-007")
             get_element_detail(project_id="abc-123", element_id="wall-timber-019")
             ... (for each timber wall found)

Iteration 3: end_turn — answer: "Found 7 timber walls. None have a FireRating
             property set. The following walls require remediation: ..."
```
