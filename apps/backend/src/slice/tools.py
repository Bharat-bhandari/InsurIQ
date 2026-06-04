"""
The slice's one read-only tool: `get_waiting_periods()`.

Reads `NIVA_BUPA_POLICY.rules.waiting_periods` and returns the value plus the
first Evidence span (page + clause + verbatim text) so synthesis can cite it.

The call site wraps the tool in a BOUNDED retry (max 2 attempts; per CONTEXT.md
§A11, infinite retry is itself a resilience failure).

The "[call_tool] fetching ..." print is the proof that resume does not re-run
the tool — it must appear exactly once per real execution.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

from src.fixtures.niva_bupa_seed import NIVA_BUPA_POLICY
from src.slice.chaos import CHAOS

MAX_TOOL_ATTEMPTS = 2


@dataclass
class ToolOutcome:
    ok: bool
    value: dict[str, Any] | None
    events: list[str]
    attempts: int


def _waiting_periods_payload() -> dict[str, Any]:
    """Shape the WaitingPeriods evidence into a citation-ready dict."""
    wp = NIVA_BUPA_POLICY.rules.waiting_periods
    specific_disease = wp.specific_disease_months
    specific_listed = wp.specific_diseases_listed
    longer_rule = wp.longer_waiting_rule
    ped = wp.pre_existing_disease_months

    def _first_span(ev: Any) -> dict[str, Any] | None:
        if ev is None or not ev.spans:
            return None
        s = ev.spans[0]
        return {
            "page": s.page_start,
            "clause": s.clause_ref,
            "text": s.text,
        }

    return {
        "specific_disease_months": {
            "value": specific_disease.value,
            "span": _first_span(specific_disease),
        },
        "specific_diseases_listed": {
            "value": specific_listed.value,
            "span": _first_span(specific_listed),
        },
        "pre_existing_disease_months": {
            "value": ped.value,
            "span": _first_span(ped),
        },
        "longer_waiting_rule": {
            "value": longer_rule.value if longer_rule else None,
            "span": _first_span(longer_rule) if longer_rule else None,
        },
    }


def _run_tool_once() -> dict[str, Any]:
    """The actual tool body. Prints the proof-of-execution line exactly once
    per real call; consults chaos first so a simulated failure does NOT print
    a misleading 'fetching' line."""
    CHAOS.maybe_fail_tool("get_waiting_periods")
    print("[call_tool] fetching waiting_periods from NIVA_BUPA_POLICY ...", flush=True)
    return _waiting_periods_payload()


def get_waiting_periods_with_retry() -> ToolOutcome:
    """Run the tool with bounded retry. Returns an outcome the caller can
    fold into the graph state — never raises."""
    events: list[str] = []
    last_err: Exception | None = None

    for attempt in range(1, MAX_TOOL_ATTEMPTS + 1):
        try:
            value = _run_tool_once()
            if attempt > 1:
                events.append(
                    f"tool get_waiting_periods recovered on attempt {attempt}"
                )
            return ToolOutcome(ok=True, value=value, events=events, attempts=attempt)
        except TimeoutError as e:
            last_err = e
            events.append(
                f"tool get_waiting_periods failed on attempt {attempt}: {e}"
            )
            # Surface the failure to stderr so a viewer of a normal run can see
            # the chaos firing in real time, separate from the graph trace.
            print(f"[call_tool] attempt {attempt} failed: {e}", file=sys.stderr, flush=True)

    events.append(
        f"tool get_waiting_periods exhausted {MAX_TOOL_ATTEMPTS} attempts; "
        f"last error: {last_err}"
    )
    return ToolOutcome(
        ok=False, value=None, events=events, attempts=MAX_TOOL_ATTEMPTS
    )
