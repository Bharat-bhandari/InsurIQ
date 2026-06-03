"""
Policy schema — the structured output of the extraction pipeline.

A `Policy` represents one fully-extracted health insurance policy. It mirrors
the three-layer document model (§5 of CONTEXT.md):

  - `rules`:    facts derived from the Wording layer (the contract itself)
  - `schedule`: facts derived from the Schedule/Certificate (THIS user's values)
  - `resolved`: facts computed by joining rules + schedule (this user's actual
                exposure to the rules)

The CIS layer is NOT a top-level region — CIS rows index *into* the wording,
so CIS-derived facts live under `rules` with CIS spans as supporting evidence.

Every fact is wrapped in `Evidence`. Two patterns for "we couldn't extract":

  - Required-by-IRDAI fields that should always exist (PED waiting, room rent,
    sub-limits etc.): use FLAGGED_UNKNOWN with value=None. Grounding-honest:
    "we looked here, we didn't find it confidently."
  - Genuinely optional fields (maternity in a non-maternity plan, optional
    rider grids): the whole field is Optional[Evidence] and may be None.

Variant-specific benefit tables (ReAssure+, Booster+) live as JSONB-flex
`Evidence` whose value is a dict — their structure isn't stable across
products.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field

from src.states.evidence import Evidence


# ---------------------------------------------------------------------------
# Identity (the policy itself, not facts about it)
# ---------------------------------------------------------------------------


class PolicyIdentity(BaseModel):
    """
    What policy is this? Identifiers and bookkeeping; NOT user PII.

    PII rule (§6 of CONTEXT.md): personal identity fields (names, DOB, address,
    customer ID, CKYC) are an access-controlled concern stored SEPARATELY.
    They are not on this model. If you need them, they live in a different
    table joined by `policy_id`.
    """

    policy_id: str = Field(..., description="Our internal id, generated at upload.")
    document_id: str = Field(..., description="The PDF this was extracted from.")
    insurer_name: Evidence = Field(..., description="e.g. 'Niva Bupa Health Insurance'.")
    product_name: Evidence = Field(..., description="e.g. 'ReAssure 2.0'.")
    uin: Evidence | None = Field(
        default=None,
        description="IRDAI Unique Identification Number. Present on every "
        "IRDAI-approved product but occasionally hard to extract.",
    )


# ---------------------------------------------------------------------------
# Standard IRDAI-defined concepts (stable across all Indian health insurers)
# ---------------------------------------------------------------------------


class IRDAIExclusionCode(str, Enum):
    """
    IRDAI standard exclusion codes. Stable across every Indian health policy
    per IRDAI standardization. The string value is what would appear in a
    clause; the enum lets us reference them in code without typos.
    """

    EXCL01 = "Excl01"  # Pre-existing diseases
    EXCL02 = "Excl02"  # Specified disease/procedure waiting
    EXCL03 = "Excl03"  # 30-day waiting period
    EXCL04 = "Excl04"  # Investigation & evaluation
    EXCL05 = "Excl05"  # Rest cure, rehabilitation
    EXCL06 = "Excl06"  # Obesity / weight control
    EXCL07 = "Excl07"  # Change of gender
    EXCL08 = "Excl08"  # Cosmetic / plastic surgery
    EXCL09 = "Excl09"  # Hazardous / adventure sports
    EXCL10 = "Excl10"  # Breach of law
    EXCL11 = "Excl11"  # Excluded providers
    EXCL12 = "Excl12"  # Substance abuse
    EXCL13 = "Excl13"  # Wellness and rejuvenation
    EXCL14 = "Excl14"  # Dietary supplements
    EXCL15 = "Excl15"  # Refractive error
    EXCL16 = "Excl16"  # Unproven treatments
    EXCL17 = "Excl17"  # Sterility and infertility
    EXCL18 = "Excl18"  # Maternity (when not opted)


# ---------------------------------------------------------------------------
# Rules layer — derived from the Wording (the contract)
# ---------------------------------------------------------------------------


class WaitingPeriods(BaseModel):
    """
    All waiting periods from the wording. Each is an Evidence-wrapped fact.

    Important meta-rule (proven against the real Niva Bupa doc): when multiple
    waiting periods could apply to the same condition, the LONGER applies.
    That rule itself is an Evidence — it's a clause too, and it's load-bearing
    for correctly answering joint PED+specific-disease questions.
    """

    initial_waiting_days: Evidence = Field(
        ...,
        description="Initial waiting period in days (typically 30, except for "
        "accidents). IRDAI Excl03.",
    )
    pre_existing_disease_months: Evidence = Field(
        ...,
        description="PED waiting from the wording. May be variant-dependent "
        "(e.g. '36 months, 48 for Bronze/Silver/Gold'). IRDAI Excl01. The "
        "per-user resolved value lives in `resolved.effective_ped_waiting_months`.",
    )
    specific_disease_months: Evidence = Field(
        ...,
        description="Specific disease/procedure waiting (joint replacement, "
        "hernia, etc.). IRDAI Excl02. Typically 24 months.",
    )
    specific_diseases_listed: Evidence = Field(
        ...,
        description="The list of specific diseases/procedures the above waiting "
        "applies to. Value is a JSON list of strings.",
    )
    longer_waiting_rule: Evidence | None = Field(
        default=None,
        description="The meta-rule 'longer of applicable waiting periods applies', "
        "when stated explicitly in the wording. Critical for answering "
        "joint-PED-plus-specific-disease questions correctly.",
    )


class StandardExclusion(BaseModel):
    """
    One IRDAI-standard exclusion (Excl01..Excl18) as it appears in this policy.

    The CODE is stable across insurers; the EXACT WORDING and SCOPE can vary
    slightly. `text` captures the verbatim per-policy text.
    """

    code: IRDAIExclusionCode
    text: Evidence = Field(
        ..., description="Verbatim exclusion text as it appears in the wording."
    )


class RoomRentRule(BaseModel):
    """
    Room rent rules from the wording. Whether they BITE for this user depends
    on whether room-modification was opted in the Schedule. The bite-or-not
    resolved fact lives in `resolved.room_rent_proportionate_deduction_applies`,
    not here.
    """

    room_rent_limit: Evidence | None = Field(
        default=None,
        description="Room rent cap from wording (e.g. 'Single Private AC Room' "
        "or '1% of sum insured per day'). None if no cap.",
    )
    proportionate_deduction: Evidence | None = Field(
        default=None,
        description="If room category is upgraded beyond the eligible category, "
        "charges are proportionately deducted. The infamous page-47 clause "
        "in Niva Bupa ReAssure 2.0.",
    )


class SubLimit(BaseModel):
    """One named sub-limit (cataract, knee replacement, etc.)."""

    condition: Evidence = Field(..., description="What this sub-limit applies to.")
    limit: Evidence = Field(..., description="The numeric/structured limit.")


class CoPayRule(BaseModel):
    """
    Co-pay rules from the wording. Co-pay rules in the wording are typically
    *conditional* (e.g. "if opted: 10%, 20%, ..."). The per-user actual co-pay
    is in the Schedule and resolves into `resolved.effective_copay_percentage`.
    """

    available_options: Evidence | None = Field(
        default=None,
        description="What co-pay levels are available per the wording.",
    )
    age_based_copay: Evidence | None = Field(
        default=None,
        description="Age-triggered mandatory co-pay (e.g. '20% for entry age "
        "above 60'). Independent of opted co-pay.",
    )


class ClaimsMechanics(BaseModel):
    """
    How claims work: intimation deadlines, document window, moratorium.
    """

    cashless_intimation_hours: Evidence | None = None
    reimbursement_submission_days: Evidence | None = None
    pre_hospitalization_days: Evidence | None = None
    post_hospitalization_days: Evidence | None = None
    moratorium_months: Evidence | None = Field(
        default=None,
        description="After this many months, the policy is incontestable except "
        "for fraud. Note the §5 'moratorium contradiction' case: structured "
        "clause text wins over marketing sidebars; verifier must enforce.",
    )


class BlacklistEntry(BaseModel):
    """
    One un-recognized / blacklisted hospital. Operationally important: do NOT
    confuse this with the network hospital list (different layer, different role).
    """

    hospital_name: Evidence
    location: Evidence | None = None


class PolicyRules(BaseModel):
    """
    Everything derived from the Wording layer. These facts are about the
    contract; they do NOT depend on which user holds this policy.

    Stable, IRDAI-standardized fields are typed. Variant-specific benefit
    grids (ReAssure+, Booster+) are JSONB-flex via `variant_features`.
    """

    waiting_periods: WaitingPeriods
    standard_exclusions: list[StandardExclusion] = Field(default_factory=list)
    non_standard_exclusions: list[Evidence] = Field(
        default_factory=list,
        description="Insurer-specific exclusions not covered by Excl01..Excl18.",
    )
    room_rent: RoomRentRule
    sub_limits: list[SubLimit] = Field(default_factory=list)
    co_pay: CoPayRule
    claims_mechanics: ClaimsMechanics
    blacklist: list[BlacklistEntry] = Field(default_factory=list)

    variant_features: Evidence | None = Field(
        default=None,
        description="JSONB-flex region for variant-specific benefit tables that "
        "don't fit a stable schema (ReAssure+/Booster+ grids, optional rider "
        "structures). Evidence.value is a dict; structure is per-product.",
    )


# ---------------------------------------------------------------------------
# Schedule layer — derived from this user's Certificate
# ---------------------------------------------------------------------------


class InsuredMember(BaseModel):
    """
    One member covered by this policy. Identity fields (name, DOB, customer
    ID) are NOT here — PII rule §6. Only what affects coverage logic.
    """

    relationship: Evidence = Field(
        ..., description="self / spouse / child / parent / parent-in-law."
    )
    age_at_inception: Evidence
    declared_pre_existing_diseases: Evidence = Field(
        ...,
        description="Value is a JSON list of declared PEDs. May be empty list. "
        "'None declared' is a value, not absence of evidence.",
    )


class PolicySchedule(BaseModel):
    """
    Everything derived from the Schedule/Certificate layer. These facts are
    THIS user's actual chosen values.

    Schedule facts are user-correctable in the review UI. Rules facts are not.
    Keeping them in separate regions makes the correction permission
    structural, not a per-field flag.
    """

    plan_variant: Evidence = Field(
        ...,
        description="e.g. 'Platinum+', 'Gold'. Determines which wording "
        "variant-clauses apply to this user.",
    )
    sum_insured: Evidence
    policy_start_date: Evidence
    policy_end_date: Evidence
    members: list[InsuredMember]

    copay_opted: Evidence = Field(
        ...,
        description="The per-user opted co-pay. Often 'Not Opted'. Resolves "
        "with wording's CoPayRule into resolved.effective_copay_percentage.",
    )
    room_modification_opted: Evidence = Field(
        ...,
        description="Whether room-type modification rider was opted. Determines "
        "whether the proportionate-deduction clause BITES for this user.",
    )
    optional_benefits_opted: Evidence | None = Field(
        default=None,
        description="JSONB-flex: which optional benefits (Booster, Safeguard+, "
        "Personal Accident, etc.) are active. Structure varies by product.",
    )


# ---------------------------------------------------------------------------
# Resolved layer — facts computed by joining rules + schedule
# ---------------------------------------------------------------------------


class ResolvedFacts(BaseModel):
    """
    Facts derived by joining the wording rules with this user's schedule
    values. Each is multi-span Evidence with resolution.method = LAYER_JOIN
    (or CONFLICT_RESOLVED for contradictions; USER_OVERRIDE after review).

    These are the facts the UI shows the user as "what applies to YOU."
    They're the answer to "what did I actually buy."

    Materialized at extraction time, not at Q&A time, so that:
      - resolution happens once (consistency)
      - the resolution is human-reviewable in the same UI as raw facts
      - downstream Q&A doesn't re-derive logic on every question
    """

    effective_ped_waiting_months: Evidence = Field(
        ...,
        description="The PED waiting that ACTUALLY applies to this user "
        "(considers variant + declared PEDs + 'longer applies' meta-rule). "
        "May be 0 if no PED was declared.",
    )
    effective_copay_percentage: Evidence = Field(
        ...,
        description="The co-pay rate that ACTUALLY applies to this user. "
        "0 if Not Opted and not age-triggered.",
    )
    room_rent_proportionate_deduction_applies: Evidence = Field(
        ...,
        description="Boolean: does the proportionate-deduction clause bite for "
        "this user? Depends on room_modification_opted.",
    )


# ---------------------------------------------------------------------------
# The top-level Policy
# ---------------------------------------------------------------------------


class Policy(BaseModel):
    """
    A fully-extracted health insurance policy: rules + this user's schedule
    + resolved per-user facts, every fact grounded in the source PDF.

    This is what the extraction pipeline produces and what the review UI,
    Q&A node, and Postgres layer consume.
    """

    identity: PolicyIdentity
    rules: PolicyRules
    schedule: PolicySchedule
    resolved: ResolvedFacts

    extracted_at: date
    schema_version: str = Field(
        default="0.1.0",
        description="Bump this when the schema changes incompatibly. Persisted "
        "with the row so migrations are tractable.",
    )
