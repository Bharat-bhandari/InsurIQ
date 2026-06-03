"""
Evidence wrapper — the core type for grounded policy extraction.

Every extracted policy fact is wrapped in `Evidence`. The wrapper answers
four questions about the fact:

  1. What is the value?              → `value`
  2. Where did it come from?         → `spans` (one or more, across layers)
  3. How was it resolved?            → `resolution` (single source, layer join, etc.)
  4. How much should we trust it?    → `status`, `confidence`, `corrected_by_user`

The grounding guarantee: every fact must point to at least one verbatim span
in the source PDF. Anything that can't be grounded is flagged as
FLAGGED_UNKNOWN, never fabricated.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, JsonValue, model_validator


class SourceLayer(str, Enum):
    """
    The three-layer document model (§5 of CONTEXT.md) plus two
    non-authoritative layers we still want to *name* when they appear.

    - WORDING:   authoritative for rules (waiting periods, exclusions, sub-limits)
    - SCHEDULE:  authoritative for this user's values (variant, opted modifications)
    - CIS:       IRDAI-mandated scaffold; useful as an index into wording
    - BLACKLIST: operationally authoritative; do NOT confuse with network list
    - MARKETING: non-authoritative; only appears in CONTRADICTED resolutions
                 (e.g. the "60 months vs 5 years" moratorium contradiction)
    """

    WORDING = "wording"
    SCHEDULE = "schedule"
    CIS = "cis"
    BLACKLIST = "blacklist"
    MARKETING = "marketing"


class VerificationStatus(str, Enum):
    """
    Per-fact trust state. Distinct from per-layer trust (which lives on
    `SourceLayer`). A fact from a high-trust layer can still be unverified.
    """

    UNVERIFIED = "unverified"  # just extracted; verifier hasn't run yet
    VERIFIED = "verified"  # verifier confirmed cited spans support the value
    VERIFICATION_FAILED = "verification_failed"  # verifier could not confirm; needs review
    USER_CORRECTED = "user_corrected"  # human edited; highest trust
    FLAGGED_UNKNOWN = "flagged_unknown"  # extractor couldn't find a value; never guess
    CONTRADICTED = "contradicted"  # layers disagree; needs human resolution


class ResolutionMethod(str, Enum):
    """How `value` was derived from `spans`."""

    SINGLE_SOURCE = "single_source"  # exactly one span; no reconciliation
    LAYER_JOIN = "layer_join"  # multiple layers combined (e.g. wording rule + schedule value)
    CONFLICT_RESOLVED = "conflict_resolved"  # spans disagreed; one won by rule (e.g. clause > marketing)
    USER_OVERRIDE = "user_override"  # human chose the value, overriding extraction


class EvidenceSpan(BaseModel):
    """
    A precise, verifiable location within the policy PDF.

    Spans are immutable pointers — they say "this exact text appears on
    these pages of this layer." They do NOT carry interpretation; that
    lives in `Evidence.value` and `Evidence.resolution`.
    """

    document_id: str = Field(..., min_length=1)
    page_start: int = Field(..., ge=1)
    page_end: int = Field(..., ge=1)
    text: str = Field(
        ...,
        min_length=1,
        description="Verbatim text from the PDF. Do not normalize or strip.",
    )
    clause_ref: str | None = Field(
        default=None,
        description="Clause pointer if present, e.g. '6.2.4(d)' or 'Section II §4'. "
        "NOT an IRDAI exclusion code (Excl01..Excl18) — those are values, not locations.",
    )
    source_type: SourceLayer

    @model_validator(mode="after")
    def _page_range_valid(self) -> EvidenceSpan:
        if self.page_end < self.page_start:
            raise ValueError(
                f"page_end ({self.page_end}) cannot be less than "
                f"page_start ({self.page_start})"
            )
        return self


class ResolutionTrail(BaseModel):
    """
    How `Evidence.value` was derived from `Evidence.spans`.

    Default is SINGLE_SOURCE because that's the common case. For multi-span
    evidence, a more specific method must be set (enforced by Evidence's
    validator).
    """

    method: ResolutionMethod = ResolutionMethod.SINGLE_SOURCE
    reasoning: str | None = Field(
        default=None,
        description="Short note: what the verifier/extractor did to combine spans. "
        "Required for non-single-source resolutions.",
    )


class Evidence(BaseModel):
    """
    One grounded policy fact: a value, its citations, how it was resolved,
    and how much we trust it.

    Used wherever the policy schema needs a fact that must be traceable to
    the source document. e.g.:

        sum_insured: Evidence
        pre_existing_disease_waiting: Evidence

    The `value` field is JsonValue (scalar, list, or dict). Shape discipline
    lives at the policy schema level: the surrounding field name tells you
    what shape to expect. If the extractor produces the wrong shape, that's
    an extractor bug caught in the verification pass — not a type error.

    `value` is None ONLY when status=FLAGGED_UNKNOWN: we looked, we didn't
    find a confident value, but `spans` still point at WHERE we looked
    (grounding-honest).
    """

    value: JsonValue | None = Field(
        default=None,
        description="The extracted value. Scalar (int/float/str/bool), list, or "
        "dict. None ONLY when status=FLAGGED_UNKNOWN. Shape determined by the "
        "surrounding policy schema field.",
    )
    spans: list[EvidenceSpan] = Field(
        ...,
        min_length=1,
        description="Citation chain. Primary/authoritative span FIRST; "
        "supporting spans follow. Order is meaningful.",
    )
    resolution: ResolutionTrail = Field(default_factory=ResolutionTrail)
    status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Set by the verification node, NOT the extractor. "
        "LLM self-reported confidence is not meaningful here.",
    )
    corrected_by_user: bool = Field(
        default=False,
        description="True if a human edited this fact in the review UI. "
        "Full audit trail lives in Postgres, not on this object.",
    )
    notes: str | None = None

    @model_validator(mode="after")
    def _resolution_matches_span_count(self) -> Evidence:
        """
        SINGLE_SOURCE ⇔ exactly one span. Catches the silent-lie case where
        multiple spans got attached but resolution still says single source.
        """
        n = len(self.spans)
        method = self.resolution.method

        if method == ResolutionMethod.SINGLE_SOURCE and n != 1:
            raise ValueError(
                f"resolution.method=SINGLE_SOURCE requires exactly 1 span, got {n}. "
                f"Set a more specific ResolutionMethod (LAYER_JOIN, "
                f"CONFLICT_RESOLVED, or USER_OVERRIDE)."
            )
        if method != ResolutionMethod.SINGLE_SOURCE and n == 1:
            raise ValueError(
                f"resolution.method={method.value} with only 1 span is inconsistent. "
                f"Use SINGLE_SOURCE for one-span evidence."
            )
        return self

    @model_validator(mode="after")
    def _flagged_unknown_consistent(self) -> Evidence:
        """
        FLAGGED_UNKNOWN means "we looked, we didn't find a confident value."
        - value MUST be None (otherwise it's not unknown)
        - spans still required (handled by min_length=1): they point at where we looked
        """
        if self.status == VerificationStatus.FLAGGED_UNKNOWN and self.value is not None:
            raise ValueError(
                "FLAGGED_UNKNOWN requires value=None; got a value, which "
                "contradicts 'we couldn't extract this'. If you have a value, "
                "use UNVERIFIED or VERIFIED instead."
            )
        if self.status != VerificationStatus.FLAGGED_UNKNOWN and self.value is None:
            raise ValueError(
                f"status={self.status.value} requires a non-None value. "
                f"Use FLAGGED_UNKNOWN if extraction couldn't find a value."
            )
        return self
