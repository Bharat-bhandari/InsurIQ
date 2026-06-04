"""
CLI entry-point for the step-3 slice.

Usage:
  python -m src.slice.run "<question>"                       # normal
  python -m src.slice.run "<q>" --fail-tool                  # honest degradation
  python -m src.slice.run "<q>" --fail-tool-once             # transient
  python -m src.slice.run "<q>" --crash-after-tools \\
                              --thread-id demo1              # arm crash
  python -m src.slice.run --thread-id demo1                  # resume

If --thread-id already has a checkpoint, the run RESUMES (input=None). Pass
the same thread-id without any chaos flags to recover from a prior crash.

Durability is forced to "sync" so checkpoints land on disk between nodes;
this is REQUIRED for the crash scenario — async/exit durability would lose
the post-call_tool checkpoint when os._exit fires.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from typing import Any

from src.slice.chaos import configure
from src.slice.graph import build_graph, open_checkpointer


def _has_existing_checkpoint(graph, thread_id: str) -> bool:
    cfg = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(cfg)
    # If nothing has ever been written for this thread, .values is empty and
    # there are no .next steps.
    return bool(state.values) or bool(state.next)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="src.slice.run",
        description="PolicyDesk step-3 slice CLI.",
    )
    parser.add_argument(
        "question",
        nargs="?",
        default=None,
        help="The policy question. Optional when resuming an existing thread.",
    )
    parser.add_argument("--fail-tool", action="store_true")
    parser.add_argument("--fail-tool-once", action="store_true")
    parser.add_argument("--crash-after-tools", action="store_true")
    parser.add_argument(
        "--thread-id",
        default=None,
        help="Stable thread id (required to resume). Auto-generated if omitted.",
    )
    args = parser.parse_args(argv)

    configure(
        fail_tool=args.fail_tool,
        fail_tool_once=args.fail_tool_once,
        crash_after_tools=args.crash_after_tools,
    )

    thread_id = args.thread_id or f"slice-{secrets.token_hex(4)}"
    checkpointer = open_checkpointer()
    graph = build_graph(checkpointer)

    config = {"configurable": {"thread_id": thread_id}}

    resuming = _has_existing_checkpoint(graph, thread_id)
    if resuming:
        if args.question:
            print(
                f"[run] thread '{thread_id}' has an existing checkpoint — "
                f"ignoring positional question and RESUMING.",
                file=sys.stderr,
            )
        graph_input: Any = None  # LangGraph 1.x resume convention
    else:
        if not args.question:
            parser.error("question is required when no prior checkpoint exists")
        graph_input = {
            "question": args.question,
            "resilience_events": [
                f"run: thread_id={thread_id} fresh start",
            ],
            "attempt_count": 0,
        }

    print(f"[run] thread_id={thread_id} resuming={resuming}")
    print("[run] node trace:")
    final_state: dict[str, Any] | None = None
    for chunk in graph.stream(
        graph_input,
        config=config,
        stream_mode="updates",
        durability="sync",
    ):
        for node_name, _node_update in chunk.items():
            print(f"  -> {node_name}")

    final_state = graph.get_state(config).values

    print()
    print("[answer]")
    print(final_state.get("answer") or "(no answer produced)")

    print()
    print("[receipt]")
    print(f"  tool_status        : {final_state.get('tool_status')}")
    print(f"  checkpoint_resumed : {resuming}")
    print(f"  attempt_count      : {final_state.get('attempt_count')}")
    print(f"  thread_id          : {thread_id}")
    print("  resilience_events  :")
    for ev in final_state.get("resilience_events", []):
        print(f"    - {ev}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
