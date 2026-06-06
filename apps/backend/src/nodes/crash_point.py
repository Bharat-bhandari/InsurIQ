"""
Real-kill checkpoint-resume hinge.

Exists solely so the call_tools checkpoint commits to disk before the os._exit
fires. Uses os._exit (NOT sys.exit) so no exception is raised and no teardown
swallows the crash. Combined with `durability="sync"` on `graph.stream(...)`
this is what makes "resume without re-running the tool" actually true.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from src.chaos import CHAOS
from src.states.qa_state import QAState


def crash_point(state: QAState) -> dict[str, Any]:
    if CHAOS.crash_after_tools:
        msg = "[crash_point] chaos armed — os._exit(1) after tool checkpoint"
        print(msg, file=sys.stderr, flush=True)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)

    return {
        "resilience_events": ["crash_point: pass-through (chaos not armed)"],
    }


def route_on_tool_status(state: QAState) -> str:
    """Branch key for the conditional edge after crash_point.

    Routes on whether ANY usable tool results survived — not on tool_status —
    so a PARTIAL failure (some tools ok, one failed) still reaches synthesis and
    the grounding gate can drop the unverifiable claim (honest drop-and-note).
    Only a total tool failure (results is None/empty) goes to the generic
    degraded synthesizer.
    """
    return "synthesize" if state.get("tool_results") else "synthesize_degraded"
