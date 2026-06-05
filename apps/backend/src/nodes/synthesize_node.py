"""
LangGraph node wrappers for synthesis (happy + degraded).

The structured-synthesis logic itself lives in `src/nodes/synthesize.py` so it
can be exercised in isolation by `scripts/prove_synthesis.py`. This module is
just the graph-state plumbing around it.
"""

from __future__ import annotations

from typing import Any

from src.nodes.synthesize import collect_evidence_records, run_synthesis
from src.states.qa_state import QAState


def synthesize(state: QAState) -> dict[str, Any]:
    """Real LLM synthesis with structured output. Bumps regenerate_count on a
    strict regenerate so the gate can enforce the bound."""
    question = state.get("question") or ""
    tool_results = state.get("tool_results") or {}
    strict = bool(state.get("needs_strict"))
    regen_used = int(state.get("regenerate_count") or 0)

    parsed, result, records, guard_events = run_synthesis(
        question, tool_results, strict=strict
    )

    new_regen = regen_used + 1 if strict else regen_used
    events: list[str] = list(guard_events)
    events.append(
        f"synthesize: model={result.resolved_model} strict={strict} "
        f"regenerate_count={new_regen} lede_cites={parsed.lede_cites} "
        f"claims={len(parsed.claims)}"
    )
    return {
        "evidence_records": records,
        "synthesis": parsed.model_dump(),
        "synthesis_meta": {
            "resolved_model": result.resolved_model,
            "finish_reason": result.finish_reason,
        },
        # Clear the strict flag after this run; if the gate wants another
        # regenerate it'll set it again.
        "needs_strict": False,
        "regenerate_count": new_regen,
        "resilience_events": events,
    }


def synthesize_degraded(state: QAState) -> dict[str, Any]:
    """Honest no-guess answer. Reused whether we got here from a tool failure
    OR from the gate exhausting regenerate attempts."""
    via_tool = state.get("tool_status") == "degraded"
    via_gate = bool((state.get("gate_verdict") or {}).get("action") == "degrade")

    if via_gate:
        msg = (
            "I'm not confident enough in the policy lookup to answer that "
            "headline directly — the supporting evidence didn't clear the "
            "grounding check, even after a stricter retry. Please rephrase or "
            "ask a related question; the rest of the policy Q&A flow remains "
            "available."
        )
        reason = "gate-degrade"
    else:
        msg = (
            "I couldn't verify the relevant policy clauses right now — the "
            "lookup did not succeed and I won't guess on a claim-defining "
            "fact. Please retry shortly; the rest of the policy Q&A flow "
            "remains available."
        )
        reason = "tool-degrade" if via_tool else "unknown-degrade"

    return {
        "answer": msg,
        "resilience_events": [f"synthesize_degraded: honest no-guess answer ({reason})"],
    }
