"""
Execute the planned tool calls and roll the outcomes into one tool_results
dict + a single `tool_status` flag.

Routing convention (carried from the slice):
  - ALL planned tools succeed  → tool_status = "ok"
  - ANY planned tool exhausts retries → tool_status = "degraded"

Each tool body still calls `CHAOS.maybe_fail_tool(name)` and prints exactly
one `[tool] ...` line per real execution — that print is the checkpoint-resume
proof from §A5.
"""

from __future__ import annotations

from typing import Any

from src.states.qa_state import QAState
from src.tools import ToolCallSpec, call_tool_with_retry


def call_tools(state: QAState) -> dict[str, Any]:
    plan_list = state.get("plan") or []
    results: dict[str, Any] = {}
    attempts: dict[str, int] = {}
    events: list[str] = []
    any_degraded = False

    for raw in plan_list:
        spec = ToolCallSpec(
            name=str(raw["name"]),
            kwargs=dict(raw.get("kwargs") or {}),
        )
        outcome = call_tool_with_retry(spec)
        events.extend(outcome.events)
        attempts[spec.name] = outcome.attempts
        if outcome.ok:
            results[spec.name] = outcome.value
            events.append(
                f"call_tools: {spec.name} ok in {outcome.attempts} attempt(s)"
            )
        else:
            any_degraded = True
            events.append(
                f"call_tools: {spec.name} EXHAUSTED retries; "
                "will route to honest degradation"
            )

    status = "degraded" if any_degraded else "ok"
    return {
        "tool_results": results if not any_degraded else None,
        "tool_status": status,
        "tool_attempts": attempts,
        "resilience_events": events + [f"call_tools: aggregate status={status}"],
    }
