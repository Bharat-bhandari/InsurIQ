"""
Small constructors for hand-assembling seed `Policy` fixtures.

These helpers exist so the fixture reads as policy data, not Pydantic plumbing,
and so it cannot accidentally violate the Evidence validators (spans/value/
status/resolution all have to agree). Each helper enforces one validator rule
up-front instead of letting Pydantic raise from deep in a 200-line literal.

Rules they enforce:
  * SINGLE_SOURCE only ever has 1 span; multi-span always has an explicit
    LAYER_JOIN / CONFLICT_RESOLVED / USER_OVERRIDE method (and a reasoning).
  * FLAGGED_UNKNOWN evidence has value=None and confidence defaults to 0.0;
    spans still point at WHERE we looked.
"""

from __future__ import annotations

from pydantic import JsonValue

from src.states.evidence import (
    Evidence,
    EvidenceSpan,
    ResolutionMethod,
    ResolutionTrail,
    SourceLayer,
    VerificationStatus,
)

DEFAULT_DOC_ID = "niva-bupa-reassure-2"


def span(
    page: int,
    text: str,
    *,
    clause: str | None = None,
    layer: SourceLayer = SourceLayer.WORDING,
    doc: str = DEFAULT_DOC_ID,
) -> EvidenceSpan:
    """Make an EvidenceSpan that points at exactly one page of the source PDF.

    `text` must be VERBATIM from the PDF — do not summarize or normalize.
    """
    return EvidenceSpan(
        document_id=doc,
        page_start=page,
        page_end=page,
        text=text,
        clause_ref=clause,
        source_type=layer,
    )


def verified(
    value: JsonValue,
    *spans: EvidenceSpan,
    method: ResolutionMethod | None = None,
    reasoning: str | None = None,
    confidence: float = 0.95,
    notes: str | None = None,
) -> Evidence:
    """Build a VERIFIED Evidence.

    Single-span calls auto-select SINGLE_SOURCE. Multi-span calls REQUIRE an
    explicit method (and benefit from a reasoning) — the Evidence validator
    will reject the alternatives anyway, but failing here gives a better error.
    """
    if not spans:
        raise ValueError("verified() requires at least one span")

    if len(spans) == 1:
        if method is not None and method != ResolutionMethod.SINGLE_SOURCE:
            raise ValueError(
                f"single-span evidence must use SINGLE_SOURCE; got {method}"
            )
        resolution = ResolutionTrail(
            method=ResolutionMethod.SINGLE_SOURCE,
            reasoning=reasoning,
        )
    else:
        if method is None or method == ResolutionMethod.SINGLE_SOURCE:
            raise ValueError(
                f"multi-span evidence ({len(spans)} spans) requires an explicit "
                f"method (LAYER_JOIN / CONFLICT_RESOLVED / USER_OVERRIDE)"
            )
        resolution = ResolutionTrail(method=method, reasoning=reasoning)

    return Evidence(
        value=value,
        spans=list(spans),
        resolution=resolution,
        status=VerificationStatus.VERIFIED,
        confidence=confidence,
        notes=notes,
    )


def flagged_unknown(
    *spans: EvidenceSpan,
    confidence: float = 0.0,
    notes: str | None = None,
) -> Evidence:
    """Build a FLAGGED_UNKNOWN Evidence (value=None) — "we looked here, no value."

    Spans are still REQUIRED: they document where we searched. A flagged-unknown
    fact with citations is honest; a fabricated value is the bug we exist to
    prevent.
    """
    if not spans:
        raise ValueError(
            "flagged_unknown requires at least one span — record where we LOOKED"
        )

    if len(spans) == 1:
        resolution = ResolutionTrail(method=ResolutionMethod.SINGLE_SOURCE)
    else:
        resolution = ResolutionTrail(
            method=ResolutionMethod.LAYER_JOIN,
            reasoning="searched multiple layers; no confident value found",
        )

    return Evidence(
        value=None,
        spans=list(spans),
        resolution=resolution,
        status=VerificationStatus.FLAGGED_UNKNOWN,
        confidence=confidence,
        notes=notes,
    )
