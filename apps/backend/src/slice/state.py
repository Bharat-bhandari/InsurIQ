"""Graph state for the step-3 slice."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, TypedDict


class SliceState(TypedDict, total=False):
    question: str

    # Tool layer
    tool_results: dict[str, Any] | None
    tool_status: Literal["ok", "degraded"] | None
    attempt_count: int

    # Synthesis
    answer: str | None

    # Append-only log of what failed / recovered. Concatenated across nodes
    # via the `add` reducer so each node can return only its new events.
    resilience_events: Annotated[list[str], add]
