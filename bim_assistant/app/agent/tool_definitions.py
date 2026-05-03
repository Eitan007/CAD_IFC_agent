"""
app/agent/tool_definitions.py
Tool schemas passed to the Anthropic API.
Each tool maps to a deterministic function in app/tools/.
"""

TOOL_DEFINITIONS = [
    {
        "name": "get_elements",
        "description": (
            "Retrieve building elements from the project. "
            "Filter by element_type (e.g. 'wall', 'slab', 'door', 'column', 'beam', 'window'). "
            "Omit element_type to get all elements. Returns id, type, material, volume, area, storey."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "The project identifier"},
                "element_type": {
                    "type": "string",
                    "description": "Optional: filter by type ('wall','slab','door','column','beam','window','stair','roof','space','furniture')",
                },
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "get_element_detail",
        "description": (
            "Get full detail of a single element including all IFC properties. "
            "Use after get_elements to drill into a specific element."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "element_id": {"type": "string", "description": "Element ID from get_elements result"},
            },
            "required": ["project_id", "element_id"],
        },
    },
    {
        "name": "get_material_quantities",
        "description": (
            "Get aggregated material quantities for the entire project. "
            "Returns total volume (m³), area (m²), and element count per material. "
            "Use for 'how much concrete/steel/timber?' questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "get_element_counts",
        "description": (
            "Get a count of each element type in the project. "
            "Useful for quick overview: 'how many walls/doors/windows are there?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "estimate_cost",
        "description": (
            "Estimate total construction cost in USD based on material volumes and unit rates. "
            "Includes labour multiplier and contingency. "
            "Returns total cost and breakdown by material."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "generate_schedule",
        "description": (
            "Generate a construction schedule as an ordered list of work packages with durations. "
            "Returns tasks with start_day, end_day, duration_days, and dependencies. "
            "Use for timeline and planning questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "check_compliance",
        "description": (
            "Check building elements against a rule set. "
            "Available rule sets: 'eurocode2' (structural), 'fire_safety', 'space_area'. "
            "Returns a list of compliance issues with severity (error/warning/info)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "rule_set": {
                    "type": "string",
                    "enum": ["eurocode2", "fire_safety", "space_area"],
                    "description": "Rule set to apply",
                },
            },
            "required": ["project_id", "rule_set"],
        },
    },
    {
        "name": "graph_traverse",
        "description": (
            "Walk the BIM graph from one element across typed relationships up to N hops. "
            "Use for connectivity / containment chains (e.g. what is connected to this wall?, "
            "what shares spatial relationships?). "
            "relationship_type must be one of: CONNECTS_TO (topology between elements), "
            "LOCATED_IN (element inside parent space id), CONTAINED_BY (host/container id), "
            "ON_STOREY (element assigned to a storey node). "
            "Prefer this over listing all elements when the question is explicitly about neighbors or paths."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "start_element_id": {"type": "string", "description": "Element id to start from"},
                "relationship_type": {
                    "type": "string",
                    "enum": ["CONNECTS_TO", "LOCATED_IN", "CONTAINED_BY", "ON_STOREY"],
                },
                "depth": {
                    "type": "integer",
                    "description": "Maximum hops from the start node (1–10)",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["project_id", "start_element_id", "relationship_type"],
        },
    },
]
