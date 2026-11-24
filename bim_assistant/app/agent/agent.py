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
from opentelemetry.trace import Status, StatusCode

from app.config import get_settings
from app.observability import get_tracer
from app.agent.tool_definitions import TOOL_DEFINITIONS
from app.tools.elements import tool_get_elements, tool_get_element_detail
from app.tools.quantities import tool_get_material_quantities, tool_get_element_counts
from app.tools.cost import tool_estimate_cost
from app.tools.schedule import tool_generate_schedule
from app.tools.compliance import tool_check_compliance
from app.tools.graph import tool_graph_traverse
from app.services.deterministic_checks import source_data_contract

logger = logging.getLogger(__name__)
settings = get_settings()
tracer = get_tracer()

SYSTEM_PROMPT = """You are an expert assistant for BIM (IFC) and CAD (STEP/STP) models.
You help people understand a model by querying structured data extracted from its source file.

You have access to a set of deterministic tools that query the building database.
Always use tools to retrieve data — never guess or invent building properties.

Source-data safety rules:
- IFC files can contain structured building information when it exists in the source file.
- STEP/STP files are CAD geometry. Do not claim thread pitch, thread class, ISO/DIN standard,
  material grade, cost, schedule, or other parametric BIM properties unless a tool result
  explicitly provides them.
- A generic STEP solid is not a parametric BIM object. Say what is known, then clearly say
  what the imported geometry cannot prove.

When answering:
- Be concise and technical where appropriate
- Present quantities with units (m², m³, USD, days)
- If data is missing or ambiguous, say so clearly
- For compliance issues, explain the rule and suggest remediation
- Never mention raw IFC format, GUIDs, or internal IDs unless explicitly asked


Replying in <= 10 sentences is preferred, the lesser the better. 
Current project context will be provided with each query.
"""


def _system_prompt_for(source_format: str) -> str:
    """Give the model an explicit data boundary for this particular project."""
    normalized_format = source_format.lower()
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"Current source format: {normalized_format.upper()}. "
        f"Data boundary: {source_data_contract(normalized_format)}"
    )


def _safe_history(history: Optional[list[dict[str, str]]]) -> list[dict[str, str]]:
    """Keep a small, valid window of earlier chat turns for follow-up questions."""
    if not history:
        return []

    safe_messages: list[dict[str, str]] = []
    for item in history[-12:]:
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        content = content.strip()
        if content:
            safe_messages.append({"role": role, "content": content[:4000]})
    return safe_messages


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

    with tracer.start_as_current_span(f"tool.{tool_name}") as span:
        span.set_attribute("tool.name", tool_name)
        span.set_attribute("tool.parameters", json.dumps(tool_input, default=str))
        span.set_attribute("bim.project_id", project_id)

        if handler is None:
            span.set_status(Status(StatusCode.ERROR, "unknown tool"))
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            result = await handler()
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise

        span.set_attribute("tool.result", json.dumps(result, default=str)[:4000])
        return result


# ── Agent loop ───────────────────────────────────────────────────────────────

async def run_agent(
    query: str,
    project_id: str,
    max_iterations: int = 8,
    source_format: str = "unknown",
    conversation_history: Optional[list[dict[str, str]]] = None,
) -> dict:
    """
    Run the agentic loop for a user query.

    Wraps the whole run in a root "agent.run" span so the per-LLM-call spans
    (auto-instrumented) and per-tool spans (see _dispatch_tool) all nest
    under one trace — this is the unit an Agent Trace Evaluation run over.

    Returns:
        {
            "answer": str,          # final natural-language answer
            "tool_calls": list,     # trace of tools invoked
            "iterations": int,
        }
    """
    with tracer.start_as_current_span("agent.run") as root_span:
        root_span.set_attribute("bim.project_id", project_id)
        root_span.set_attribute("bim.query", query)
        root_span.set_attribute("bim.source_format", source_format)
        root_span.set_attribute("bim.history_messages", len(conversation_history or []))
        try:
            result = await _run_agent_loop(
                query,
                project_id,
                max_iterations,
                source_format=source_format,
                conversation_history=conversation_history,
            )
        except Exception as exc:
            root_span.record_exception(exc)
            root_span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise

        root_span.set_attribute("bim.answer", result["answer"][:4000])
        root_span.set_attribute("bim.iterations", result["iterations"])
        root_span.set_attribute("bim.tool_call_count", len(result["tool_calls"]))
        if result.get("warning"):
            root_span.set_attribute("bim.warning", result["warning"])
        return result


async def _run_agent_loop(
    query: str,
    project_id: str,
    max_iterations: int,
    *,
    source_format: str,
    conversation_history: Optional[list[dict[str, str]]],
) -> dict:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    model = settings.llm_model

    messages = _safe_history(conversation_history)
    messages.append(
        {
            "role": "user",
            "content": f"Project ID: {project_id}\n\nQuery: {query}",
        }
    )

    tool_trace: list[dict] = []
    for iteration in range(max_iterations):
        logger.debug("Agent iteration %d/%d", iteration + 1, max_iterations)

        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=_system_prompt_for(source_format),
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
