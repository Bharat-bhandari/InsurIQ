"""
Build and compile the slice's StateGraph.

Persistent disk-backed SQLite checkpointer is required: state must survive a
real os._exit, which MemorySaver would NOT. The .sqlite file lives under
apps/backend/ and is gitignored.

Shape:

    plan -> call_tool -> crash_point -> ⟨tool_status⟩
                                          ok       -> synthesize         -> END
                                          degraded -> synthesize_degraded -> END
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from src.slice.nodes import (
    call_tool,
    crash_point,
    plan,
    route_on_tool_status,
    synthesize,
    synthesize_degraded,
)
from src.slice.state import SliceState


# apps/backend/.slice_checkpoints.sqlite — colocated with pyproject.toml.
CHECKPOINT_PATH = (
    Path(__file__).resolve().parents[2] / ".slice_checkpoints.sqlite"
)


def _build_uncompiled() -> StateGraph:
    g = StateGraph(SliceState)
    g.add_node("plan", plan)
    g.add_node("call_tool", call_tool)
    g.add_node("crash_point", crash_point)
    g.add_node("synthesize", synthesize)
    g.add_node("synthesize_degraded", synthesize_degraded)

    g.add_edge(START, "plan")
    g.add_edge("plan", "call_tool")
    g.add_edge("call_tool", "crash_point")
    g.add_conditional_edges(
        "crash_point",
        route_on_tool_status,
        {
            "synthesize": "synthesize",
            "synthesize_degraded": "synthesize_degraded",
        },
    )
    g.add_edge("synthesize", END)
    g.add_edge("synthesize_degraded", END)
    return g


def open_checkpointer() -> SqliteSaver:
    """Disk-backed SqliteSaver. Direct construction (the from_conn_string
    classmethod is a context manager; the slice's CLI holds the saver for the
    process lifetime, so we own the connection ourselves)."""
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CHECKPOINT_PATH), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


def build_graph(checkpointer: SqliteSaver):
    """Compile against the given checkpointer."""
    return _build_uncompiled().compile(checkpointer=checkpointer)
