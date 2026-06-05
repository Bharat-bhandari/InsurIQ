"""
Build + compile the real PolicyDesk Q&A LangGraph.

Shape (Step 4):

    question
      → plan
      → call_tools
      → crash_point → ⟨tool_status⟩
                         ok       → synthesize
                                     → grounding_gate → ⟨verdict⟩
                                          PASS / DROP_AND_NOTE → END
                                          REGENERATE           → synthesize (loop)
                                          DEGRADE              → synthesize_degraded → END
                         degraded → synthesize_degraded → END

The checkpointer + durability convention mirror the proven Step-3 slice:
SqliteSaver over a `sqlite3.connect(..., check_same_thread=False)`, and the
CLI must run `graph.stream(..., durability="sync")` so the post-call_tools
checkpoint commits before any crash_point firing.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from src.nodes.call_tools import call_tools
from src.nodes.crash_point import crash_point, route_on_tool_status
from src.nodes.grounding_gate_node import grounding_gate, route_after_gate
from src.nodes.plan import plan
from src.nodes.synthesize_node import synthesize, synthesize_degraded
from src.states.qa_state import QAState


# apps/backend/.qa_checkpoints.sqlite — colocated with pyproject.toml. Distinct
# from the slice's file so the slice CLI keeps working unchanged.
CHECKPOINT_PATH = Path(__file__).resolve().parents[2] / ".qa_checkpoints.sqlite"


def _build_uncompiled() -> StateGraph:
    g = StateGraph(QAState)
    g.add_node("plan", plan)
    g.add_node("call_tools", call_tools)
    g.add_node("crash_point", crash_point)
    g.add_node("synthesize", synthesize)
    g.add_node("grounding_gate", grounding_gate)
    g.add_node("synthesize_degraded", synthesize_degraded)

    g.add_edge(START, "plan")
    g.add_edge("plan", "call_tools")
    g.add_edge("call_tools", "crash_point")

    # Tool status branch.
    g.add_conditional_edges(
        "crash_point",
        route_on_tool_status,
        {
            "synthesize": "synthesize",
            "synthesize_degraded": "synthesize_degraded",
        },
    )

    g.add_edge("synthesize", "grounding_gate")

    # Grounding gate branch.
    g.add_conditional_edges(
        "grounding_gate",
        route_after_gate,
        {
            "finalize": END,
            "regenerate": "synthesize",
            "degrade": "synthesize_degraded",
        },
    )

    g.add_edge("synthesize_degraded", END)
    return g


def open_checkpointer() -> SqliteSaver:
    """Disk-backed SqliteSaver — direct construction.

    The classmethod `SqliteSaver.from_conn_string` is a context manager; the
    CLI holds the saver for the process lifetime, so we own the connection
    ourselves to avoid the context exiting from under us."""
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CHECKPOINT_PATH), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


def build_graph(checkpointer: SqliteSaver):
    return _build_uncompiled().compile(checkpointer=checkpointer)
