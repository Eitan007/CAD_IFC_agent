"""
app/agent/agent.py
LLM Agent that orchestrates tool calls.

The agent:
1. Receives a user query + project_id
2. Selects and chains tool calls via the Anthropic tool-use API
3. Returns a final synthesised answer

CONSTRAINT: The agent NEVER receives raw IFC/STEP data.
It only sees the structured output of deterministic tool functions.
"""
from __future__ import annotations
import json
import logging
from typing import Any, Optional

from anthropic import AsyncAnthropic

from app.config import get_settings
from app.agent.tool_definitions import TOOL_DEFINITIONS
from app.tools.elements import tool_get_elements, tool_get_element_detail
from app.tools.quantities import tool_get_material_quantities, tool_get_element_counts
from app.tools.cost import tool_estimate_cost
from app.tools.schedule import tool_generate_schedule
from app.tools.compliance import tool_check_compliance
from app.tools.graph import tool_graph_traverse

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are an expert BIM (Building Information Modelling) analyst assistant.
You help architects, engineers, and project managers understand building models by querying
structured data extracted from IFC/CAD files.

You have access to a set of deterministic tools that query the building database.
Always use tools to retrieve data — never guess or invent building properties.

When answering:
- Be concise and technical where appropriate
- Present quantities with units (m², m³, USD, days)
- If data is missing or ambiguous, say so clearly
- For compliance issues, explain the rule and suggest remediation
- Never mention raw IFC format, GUIDs, or internal IDs unless explicitly asked


Replying in <= 10 sentences is preferred, the lesser the better. 
Current project context will be provided with each query.
"""


# ── Tool dispatcher ──────────────────────────────────────────────────────────

async def _dispatch_tool(tool_name: str, tool_input: dict) -> Any:
    """Route tool calls from the LLM to the correct Python function."""
    project_id: str = tool_input.get("project_id", "")

    dispatch_map = {
        "get_elements": lambda: tool_get_elements(
            project_id=project_id,
            element_type=tool_input.get("element_type"),
        ),
        "get_element_detail": lambda: tool_get_element_detail(
            project_id=project_id,
            element_id=tool_input["element_id"],
        ),
        "get_material_quantities": lambda: tool_get_material_quantities(project_id),
        "get_element_counts": lambda: tool_get_element_counts(project_id),
        "estimate_cost": lambda: tool_estimate_cost(project_id),
        "generate_schedule": lambda: tool_generate_schedule(project_id),
        "check_compliance": lambda: tool_check_compliance(
            project_id=project_id,
            rule_set=tool_input.get("rule_set", "fire_safety"),
        ),
        "graph_traverse": lambda: tool_graph_traverse(
            project_id=project_id,
            start_element_id=tool_input["start_element_id"],
            relationship_type=tool_input["relationship_type"],
            depth=int(tool_input.get("depth", 2)),
        ),
    }

    handler = dispatch_map.get(tool_name)
    if handler is None:
        return {"error": f"Unknown tool: {tool_name}"}

    result = await handler()
    return result


# ── Agent loop ───────────────────────────────────────────────────────────────

async def run_agent(
    query: str,
    project_id: str,
    max_iterations: int = 8,
) -> dict:
    """
    Run the agentic loop for a user query.

    Returns:
        {
            "answer": str,          # final natural-language answer
            "tool_calls": list,     # trace of tools invoked
            "iterations": int,
        }
    """
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    model = settings.llm_model

    messages = [
        {
            "role": "user",
            "content": f"Project ID: {project_id}\n\nQuery: {query}",
        }
    ]

    tool_trace: list[dict] = []

    for iteration in range(max_iterations):
        logger.debug("Agent iteration %d/%d", iteration + 1, max_iterations)

        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Check stop condition
        if response.stop_reason == "end_turn":
            answer = _extract_text(response)
            logger.info("Agent finished in %d iterations", iteration + 1)
            return {
                "answer": answer,
                "tool_calls": tool_trace,
                "iterations": iteration + 1,
            }

        if response.stop_reason == "tool_use":
            # Append assistant's response to messages
            messages.append({"role": "assistant", "content": response.content})

            # Process all tool calls in this turn
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input
                logger.info("Tool call: %s(%s)", tool_name, json.dumps(tool_input)[:200])

                result = await _dispatch_tool(tool_name, tool_input)
                tool_trace.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "result_summary": str(result)[:300],
                })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                })

            messages.append({"role": "user", "content": tool_results})

        else:
            # Unexpected stop reason
            logger.warning("Unexpected stop reason: %s", response.stop_reason)
            break

    # Max iterations reached — return best effort
    last_text = _extract_text(response) if response else "Agent reached maximum iterations."
    return {
        "answer": last_text,
        "tool_calls": tool_trace,
        "iterations": max_iterations,
        "warning": "Max iterations reached",
    }


def _extract_text(response) -> str:
    """Extract the last text block from a response."""
    for block in reversed(response.content):
        if hasattr(block, "text"):
            return block.text
    return ""
