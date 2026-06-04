"""
The five slice nodes.

No real LLM calls — synthesis just formats a string from `tool_results`. The
slice is about checkpoint+branch mechanics, not generation.

Routing keyed on `tool_status` after `crash_point`:
  ok       -> synthesize
  degraded -> synthesize_degraded
"""

from __future__ import annotations

import os
import sys
from typing import Any

from src.slice.chaos import CHAOS
from src.slice.state import SliceState
from src.slice.tools import get_waiting_periods_with_retry


# ---------------------------------------------------------------------------
# 1. plan
# ---------------------------------------------------------------------------


def plan(state: SliceState) -> dict[str, Any]:
    """Trivially decide we need the waiting-periods lookup."""
    q = state.get("question", "")
    return {
        "resilience_events": [
            f"plan: question='{q}' -> tool=get_waiting_periods",
        ],
    }


# ---------------------------------------------------------------------------
# 2. call_tool
# ---------------------------------------------------------------------------


def call_tool(state: SliceState) -> dict[str, Any]:
    """Run the tool via the bounded-retry wrapper. Never raises."""
    outcome = get_waiting_periods_with_retry()

    if outcome.ok:
        return {
            "tool_results": outcome.value,
            "tool_status": "ok",
            "attempt_count": outcome.attempts,
            "resilience_events": outcome.events
            + [f"call_tool: ok after {outcome.attempts} attempt(s)"],
        }

    # Final failure -> deliberate degradation.
    return {
        "tool_results": None,
        "tool_status": "degraded",
        "attempt_count": outcome.attempts,
        "resilience_events": outcome.events
        + [
            "call_tool: degraded — lookup failed, will answer honestly without "
            "the unverified fact",
        ],
    }


# ---------------------------------------------------------------------------
# 3. crash_point — exists solely to make the post-call_tool checkpoint commit
# ---------------------------------------------------------------------------


def crash_point(state: SliceState) -> dict[str, Any]:
    """If chaos.crash_after_tools is armed, hard-kill the process AFTER the
    call_tool checkpoint has been persisted. Uses os._exit (NOT sys.exit) so
    no exception is raised and no teardown swallows the crash."""
    if CHAOS.crash_after_tools:
        msg = "[crash_point] chaos armed — os._exit(1) after tool checkpoint"
        print(msg, file=sys.stderr, flush=True)
        # Best-effort flush before pulling the rug.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)

    return {
        "resilience_events": ["crash_point: pass-through (chaos not armed)"],
    }


# ---------------------------------------------------------------------------
# 4a. synthesize — happy path
# ---------------------------------------------------------------------------


def synthesize(state: SliceState) -> dict[str, Any]:
    """Format a cited answer from `tool_results`. Stub text; real graph will
    use the LLM. Citation pulls page + clause from the Evidence span."""
    results = state.get("tool_results") or {}
    sd = results.get("specific_disease_months") or {}
    longer = results.get("longer_waiting_rule") or {}
    ped = results.get("pre_existing_disease_months") or {}

    sd_value = sd.get("value")
    sd_span = sd.get("span") or {}
    ped_value = ped.get("value")
    ped_span = ped.get("span") or {}
    longer_span = longer.get("span") or {}

    parts = [
        "Knee replacement falls under the specific-disease/procedure waiting "
        f"period of {sd_value} months "
        f"(clause {sd_span.get('clause')}, p{sd_span.get('page')}).",
        f"If it is also a pre-existing condition, the PED waiting of "
        f"{ped_value} months applies "
        f"(clause {ped_span.get('clause')}, p{ped_span.get('page')}), "
        "and per the 'longer applies' meta-rule "
        f"(clause {longer_span.get('clause')}, p{longer_span.get('page')}) "
        "the longer of the two governs.",
    ]
    answer = " ".join(parts)
    return {
        "answer": answer,
        "resilience_events": ["synthesize: cited answer produced"],
    }


# ---------------------------------------------------------------------------
# 4b. synthesize_degraded — honest "couldn't verify" path
# ---------------------------------------------------------------------------


def synthesize_degraded(state: SliceState) -> dict[str, Any]:
    """Format a deliberately honest answer. Must NOT read like an error — this
    is the principled, grounded response when verification fails."""
    answer = (
        "I couldn't verify the waiting-period clauses for knee replacement "
        "right now — the policy lookup did not succeed and I won't guess on a "
        "claim-defining fact. Please retry shortly; the rest of the policy "
        "Q&A flow remains available."
    )
    return {
        "answer": answer,
        "resilience_events": ["synthesize_degraded: honest no-guess answer produced"],
    }


# ---------------------------------------------------------------------------
# Conditional router (after crash_point)
# ---------------------------------------------------------------------------


def route_on_tool_status(state: SliceState) -> str:
    """Branch key for the conditional edge."""
    return "synthesize" if state.get("tool_status") == "ok" else "synthesize_degraded"
