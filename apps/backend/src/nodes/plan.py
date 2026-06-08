"""
Deterministic planner (CONTRACT 1 — no LLM in this step).

Maps a question to a fixed list of tool-call specs via simple keyword rules.
The list is the seam an optional LLM-based planner (Step 4.opt) would replace;
the rest of the graph doesn't care HOW the plan was produced.
"""

from __future__ import annotations

from typing import Any

from src.states.qa_state import QAState


# Keyword → list of ToolCallSpec dicts. Conditions that have a dedicated entry
# go first; the "default" demo plan covers the canonical knee-surgery question.
_KNEE_TRIGGERS = ("knee", "joint replacement", "joint-replacement")
# "eligible limit"/"eligible room" route the demo's room chips here so they hit
# get_room_rent_rule: chip 2 ("…room above my eligible limit?") is the fail-tool
# target, and chip 3 ("…per-day cap on my hospital room rent?") is the gate
# drop-and-note hook on the FLAGGED_UNKNOWN room_rent_limit.
_ROOM_TRIGGERS = (
    "room rent",
    "room-rent",
    "room cap",
    "per-day",
    "per day",
    "eligible limit",
    "eligible room",
)
_CATARACT_TRIGGERS = ("cataract",)
_HERNIA_TRIGGERS = ("hernia",)
_PED_TRIGGERS = ("pre-existing", "pre existing", "ped")


def _spec(name: str, **kwargs: Any) -> dict[str, Any]:
    return {"name": name, "kwargs": kwargs}


def _plan_for(question: str) -> list[dict[str, Any]]:
    q = question.lower()

    # Demo question: knee replacement waiting + meta-rule + room-rent context.
    if any(t in q for t in _KNEE_TRIGGERS):
        return [
            _spec("get_waiting_periods"),
            _spec("resolve_for_user", condition="knee replacement"),
            _spec("get_room_rent_rule"),
        ]

    # "What is the room rent cap?" — the demo's ungrounded-claim scenario.
    if any(t in q for t in _ROOM_TRIGGERS):
        return [
            _spec("get_room_rent_rule"),
            _spec("resolve_for_user", condition="room rent"),
        ]

    if any(t in q for t in _CATARACT_TRIGGERS):
        return [
            _spec("get_waiting_periods"),
            _spec("resolve_for_user", condition="cataract"),
            _spec("get_sub_limit", condition="Cataract"),
        ]

    if any(t in q for t in _HERNIA_TRIGGERS):
        return [
            _spec("get_waiting_periods"),
            _spec("resolve_for_user", condition="hernia"),
        ]

    if any(t in q for t in _PED_TRIGGERS):
        return [
            _spec("get_waiting_periods"),
            _spec("resolve_for_user", condition="pre-existing disease"),
        ]

    # Fallback: at least fetch waiting periods and resolved facts so the user
    # gets SOMETHING grounded to read.
    return [
        _spec("get_waiting_periods"),
        _spec("resolve_for_user", condition=question[:60]),
    ]


def plan(state: QAState) -> dict[str, Any]:
    """Plan node: question -> deterministic tool-call list."""
    q = state.get("question") or ""
    specs = _plan_for(q)
    names = [s["name"] for s in specs]
    return {
        "plan": specs,
        "regenerate_count": 0,
        "needs_strict": False,
        "resilience_events": [f"plan: question='{q[:60]}' -> tools={names}"],
    }
