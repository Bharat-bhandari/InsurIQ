"""
4.4 isolation proof: the grounding gate, three cases, no LLM involved.

Run from apps/backend/:
    uv run python -m scripts.prove_grounding_gate

Cases (locked):
  (a) fully-grounded answer  → PASS
  (b) non-lede claim cites a FLAGGED_UNKNOWN key  → DROP_AND_NOTE
  (c) lede cites a missing/unverified key  → REGENERATE (then DEGRADE at cap)
"""

from __future__ import annotations

import sys

from src.nodes.grounding_gate import GateAction, evaluate
from src.nodes.synthesize import SynthesisAnswer, SynthesisClaim


# Synthetic evidence list — mirrors what the tools would have produced.
EVIDENCE = [
    {
        "key": "ev_specific_wait",
        "value": 24,
        "status": "verified",
        "clause": "5.1.2",
        "page": 37,
        "notes": None,
    },
    {
        "key": "ev_longer_rule",
        "value": "If any of the specified disease ...",
        "status": "verified",
        "clause": "5.1.2(c)",
        "page": 37,
        "notes": None,
    },
    {
        "key": "ev_room_rent_cap",
        "value": None,
        "status": "flagged_unknown",
        "clause": "4.21",
        "page": 36,
        "notes": "Platinum+ does not state a per-day cap.",
    },
]


def case_a_pass() -> bool:
    print("\n--- case (a) fully grounded → PASS ---")
    ans = SynthesisAnswer(
        lede="Yes — covered, after a 24-month waiting period.",
        lede_cites="ev_specific_wait",
        claims=[
            SynthesisClaim(
                text="Joint replacement falls under the 24-month specific-disease waiting.",
                cites="ev_specific_wait",
            ),
            SynthesisClaim(
                text="If it is also pre-existing, the longer of the two waits applies.",
                cites="ev_longer_rule",
            ),
        ],
    )
    v = evaluate(ans, EVIDENCE, regenerate_attempts_used=0)
    print(f"action: {v.action}")
    print(f"reason: {v.reason}")
    print(f"kept_claims: {len(v.kept_claims)}  dropped: {len(v.dropped)}")
    return v.action == GateAction.PASS and len(v.kept_claims) == 2 and not v.dropped


def case_b_drop_and_note() -> bool:
    print("\n--- case (b) one non-lede claim cites FLAGGED_UNKNOWN → DROP_AND_NOTE ---")
    ans = SynthesisAnswer(
        lede="Yes — covered, after a 24-month waiting period.",
        lede_cites="ev_specific_wait",
        claims=[
            SynthesisClaim(
                text="Joint replacement falls under the 24-month specific-disease waiting.",
                cites="ev_specific_wait",
            ),
            SynthesisClaim(
                text="The room rent is capped at INR 5,000 per day.",
                cites="ev_room_rent_cap",
            ),
        ],
    )
    v = evaluate(ans, EVIDENCE, regenerate_attempts_used=0)
    print(f"action: {v.action}")
    print(f"reason: {v.reason}")
    print(f"kept_claims: {[c.cites for c in v.kept_claims]}")
    print(f"dropped:     {[(d.cite, d.reason) for d in v.dropped]}")
    print(f"note:        {v.note}")
    return (
        v.action == GateAction.DROP_AND_NOTE
        and len(v.kept_claims) == 1
        and v.kept_claims[0].cites == "ev_specific_wait"
        and len(v.dropped) == 1
        and v.dropped[0].cite == "ev_room_rent_cap"
        and v.note is not None
        and "ev_room_rent_cap" in v.note
    )


def case_c_regenerate_then_degrade() -> bool:
    print("\n--- case (c) lede cites missing/unverified key → REGENERATE, then DEGRADE ---")
    ans = SynthesisAnswer(
        lede="Yes — covered, with a hard room rent cap of INR 5,000 per day.",
        lede_cites="ev_room_rent_cap",  # FLAGGED_UNKNOWN → ungrounded
        claims=[
            SynthesisClaim(
                text="Specific-disease waiting is 24 months.",
                cites="ev_specific_wait",
            )
        ],
    )

    v0 = evaluate(ans, EVIDENCE, regenerate_attempts_used=0)
    print(f"attempt 0 -> action: {v0.action}  reason: {v0.reason}")

    v1 = evaluate(ans, EVIDENCE, regenerate_attempts_used=1)
    print(f"attempt 1 -> action: {v1.action}  reason: {v1.reason}")

    v2 = evaluate(ans, EVIDENCE, regenerate_attempts_used=2)
    print(f"attempt 2 -> action: {v2.action}  reason: {v2.reason}")

    # Also confirm "missing key entirely" path.
    ans_missing = SynthesisAnswer(
        lede="Yes — covered.",
        lede_cites="ev_nonexistent_key",
        claims=[],
    )
    v_missing = evaluate(ans_missing, EVIDENCE, regenerate_attempts_used=0)
    print(f"missing-key lede attempt 0 -> action: {v_missing.action}  "
          f"reason: {v_missing.reason}")

    return (
        v0.action == GateAction.REGENERATE
        and v1.action == GateAction.REGENERATE
        and v2.action == GateAction.DEGRADE
        and v_missing.action == GateAction.REGENERATE
    )


def main() -> int:
    results = {
        "a_pass": case_a_pass(),
        "b_drop_and_note": case_b_drop_and_note(),
        "c_regenerate_then_degrade": case_c_regenerate_then_degrade(),
    }
    print("\n=== summary ===")
    for k, v in results.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
