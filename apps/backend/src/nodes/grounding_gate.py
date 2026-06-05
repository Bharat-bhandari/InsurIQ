"""
Grounding gate — deterministic, no LLM-as-judge.

Resolves each claim's `cites` key against the evidence records the synthesis
node was shown, then checks `status == VERIFIED`. Behavior (locked in the
Step-4 brief, "drop-and-note"):

  - All grounded                            → PASS, keep the answer as-is.
  - LEDE ungrounded                         → REGENERATE (bounded by 2 attempts).
  - One or more NON-lede claims ungrounded  → DROP those claims, KEEP the rest,
                                              append an honest note about what
                                              could not be verified.
  - Lede ungrounded AND regenerate cap hit  → DEGRADE (graph hands off to the
                                              degraded synthesizer).

The gate emits a `GateVerdict` for the receipt; the graph reads `.action` to
route. No randomness, no model — "resolve the key, check the enum."

`VERIFIED` is the only status that means grounded. `USER_CORRECTED` is also
treated as grounded (human edited → highest trust). Everything else
(UNVERIFIED, FLAGGED_UNKNOWN, VERIFICATION_FAILED, CONTRADICTED, plus the
synthetic 'no_record' the tools can emit) is UNGROUNDED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.nodes.synthesize import SynthesisAnswer, SynthesisClaim


# ---------------------------------------------------------------------------
# Verdict shapes
# ---------------------------------------------------------------------------


class GateAction(str, Enum):
    PASS = "pass"
    DROP_AND_NOTE = "drop_and_note"
    REGENERATE = "regenerate"
    DEGRADE = "degrade"


_GROUNDED_STATUSES = {"verified", "user_corrected"}


@dataclass
class DroppedClaim:
    cite: str
    text: str
    reason: str


@dataclass
class GateVerdict:
    action: GateAction
    kept_claims: list[SynthesisClaim] = field(default_factory=list)
    dropped: list[DroppedClaim] = field(default_factory=list)
    note: str | None = None
    # The lede the gate ended up with (may be the original or the synthesis
    # answer's lede if we degrade).
    lede: str | None = None
    lede_cites: str | None = None
    lede_status: str | None = None
    reason: str = ""


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def _index_records(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r["key"]): r for r in records if "key" in r}


def _status_of(cite: str, index: dict[str, dict[str, Any]]) -> str:
    rec = index.get(cite)
    if rec is None:
        return "missing"  # not even in the evidence list
    return str(rec.get("status") or "unverified")


def _is_grounded(status: str) -> bool:
    return status in _GROUNDED_STATUSES


def _format_drop_note(dropped: list[DroppedClaim]) -> str:
    """One honest sentence per dropped claim, joined."""
    if not dropped:
        return ""
    bullets = "; ".join(
        f"couldn't verify '{d.text}' (cite {d.cite} → {d.reason})"
        for d in dropped
    )
    return (
        "Note: I dropped claim(s) I couldn't verify against the policy evidence — "
        f"{bullets}."
    )


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def evaluate(
    answer: SynthesisAnswer,
    evidence_records: list[dict[str, Any]],
    *,
    regenerate_attempts_used: int,
    max_regenerate_attempts: int = 2,
) -> GateVerdict:
    """Apply the drop-and-note policy.

    `regenerate_attempts_used` is the number of regenerate passes already
    performed. When the lede is ungrounded the gate asks for one more
    regenerate up to `max_regenerate_attempts`; past that it degrades.
    """
    index = _index_records(evidence_records)

    lede_status = _status_of(answer.lede_cites, index)
    lede_grounded = _is_grounded(lede_status)

    # Lede ungrounded → regenerate or degrade.
    if not lede_grounded:
        if regenerate_attempts_used < max_regenerate_attempts:
            return GateVerdict(
                action=GateAction.REGENERATE,
                lede=answer.lede,
                lede_cites=answer.lede_cites,
                lede_status=lede_status,
                reason=(
                    f"lede cite {answer.lede_cites!r} is {lede_status}, not grounded; "
                    f"regenerate attempt {regenerate_attempts_used + 1} of "
                    f"{max_regenerate_attempts}"
                ),
            )
        return GateVerdict(
            action=GateAction.DEGRADE,
            lede=answer.lede,
            lede_cites=answer.lede_cites,
            lede_status=lede_status,
            reason=(
                f"lede cite {answer.lede_cites!r} is {lede_status} after "
                f"{regenerate_attempts_used} regenerate attempt(s); degrading."
            ),
        )

    # Lede is grounded — evaluate the supporting claims.
    kept: list[SynthesisClaim] = []
    dropped: list[DroppedClaim] = []
    for claim in answer.claims:
        status = _status_of(claim.cites, index)
        if _is_grounded(status):
            kept.append(claim)
        else:
            dropped.append(
                DroppedClaim(cite=claim.cites, text=claim.text, reason=status)
            )

    if not dropped:
        return GateVerdict(
            action=GateAction.PASS,
            kept_claims=kept,
            lede=answer.lede,
            lede_cites=answer.lede_cites,
            lede_status=lede_status,
            reason="all claims grounded; gate passed",
        )

    return GateVerdict(
        action=GateAction.DROP_AND_NOTE,
        kept_claims=kept,
        dropped=dropped,
        note=_format_drop_note(dropped),
        lede=answer.lede,
        lede_cites=answer.lede_cites,
        lede_status=lede_status,
        reason=f"dropped {len(dropped)} ungrounded claim(s); kept {len(kept)}",
    )
