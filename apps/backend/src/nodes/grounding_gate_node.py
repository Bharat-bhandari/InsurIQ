"""
LangGraph node wrapper for the grounding gate.

The gate logic itself lives in `src/nodes/grounding_gate.py` (pure-function,
no LLM) and is exercised in isolation by `scripts/prove_grounding_gate.py`.
This module turns the verdict into:

  * a finalized `answer` (when the verdict is PASS or DROP_AND_NOTE), or
  * a routing signal to regenerate / degrade.

The graph reads `gate_verdict["action"]` to choose the next edge.
"""

from __future__ import annotations

from typing import Any

from src.nodes.grounding_gate import GateAction, evaluate
from src.nodes.synthesize import SynthesisAnswer, SynthesisClaim
from src.states.qa_state import QAState


def _format_finalized_answer(
    lede: str,
    kept_claims: list[SynthesisClaim],
    note: str | None,
    *,
    evidence_index: dict[str, dict[str, Any]],
) -> str:
    """Build the user-facing answer string with inline (clause, page) citations."""
    lines = [lede]
    for c in kept_claims:
        rec = evidence_index.get(c.cites) or {}
        clause = rec.get("clause")
        page = rec.get("page")
        cite = ""
        if clause or page:
            cite = f" (clause {clause}, p{page})"
        lines.append(f"- {c.text}{cite}")
    if note:
        lines.append("")
        lines.append(note)
    return "\n".join(lines)


def grounding_gate(state: QAState) -> dict[str, Any]:
    # Guardrail block: answer is already set by synthesize; route straight to END.
    if state.get("guardrail_blocked"):
        return {
            "gate_verdict": {"action": GateAction.PASS.value, "reason": "guardrail-blocked"},
            "resilience_events": ["grounding_gate: bypassed (guardrail block already handled)"],
        }

    synthesis = state.get("synthesis") or {}
    if not synthesis:
        return {
            "gate_verdict": {"action": GateAction.DEGRADE.value, "reason": "no synthesis"},
            "resilience_events": ["grounding_gate: no synthesis to evaluate; degrading"],
        }

    answer = SynthesisAnswer.model_validate(synthesis)
    records = state.get("evidence_records") or []
    regen_used = int(state.get("regenerate_count") or 0)

    verdict = evaluate(answer, records, regenerate_attempts_used=regen_used)

    # Round-trip the verdict to a serializable dict for the receipt.
    verdict_dict: dict[str, Any] = {
        "action": verdict.action.value,
        "reason": verdict.reason,
        "lede_cites": verdict.lede_cites,
        "lede_status": verdict.lede_status,
        "kept_claim_cites": [c.cites for c in verdict.kept_claims],
        "dropped": [
            {"cite": d.cite, "text": d.text, "reason": d.reason}
            for d in verdict.dropped
        ],
        "note": verdict.note,
    }

    update: dict[str, Any] = {
        "gate_verdict": verdict_dict,
        "resilience_events": [f"grounding_gate: {verdict.action.value} — {verdict.reason}"],
    }

    if verdict.action in (GateAction.PASS, GateAction.DROP_AND_NOTE):
        evidence_index = {str(r["key"]): r for r in records if "key" in r}
        update["answer"] = _format_finalized_answer(
            answer.lede,
            verdict.kept_claims,
            verdict.note,
            evidence_index=evidence_index,
        )
    elif verdict.action == GateAction.REGENERATE:
        # The synthesize node bumps regenerate_count and reads needs_strict.
        update["needs_strict"] = True

    # DEGRADE leaves answer empty; the graph routes to synthesize_degraded.
    return update


def route_after_gate(state: QAState) -> str:
    verdict = state.get("gate_verdict") or {}
    action = verdict.get("action")
    if action == GateAction.PASS.value or action == GateAction.DROP_AND_NOTE.value:
        return "finalize"
    if action == GateAction.REGENERATE.value:
        return "regenerate"
    return "degrade"
