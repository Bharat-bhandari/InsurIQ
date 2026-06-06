"""
Graph state for the real PolicyDesk Q&A agent.

Pydantic models (SynthesisAnswer, GateVerdict) are stored as dicts on the
state so the SqliteSaver doesn't have to teach itself how to (de)serialize
them — the nodes round-trip through `model_dump()` / explicit dataclass dumps.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, TypedDict


class QAState(TypedDict, total=False):
    # Input
    question: str

    # Plan (CONTRACT 1 — list of {"name": ..., "kwargs": {...}})
    plan: list[dict[str, Any]]

    # Tool layer
    tool_results: dict[str, Any] | None
    tool_status: Literal["ok", "degraded"] | None
    tool_attempts: dict[str, int]

    # Synthesis
    evidence_records: list[dict[str, Any]]
    synthesis: dict[str, Any] | None     # serialized SynthesisAnswer
    synthesis_meta: dict[str, Any]       # resolved_model, finish_reason
    needs_strict: bool                   # set by gate when asking for a regenerate
    regenerate_count: int

    # Gate
    gate_verdict: dict[str, Any] | None  # serialized GateVerdict

    # Final
    answer: str | None
    receipt: dict[str, Any]
    guardrail_blocked: dict[str, Any] | None  # set only when a guardrail fired

    # Append-only events log. `add` reducer concatenates per-node returns.
    resilience_events: Annotated[list[str], add]
