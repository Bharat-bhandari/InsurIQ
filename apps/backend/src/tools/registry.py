"""
Read-only tools over `NIVA_BUPA_POLICY`. Each tool returns a dict whose values
follow the **keyed-Evidence shape** (CONTRACT 2 in the Step-4 brief):

    {
      "<logical_field>": {
        "key":    "ev_<stable_id>",      # what synthesis cites
        "value":  <scalar | list | dict | None>,
        "status": "verified" | "flagged_unknown" | ...,
        "span":   {"clause": "...", "page": <int>, "text": "..."} | None,
        "notes":  "..."                  # optional, surfaced for FLAGGED_UNKNOWN
      },
      ...
    }

The **key is the linchpin of the grounding gate** — every claim the synthesis
LLM produces carries a `cites` field that names one of these keys. The gate
resolves the key against this dict and checks `status == "verified"`.

A `_run_tool_once` wrapper:
  * calls `CHAOS.maybe_fail_tool(name)` first (so simulated failures don't
    print a misleading "fetching" line),
  * prints exactly ONE `[tool] ...` line per real execution (this is the
    checkpoint-resume proof from §A5 / Step 3),
  * returns the keyed dict.

`call_tool_with_retry` is the bounded-retry envelope used by `call_tools`.
Max 2 attempts (CONTEXT.md §A11: infinite retry is itself a resilience failure).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from src.chaos import CHAOS
from src.fixtures.niva_bupa_seed import NIVA_BUPA_POLICY
from src.states.evidence import Evidence
from src.tools.mcp_client import fetch_via_mcp, use_mcp_for

MAX_TOOL_ATTEMPTS = 2


# ---------------------------------------------------------------------------
# Evidence → keyed dict helpers
# ---------------------------------------------------------------------------


def _first_span(ev: Evidence | None) -> dict[str, Any] | None:
    """Pull (page, clause, text) off the primary span. None if no evidence."""
    if ev is None or not ev.spans:
        return None
    s = ev.spans[0]
    return {
        "page": s.page_start,
        "clause": s.clause_ref,
        "text": s.text,
    }


def _keyed(key: str, ev: Evidence | None) -> dict[str, Any]:
    """Wrap an Evidence into the CONTRACT-2 keyed shape.

    A None evidence is itself keyed (status=unverified, value=None) so the
    grounding gate's resolve-then-check logic stays uniform across cases.
    """
    if ev is None:
        return {
            "key": key,
            "value": None,
            "status": "unverified",
            "span": None,
            "notes": "no evidence record on this field",
        }
    return {
        "key": key,
        "value": ev.value,
        "status": ev.status.value,
        "span": _first_span(ev),
        "notes": ev.notes,
    }


# ---------------------------------------------------------------------------
# 1. get_waiting_periods
# ---------------------------------------------------------------------------


def _get_waiting_periods_body() -> dict[str, Any]:
    wp = NIVA_BUPA_POLICY.rules.waiting_periods
    return {
        "specific_disease_months": _keyed("ev_specific_wait", wp.specific_disease_months),
        "specific_diseases_listed": _keyed(
            "ev_specific_listed", wp.specific_diseases_listed
        ),
        "pre_existing_disease_months": _keyed(
            "ev_ped_wait", wp.pre_existing_disease_months
        ),
        "initial_waiting_days": _keyed("ev_initial_wait", wp.initial_waiting_days),
        "longer_waiting_rule": _keyed("ev_longer_rule", wp.longer_waiting_rule),
    }


def _get_waiting_periods_dispatch() -> dict[str, Any]:
    """Route get_waiting_periods to the MCP Gateway when USE_MCP_FOR selects it,
    else run the local body. SAME keyed-Evidence dict either way.

    This runs INSIDE `_wrap`, so by the time we get here the chaos hook and the
    single proof-of-execution print have already fired, and the call is still
    inside `call_tool_with_retry`'s bounded-retry envelope. The remote path adds
    no new resilience of its own — that all stays client-side (CONTEXT.md §A4).
    """
    if use_mcp_for("get_waiting_periods"):
        return fetch_via_mcp("get_waiting_periods")
    return _get_waiting_periods_body()


# ---------------------------------------------------------------------------
# 2. resolve_for_user(condition)
# ---------------------------------------------------------------------------


# Lightweight condition vocabulary. Keep it explicit; LLM is NOT in the plan
# step (CONTRACT 1). New questions get new entries here, not new prompts.
_SPECIFIC_KEYWORDS = {
    "knee replacement": ["joint replacement", "osteoarthritis"],
    "joint replacement": ["joint replacement"],
    "hip replacement": ["joint replacement"],
    "cataract": ["cataract"],
    "hernia": ["hernia"],
    "hysterectomy": ["hysterectomy"],
}


def _is_specific_disease(condition: str) -> tuple[bool, str | None]:
    """Returns (matched, the listed-phrase that triggered the match)."""
    listed = NIVA_BUPA_POLICY.rules.waiting_periods.specific_diseases_listed.value
    if not isinstance(listed, list):
        return False, None
    cond = condition.lower().strip()
    needles = _SPECIFIC_KEYWORDS.get(cond, [cond])
    for entry in listed:
        entry_lower = str(entry).lower()
        for needle in needles:
            if needle in entry_lower:
                return True, str(entry)
    return False, None


def _resolve_for_user_body(condition: str) -> dict[str, Any]:
    resolved = NIVA_BUPA_POLICY.resolved
    matched, matched_phrase = _is_specific_disease(condition)

    # Synthesizable boolean: is the queried condition in the 24-mo specific list?
    # We mirror the underlying specific_diseases_listed evidence's verification
    # status so a downstream "ev_condition_in_specific_list" cite is honest.
    listed_ev = NIVA_BUPA_POLICY.rules.waiting_periods.specific_diseases_listed
    condition_match = {
        "key": "ev_condition_in_specific_list",
        "value": matched,
        "status": listed_ev.status.value,
        "span": _first_span(listed_ev),
        "notes": (
            f"matched listed entry: {matched_phrase!r}" if matched
            else "no listed entry matched this condition"
        ),
    }

    return {
        "condition": condition,
        "condition_in_specific_list": condition_match,
        "effective_ped_waiting_months": _keyed(
            "ev_resolved_ped_user", resolved.effective_ped_waiting_months
        ),
        "effective_copay_percentage": _keyed(
            "ev_resolved_copay_user", resolved.effective_copay_percentage
        ),
        "room_rent_proportionate_deduction_applies": _keyed(
            "ev_resolved_room_user",
            resolved.room_rent_proportionate_deduction_applies,
        ),
    }


# ---------------------------------------------------------------------------
# 3. get_room_rent_rule  (the honest FLAGGED_UNKNOWN hook for the demo)
# ---------------------------------------------------------------------------


def _get_room_rent_rule_body() -> dict[str, Any]:
    rr = NIVA_BUPA_POLICY.rules.room_rent
    return {
        # NOTE: room_rent_limit on Platinum+ is genuinely FLAGGED_UNKNOWN — the
        # grounding gate will refuse to ground any claim that cites this key,
        # and the demo's "ungrounded claim → dropped + noted" path lands here.
        "room_rent_limit": _keyed("ev_room_rent_cap", rr.room_rent_limit),
        "proportionate_deduction": _keyed(
            "ev_room_prop_deduction", rr.proportionate_deduction
        ),
    }


# ---------------------------------------------------------------------------
# 4. get_sub_limit(condition)
# ---------------------------------------------------------------------------


def _normalize(s: str) -> str:
    return s.lower().strip()


def _get_sub_limit_body(condition: str) -> dict[str, Any]:
    target = _normalize(condition)
    sub_limits = NIVA_BUPA_POLICY.rules.sub_limits

    safe_slug = "".join(c if c.isalnum() else "_" for c in target).strip("_") or "unknown"
    cond_key = f"ev_sublimit_condition_{safe_slug}"
    limit_key = f"ev_sublimit_value_{safe_slug}"

    for sl in sub_limits:
        if _normalize(str(sl.condition.value)) == target:
            return {
                "condition": _keyed(cond_key, sl.condition),
                "limit": _keyed(limit_key, sl.limit),
            }

    # No matching sub-limit was extracted. Be honest about it: surface a
    # "no_record" status that the gate will treat as ungrounded.
    return {
        "condition": {
            "key": cond_key,
            "value": condition,
            "status": "no_record",
            "span": None,
            "notes": f"no SubLimit entry found for condition={condition!r}",
        },
        "limit": {
            "key": limit_key,
            "value": None,
            "status": "no_record",
            "span": None,
            "notes": "no SubLimit entry to draw a value from",
        },
    }


# ---------------------------------------------------------------------------
# Tool registry + bounded-retry envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolCallSpec:
    """One planned tool invocation (CONTRACT 1: plan returns a list of these)."""

    name: str
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolOutcome:
    ok: bool
    name: str
    value: dict[str, Any] | None
    events: list[str]
    attempts: int


def _wrap(name: str, body: Callable[..., dict[str, Any]]):
    """Wrap a tool body with (a) chaos hook, (b) the single proof-of-execution
    print line.  We keep them tiny here so the bodies above read as data."""

    def runner(**kwargs: Any) -> dict[str, Any]:
        CHAOS.maybe_fail_tool(name)
        # The single identifiable line that proves checkpoint-resume did NOT
        # re-run the tool. Mirrors the slice's `[call_tool] fetching ...`.
        arg_str = f" args={kwargs}" if kwargs else ""
        print(f"[tool] {name}{arg_str}", flush=True)
        return body(**kwargs)

    return runner


TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "get_waiting_periods": _wrap("get_waiting_periods", _get_waiting_periods_dispatch),
    "resolve_for_user": _wrap("resolve_for_user", _resolve_for_user_body),
    "get_room_rent_rule": _wrap("get_room_rent_rule", _get_room_rent_rule_body),
    "get_sub_limit": _wrap("get_sub_limit", _get_sub_limit_body),
}


def call_tool_with_retry(spec: ToolCallSpec) -> ToolOutcome:
    """Bounded-retry envelope around one tool call.

    Returns an outcome the graph state can fold in — never raises. Per §A11,
    MAX_TOOL_ATTEMPTS=2: infinite retry is itself a resilience failure.
    """
    body = TOOLS.get(spec.name)
    if body is None:
        return ToolOutcome(
            ok=False,
            name=spec.name,
            value=None,
            events=[f"tool {spec.name}: unknown tool name"],
            attempts=0,
        )

    events: list[str] = []
    last_err: Exception | None = None

    for attempt in range(1, MAX_TOOL_ATTEMPTS + 1):
        try:
            value = body(**spec.kwargs)
            if attempt > 1:
                events.append(f"tool {spec.name} recovered on attempt {attempt}")
            return ToolOutcome(
                ok=True,
                name=spec.name,
                value=value,
                events=events,
                attempts=attempt,
            )
        except TimeoutError as e:
            last_err = e
            events.append(f"tool {spec.name} failed on attempt {attempt}: {e}")
            print(
                f"[tool] {spec.name} attempt {attempt} failed: {e}",
                file=sys.stderr,
                flush=True,
            )

    events.append(
        f"tool {spec.name} exhausted {MAX_TOOL_ATTEMPTS} attempts; "
        f"last error: {last_err}"
    )
    return ToolOutcome(
        ok=False,
        name=spec.name,
        value=None,
        events=events,
        attempts=MAX_TOOL_ATTEMPTS,
    )
