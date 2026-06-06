"""
CLI entry-point for the real PolicyDesk Q&A graph (Step 4).

Usage:
    uv run python -m src.graphs.run "<question>"                  # normal
    uv run python -m src.graphs.run "<q>" --fail-tool             # honest degradation
    uv run python -m src.graphs.run "<q>" --fail-tool-once        # transient
    uv run python -m src.graphs.run "<q>" --crash-after-tools \\
                                          --thread-id demo1        # arm crash
    uv run python -m src.graphs.run --thread-id demo1              # resume

If --thread-id already has a checkpoint, the run RESUMES (input=None) — same
convention as the slice. Pass the same thread-id without chaos flags to
recover from a prior crash; the tool MUST NOT re-run (single `[tool] ...`
line across both invocations is the proof).

Durability is forced to "sync" so checkpoints land on disk between nodes;
this is REQUIRED for the crash scenario (§A5 in CONTEXT.md).
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from typing import Any

from src.chaos import configure
from src.graphs.qa_graph import build_graph, open_checkpointer


def _has_existing_checkpoint(graph, thread_id: str) -> bool:
    cfg = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(cfg)
    return bool(state.values) or bool(state.next)


def _build_receipt(final_state: dict[str, Any], *, thread_id: str, resumed: bool, break_model: bool = False) -> dict[str, Any]:
    """The Aegis-style resilience receipt (CONTEXT.md §A7).

    Includes resolved model (from gateway response metadata), per-tool retry
    counts and statuses, grounding-gate verdict, regenerate count, whether the
    run resumed from a checkpoint, and the full events log.
    """
    synth_meta = final_state.get("synthesis_meta") or {}
    gate_verdict = final_state.get("gate_verdict") or {}
    receipt: dict[str, Any] = {
        "thread_id": thread_id,
        "checkpoint_resumed": resumed,
        "resolved_model": synth_meta.get("resolved_model"),
        "guardrail_blocked": final_state.get("guardrail_blocked"),
        "tool_status": final_state.get("tool_status"),
        "tool_attempts": final_state.get("tool_attempts") or {},
        "grounding": {
            "action": gate_verdict.get("action"),
            "reason": gate_verdict.get("reason"),
            "lede_cites": gate_verdict.get("lede_cites"),
            "lede_status": gate_verdict.get("lede_status"),
            "kept_claim_cites": gate_verdict.get("kept_claim_cites") or [],
            "dropped": gate_verdict.get("dropped") or [],
        },
        "regenerate_count": int(final_state.get("regenerate_count") or 0),
        "events": list(final_state.get("resilience_events") or []),
    }
    if break_model:
        receipt["chaos_mode"] = "break_model"
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="src.graphs.run", description="PolicyDesk Q&A graph CLI.")
    parser.add_argument("question", nargs="?", default=None)
    parser.add_argument("--fail-tool", action="store_true")
    parser.add_argument("--fail-tool-once", action="store_true")
    parser.add_argument("--crash-after-tools", action="store_true")
    parser.add_argument("--break-model", action="store_true")
    parser.add_argument("--thread-id", default=None)
    parser.add_argument(
        "--receipt-json",
        action="store_true",
        help="Print the receipt as a JSON object (in addition to the human view).",
    )
    args = parser.parse_args(argv)

    configure(
        fail_tool=args.fail_tool,
        fail_tool_once=args.fail_tool_once,
        crash_after_tools=args.crash_after_tools,
        break_model=args.break_model,
    )

    thread_id = args.thread_id or f"qa-{secrets.token_hex(4)}"
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
        graph_input: Any = None
    else:
        if not args.question:
            parser.error("question is required when no prior checkpoint exists")
        graph_input = {
            "question": args.question,
            "resilience_events": [f"run: thread_id={thread_id} fresh start"],
            "regenerate_count": 0,
        }

    print(f"[run] thread_id={thread_id} resuming={resuming}")
    print("[run] node trace:")
    for chunk in graph.stream(
        graph_input,
        config=config,
        stream_mode="updates",
        durability="sync",
    ):
        for node_name in chunk:
            print(f"  -> {node_name}")

    final_state = graph.get_state(config).values

    print()
    print("[answer]")
    print(final_state.get("answer") or "(no answer produced)")

    receipt = _build_receipt(final_state, thread_id=thread_id, resumed=resuming, break_model=args.break_model)
    print()
    print("[receipt]")
    print(f"  resolved_model     : {receipt['resolved_model']}")
    if "chaos_mode" in receipt:
        print(f"  chaos_mode         : {receipt['chaos_mode']}")
    if receipt.get("guardrail_blocked"):
        gb = receipt["guardrail_blocked"]
        print(f"  guardrail_blocked  : stage={gb['stage']} integrations={gb['integrations']} action={gb['action']}")
    print(f"  tool_status        : {receipt['tool_status']}")
    print(f"  tool_attempts      : {receipt['tool_attempts']}")
    print(f"  grounding.action   : {receipt['grounding']['action']}")
    print(f"  grounding.reason   : {receipt['grounding']['reason']}")
    print(f"  grounding.lede     : {receipt['grounding']['lede_cites']} -> {receipt['grounding']['lede_status']}")
    print(f"  grounding.kept     : {receipt['grounding']['kept_claim_cites']}")
    print(f"  grounding.dropped  : {receipt['grounding']['dropped']}")
    print(f"  regenerate_count   : {receipt['regenerate_count']}")
    print(f"  checkpoint_resumed : {receipt['checkpoint_resumed']}")
    print(f"  thread_id          : {receipt['thread_id']}")
    print("  events:")
    for ev in receipt["events"]:
        print(f"    - {ev}")

    if args.receipt_json:
        print()
        print("[receipt-json]")
        print(json.dumps(receipt, indent=2, default=str))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
