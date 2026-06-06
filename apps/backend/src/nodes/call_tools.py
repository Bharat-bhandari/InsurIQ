"""
Execute the planned tool calls and roll the outcomes into one tool_results
dict + a single `tool_status` flag.

Routing convention:
  - ALL planned tools succeed       → tool_status = "ok",  full results
  - SOME succeed, some exhaust retry → tool_status = "degraded", PARTIAL results
                                       kept (the grounding gate then drops the
                                       claim that needed the failed tool — honest
                                       drop-and-note, not a blanket failure).
  - NO tool succeeds                → tool_status = "degraded", results = None
                                       (routes to the generic honest no-guess).

`tool_status` is the receipt's signal; the next-node routing keys off whether
ANY usable results survived (see `route_on_tool_status`), so a partial failure
still reaches synthesis.

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
    # Keep partial results when SOME tools succeeded — only blank out when the
    # whole lookup failed. This is what lets a single failed tool degrade into
    # an honest drop-and-note instead of a blanket "couldn't verify anything".
    partial = bool(results) and any_degraded
    return {
        "tool_results": results if results else None,
        "tool_status": status,
        "tool_attempts": attempts,
        "resilience_events": events
        + [
            f"call_tools: aggregate status={status}"
            + (" (partial results kept → drop-and-note)" if partial else "")
        ],
    }
