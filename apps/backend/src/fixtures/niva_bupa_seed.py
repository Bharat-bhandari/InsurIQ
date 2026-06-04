"""
Seed `Policy` fixture for PolicyDesk.

Source PDF: Niva Bupa ReAssure 2.0, Policy 34884769202601, Platinum+ variant,
issued 26/03/2026 for the policy period 29/03/2026 → 28/03/2027.

This fixture is hand-assembled (one-time, not extracted) because the hackathon
project is the *resilient Q&A tier on top of* an extracted Policy — extraction
itself is explicitly out of scope (CONTEXT.md §A2).

Layout mirrors the schema:
  identity  → who issued / what product
  rules     → from the wording (the contract)
  schedule  → from this user's certificate
  resolved  → wording × schedule joined for THIS user

Verbatim spans + real page numbers everywhere a Tier-A fact lands; honest
FLAGGED_UNKNOWNs where the policy doesn't state the fact.
"""

from __future__ import annotations

from datetime import date

from src.fixtures._builders import flagged_unknown, span, verified
from src.states.evidence import ResolutionMethod, SourceLayer
from src.states.policy import (
    BlacklistEntry,
    ClaimsMechanics,
    CoPayRule,
    InsuredMember,
    IRDAIExclusionCode,
    Policy,
    PolicyIdentity,
    PolicyRules,
    PolicySchedule,
    ResolvedFacts,
    RoomRentRule,
    StandardExclusion,
    SubLimit,
    WaitingPeriods,
)

# ---------------------------------------------------------------------------
# 1. Identity
# ---------------------------------------------------------------------------

_identity = PolicyIdentity(
    policy_id="seed-niva-bupa-reassure-2-platinum-plus",
    document_id="niva-bupa-reassure-2",
    insurer_name=verified(
        "Niva Bupa Health Insurance Company Limited",
        span(
            4,
            "For and on behalf of Niva Bupa Health Insurance Company Limited",
            clause="Insurance Certificate",
            layer=SourceLayer.SCHEDULE,
        ),
    ),
    product_name=verified(
        "ReAssure 2.0",
        span(
            4,
            "Product Name: ReAssure 2.0 | Product UIN: NBHHLIP26042V022526",
            clause="page footer",
            layer=SourceLayer.SCHEDULE,
        ),
    ),
    uin=verified(
        "NBHHLIP26042V022526",
        span(
            4,
            "Product Name: ReAssure 2.0 | Product UIN: NBHHLIP26042V022526",
            clause="page footer",
            layer=SourceLayer.SCHEDULE,
        ),
    ),
)


# ---------------------------------------------------------------------------
# 2. Rules — from the Wording layer
# ---------------------------------------------------------------------------

# ---- Waiting periods (Tier A: all verbatim, real pages) ----

_waiting_periods = WaitingPeriods(
    initial_waiting_days=verified(
        30,
        span(
            37,
            "Expenses related to the treatment of any Illness within 30 days from the first Policy commencement date shall be excluded except claims arising due to an Accident, provided the same are covered.",
            clause="5.1.3 (Excl03)",
        ),
    ),
    pre_existing_disease_months=verified(
        36,
        span(
            36,
            "Expenses related to the treatment of a Pre-existing Disease (PED) and its direct complications shall be excluded until the expiry of 36 months of continuous coverage after the date of inception of the first Policy.",
            clause="5.1.1 (Excl01)",
        ),
    ),
    specific_disease_months=verified(
        24,
        span(
            37,
            "Expenses related to the treatment of the listed conditions, surgeries/treatments shall be excluded until the expiry of 24 months of continuous coverage after the date of inception of the first Policy. This exclusion shall not be applicable for claims arising due to an Accident (covered from day 1) or Cancer (covered after 30-day waiting period).",
            clause="5.1.2 (Excl02)",
        ),
    ),
    specific_diseases_listed=verified(
        [
            "Pancreatitis and stones in biliary and urinary system",
            "Cataract, glaucoma and retinal detachment",
            "Hyperplasia of prostate, hydrocele and spermatocele",
            "Prolapse uterus or cervix, endometriosis, Fibroids, Polycystic ovarian disease (PCOD), hysterectomy (unless necessitated by Malignancy)",
            "Hemorrhoids, fissure, fistula or abscess of anal and rectal region",
            "Hernia of any site or type",
            "Osteoarthritis, joint replacement, osteoporosis, systemic connective tissue disorders, inflammatory polyarthropathies, Rheumatoid Arthritis, gout, intervertebral disc disorders, arthroscopic surgeries for ligament repair",
            "Varicose veins of lower extremities",
            "All internal or external benign neoplasms/ tumours, cyst, sinus, polyps, nodules, mass or lump",
            "Ulcer, erosion or varices of gastro intestinal tract",
            "Surgical treatment for diseases of middle ear and mastoid (including otitis media, cholesteatoma, perforation of tympanic membrane), Tonsils and adenoids, nasal septum and nasal sinuses",
        ],
        span(
            37,
            "f. List of specific diseases/procedures: i. Pancreatitis and stones in biliary and urinary system ii. Cataract, glaucoma and retinal detachment iii. Hyperplasia of prostate, hydrocele and spermatocele iv. Prolapse uterus or cervix, endometriosis, Fibroids, Polycystic ovarian disease (PCOD), hysterectomy (unless necessitated by Malignancy) v. Hemorrhoids, fissure, fistula or abscess of anal and rectal region vi. Hernia of any site or type, vii. Osteoarthritis, joint replacement, osteoporosis, systemic connective tissue disorders, inflammatory polyarthropathies, Rheumatoid Arthritis, gout, intervertebral disc disorders, arthroscopic surgeries for ligament repair viii. Varicose veins of lower extremities ix. All internal or external benign neoplasms/ tumours, cyst, sinus, polyps, nodules, mass or lump x. Ulcer, erosion or varices of gastro intestinal tract xi. Surgical treatment for diseases of middle ear and mastoid (including otitis media, cholesteatoma, perforation of tympanic membrane), Tonsils and adenoids, nasal septum and nasal sinuses",
            clause="5.1.2(f)",
        ),
    ),
    # The load-bearing meta-rule that drives the knee-surgery demo answer.
    longer_waiting_rule=verified(
        "If any of the specified disease/procedure falls under the waiting period specified for pre-Existing diseases, then the longer of the two waiting periods shall apply.",
        span(
            37,
            "If any of the specified disease/procedure falls under the waiting period specified for pre-Existing diseases, then the longer of the two waiting periods shall apply.",
            clause="5.1.2(c)",
        ),
    ),
)


# ---- Standard exclusions (Tier B: real clauses, page-grounded) ----

_standard_exclusions = [
    StandardExclusion(
        code=IRDAIExclusionCode.EXCL01,
        text=verified(
            "Expenses related to the treatment of a Pre-existing Disease (PED) and its direct complications shall be excluded until the expiry of 36 months of continuous coverage after the date of inception of the first Policy.",
            span(
                36,
                "Expenses related to the treatment of a Pre-existing Disease (PED) and its direct complications shall be excluded until the expiry of 36 months of continuous coverage after the date of inception of the first Policy.",
                clause="5.1.1 (Excl01)",
            ),
        ),
    ),
    StandardExclusion(
        code=IRDAIExclusionCode.EXCL02,
        text=verified(
            "Expenses related to the treatment of the listed conditions, surgeries/treatments shall be excluded until the expiry of 24 months of continuous coverage after the date of inception of the first Policy. This exclusion shall not be applicable for claims arising due to an Accident (covered from day 1) or Cancer (covered after 30-day waiting period).",
            span(
                37,
                "Expenses related to the treatment of the listed conditions, surgeries/treatments shall be excluded until the expiry of 24 months of continuous coverage after the date of inception of the first Policy. This exclusion shall not be applicable for claims arising due to an Accident (covered from day 1) or Cancer (covered after 30-day waiting period).",
                clause="5.1.2 (Excl02)",
            ),
        ),
    ),
    StandardExclusion(
        code=IRDAIExclusionCode.EXCL03,
        text=verified(
            "Expenses related to the treatment of any Illness within 30 days from the first Policy commencement date shall be excluded except claims arising due to an Accident, provided the same are covered.",
            span(
                37,
                "Expenses related to the treatment of any Illness within 30 days from the first Policy commencement date shall be excluded except claims arising due to an Accident, provided the same are covered.",
                clause="5.1.3 (Excl03)",
            ),
        ),
    ),
    StandardExclusion(
        code=IRDAIExclusionCode.EXCL06,
        text=verified(
            "Expenses related to the surgical treatment of obesity that does not fulfil all the below conditions: a. Surgery to be conducted is upon the advice of the Doctor. b. The surgery/Procedure conducted should be supported by clinical protocols. c. The member has to be 18 years of age or older and; d. Body Mass Index (BMI); greater than or equal to 40 or greater than or equal to 35 in conjunction with severe co-morbidities.",
            span(
                38,
                "Expenses related to the surgical treatment of obesity that does not fulfil all the below conditions",
                clause="5.1.6 (Excl06)",
            ),
            confidence=0.85,
            notes="paraphrased for fixture; full clause spans multiple bullet points",
        ),
    ),
    StandardExclusion(
        code=IRDAIExclusionCode.EXCL08,
        text=verified(
            "Expenses for cosmetic or plastic surgery or any treatment to change appearance unless for reconstruction following an Accident, Burn(s) or Cancer or as part of medically necessary treatment to remove a direct and immediate health risk to the insured.",
            span(
                38,
                "Expenses for cosmetic or plastic surgery or any treatment to change appearance unless for reconstruction following an Accident, Burn(s) or Cancer or as part of medically necessary treatment to remove a direct and immediate health risk to the insured.",
                clause="5.1.7 (Excl08)",
            ),
        ),
    ),
    StandardExclusion(
        code=IRDAIExclusionCode.EXCL09,
        text=verified(
            "Expenses related to any treatment necessitated due to participation as a professional in hazardous or adventure sports, including but not limited to, para-jumping, rock climbing, mountaineering, rafting, motor racing, horse racing or scuba diving, hand gliding, sky diving, deep-sea diving.",
            span(
                38,
                "Expenses related to any treatment necessitated due to participation as a professional in hazardous or adventure sports, including but not limited to, para-jumping, rock climbing, mountaineering, rafting, motor racing, horse racing or scuba diving, hand gliding, sky diving, deep-sea diving.",
                clause="5.1.8 (Excl09)",
            ),
        ),
    ),
    StandardExclusion(
        code=IRDAIExclusionCode.EXCL15,
        text=verified(
            "Expenses related to the treatment for correction of eye sight due to refractive error less than 7.5 dioptres.",
            span(
                39,
                "Expenses related to the treatment for correction of eye sight due to refractive error less than 7.5 dioptres.",
                clause="5.1.13 (Excl15)",
            ),
        ),
    ),
    StandardExclusion(
        code=IRDAIExclusionCode.EXCL16,
        text=verified(
            "Expenses related to any unproven treatment, services and supplies for or in connection with any treatment. Unproven treatments are treatments, procedures or supplies that lack significant medical documentation to support their effectiveness.",
            span(
                39,
                "Expenses related to any unproven treatment, services and supplies for or in connection with any treatment. Unproven treatments are treatments, procedures or supplies that lack significant medical documentation to support their effectiveness.",
                clause="5.1.14 (Excl16)",
            ),
        ),
    ),
    StandardExclusion(
        code=IRDAIExclusionCode.EXCL17,
        text=verified(
            "Expenses related to sterility and infertility. This includes: a. Any type of contraception, sterilization b. Assisted Reproduction services including artificial insemination and advanced reproductive technologies such as IVF, ZIFT, GIFT, ICSI c. Gestational Surrogacy d. Reversal of sterilization",
            span(
                39,
                "Expenses related to sterility and infertility. This includes: a. Any type of contraception, sterilization b. Assisted Reproduction services including artificial insemination and advanced reproductive technologies such as IVF, ZIFT, GIFT, ICSI c. Gestational Surrogacy d. Reversal of sterilization",
                clause="5.1.15 (Excl17)",
            ),
        ),
    ),
    StandardExclusion(
        code=IRDAIExclusionCode.EXCL18,
        text=verified(
            "a. Medical treatment expenses traceable to childbirth (including complicated deliveries and caesarean sections incurred during Hospitalization) except ectopic pregnancy; b. Expenses towards miscarriage (unless due to an Accident) and lawful medical termination of pregnancy during the Policy Period.",
            span(
                39,
                "a. Medical treatment expenses traceable to childbirth (including complicated deliveries and caesarean sections incurred during Hospitalization) except ectopic pregnancy; b. Expenses towards miscarriage (unless due to an Accident) and lawful medical termination of pregnancy during the Policy Period.",
                clause="5.1.16 (Excl18)",
            ),
        ),
    ),
]


# ---- Room rent (Tier A: the load-bearing page-47 clause) ----

_room_rent = RoomRentRule(
    # The Platinum+ variant lets the user choose room category at hospital
    # admission and does not put an explicit Rs/day cap; the cap surfaces only
    # if the Room Type Modification optional is opted (here it is NOT).
    # Grounding-honest: no extracted limit → FLAGGED_UNKNOWN with the search span.
    room_rent_limit=flagged_unknown(
        span(
            36,
            "You can choose between a Single Private Room and a Sharing Room. Irrespective of the Room type you choose, ICU admission will always be paid up to Base Sum Insured.",
            clause="4.21 Room Type Modification",
        ),
        notes=(
            "The wording does not state a per-day room rent cap for Platinum+. "
            "Room category becomes restrictive only when 'Room Type Modification' "
            "is opted (not opted on this policy)."
        ),
    ),
    proportionate_deduction=verified(
        "If You opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula: (Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses. Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges.",
        span(
            47,
            "If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses (including surcharge or taxes thereon) as per the following formula: (Eligible Room Rent limit / Room Rent actually incurred) * total Associated Medical Expenses Associated Medical Expenses shall include Room Rent, nursing charges, Medical Practitioners' fees and operation theatre charges.",
            clause="6.2.4(d)",
        ),
    ),
)


# ---- Sub-limits (Tier B: representative; one intentional FLAGGED_UNKNOWN) ----

_sub_limits = [
    SubLimit(
        condition=verified(
            "Air Ambulance (Emergency)",
            span(
                26,
                "Air Ambulance: Only in case of Emergency. Maximum INR 2,50,000 per hospitalization.",
                clause="4.1.2",
            ),
        ),
        limit=verified(
            {"amount_inr": 250000, "unit": "per hospitalization"},
            span(
                26,
                "Air Ambulance: Only in case of Emergency. Maximum INR 2,50,000 per hospitalization.",
                clause="4.1.2",
            ),
        ),
    ),
    SubLimit(
        condition=verified(
            "Annual Health Check-up",
            span(
                27,
                "Available once every Policy Year, from day 1 of the policy. You can choose any test(s) from the list specified below up to your eligibility limit.",
                clause="4.6",
            ),
        ),
        limit=verified(
            {"amount_inr": 5000, "unit": "per policy", "cashless_only": True},
            span(
                15,
                "Annual Health Check-up: ; maximum up to INR 5,000 per policy.",
                clause="CIS row 8.B",
                layer=SourceLayer.CIS,
            ),
        ),
    ),
    SubLimit(
        condition=verified(
            "Shared Accommodation Cash Benefit",
            span(
                33,
                "If you opt for a shared room (for which hospitalization claim is paid), we will pay an additional amount for each day's hospitalization. One day is considered as 24 continuous hours of hospitalization.",
                clause="4.11",
            ),
        ),
        limit=verified(
            {"per_day_inr": 800, "max_inr": 4800},
            span(
                15,
                "Shared accommodation Cash Benefit- INR 800 paid each day if treatment taken in a shared room. Maximum pay out INR 4,800",
                clause="CIS row 8.C",
                layer=SourceLayer.CIS,
            ),
        ),
    ),
    # Intentionally flagged: the wording lists Cataract under specific-disease
    # waiting (24mo) but never states a Rs sub-limit for it on Platinum+.
    SubLimit(
        condition=verified(
            "Cataract",
            span(
                37,
                "ii. Cataract, glaucoma and retinal detachment",
                clause="5.1.2(f)(ii)",
            ),
        ),
        limit=flagged_unknown(
            span(
                37,
                "ii. Cataract, glaucoma and retinal detachment",
                clause="5.1.2(f)(ii)",
            ),
            notes=(
                "Cataract is named in the 24-month specific-disease list but the "
                "Platinum+ wording does not state a separate per-eye cap or "
                "monetary sub-limit. Some other ReAssure 2.0 variants do; "
                "Platinum+ does not."
            ),
        ),
    ),
]


# ---- Co-pay (Tier A: Not Opted on schedule; available options not enumerated
#               on Platinum+ in this PDF beyond the optional-benefit grid) ----

_co_pay = CoPayRule(
    available_options=flagged_unknown(
        span(
            36,
            "Co-Payment: It is the percentage of admissible claim amount You would have to bear, Rest we will pay.",
            clause="4.19",
        ),
        notes=(
            "The wording defines co-pay generically (4.19) but the discrete "
            "percentage options offered on Platinum+ are not enumerated in the "
            "main policy document; they appear in the prospectus."
        ),
    ),
    age_based_copay=flagged_unknown(
        span(
            5,
            "Co-payment | Not Opted",
            clause="Optional Benefit/Feature Details",
            layer=SourceLayer.SCHEDULE,
        ),
        notes=(
            "No age-triggered mandatory co-pay is stated in the Platinum+ "
            "wording carried in this PDF; the schedule confirms co-payment is "
            "Not Opted."
        ),
    ),
)


# ---- Claims mechanics (Tier A on the demo fields) ----

_claims_mechanics = ClaimsMechanics(
    cashless_intimation_hours=verified(
        48,
        span(
            57,
            "Pre-intimate hospitalisation 48 hours in advance (non-emergency cases) via our helpline: 1860-500-8888.",
            clause="Claim Promise with Zero Deductions",
        ),
        notes=(
            "48-hour pre-intimation is the documented requirement for non-"
            "emergency hospitalisation on this Platinum+ Claim Promise."
        ),
    ),
    reimbursement_submission_days=flagged_unknown(
        span(
            46,
            "All documents MUST be submitted at the earliest possible time.",
            clause="6.2.4 IMPORTANT note",
        ),
        notes=(
            "The wording requires reimbursement docs 'at the earliest possible "
            "time' but does not give a hard day-count for the policyholder's "
            "submission window. Insurer's settlement TAT (15 days from receipt) "
            "is stated separately on page 3."
        ),
    ),
    pre_hospitalization_days=verified(
        60,
        span(
            27,
            "We will pay expenses incurred on consultations, medicines, physiotherapy, diagnostic tests for 60 days before the date of admission and 180 days after date of discharge IF these are related to the condition for which hospitalization claim is paid.",
            clause="4.3",
        ),
    ),
    post_hospitalization_days=verified(
        180,
        span(
            27,
            "We will pay expenses incurred on consultations, medicines, physiotherapy, diagnostic tests for 60 days before the date of admission and 180 days after date of discharge IF these are related to the condition for which hospitalization claim is paid.",
            clause="4.3",
        ),
    ),
    moratorium_months=verified(
        60,
        span(
            44,
            "After completion of sixty continuous months of coverage (including portability and migration) in health insurance policy, no policy and claim shall be contestable by the insurer on the grounds of non-disclosure, misrepresentation, except on grounds of established fraud. The period of sixty continuous months is called as moratorium period.",
            clause="6.1.10",
        ),
    ),
)


# ---- Blacklist (a few representative un-recognized hospitals) ----

_blacklist = [
    BlacklistEntry(
        hospital_name=verified(
            "Aakanksha Hospital",
            span(
                8,
                "1 Gujarat Surat Aakanksha Hospital 126, Aaradhnanagar Soc., B/H. Bhulkabhavan School, AanandMahal Rd., Adajan, Surat",
                clause="List of Un-recognized Hospitals, row 1",
                layer=SourceLayer.BLACKLIST,
            ),
        ),
        location=verified(
            "Surat, Gujarat",
            span(
                8,
                "1 Gujarat Surat Aakanksha Hospital",
                clause="List of Un-recognized Hospitals, row 1",
                layer=SourceLayer.BLACKLIST,
            ),
        ),
    ),
    BlacklistEntry(
        hospital_name=verified(
            "Royal Nursing Home",
            span(
                10,
                "54 Maharashtra Mumbai Royal Nursing Home Plot No 7, Sector-1, Airoli,, Navi Mumbai-400708",
                clause="List of Un-recognized Hospitals, row 54",
                layer=SourceLayer.BLACKLIST,
            ),
        ),
        location=verified(
            "Navi Mumbai, Maharashtra",
            span(
                10,
                "54 Maharashtra Mumbai Royal Nursing Home Plot No 7, Sector-1, Airoli,, Navi Mumbai-400708",
                clause="List of Un-recognized Hospitals, row 54",
                layer=SourceLayer.BLACKLIST,
            ),
        ),
    ),
]


_rules = PolicyRules(
    waiting_periods=_waiting_periods,
    standard_exclusions=_standard_exclusions,
    non_standard_exclusions=[],
    room_rent=_room_rent,
    sub_limits=_sub_limits,
    co_pay=_co_pay,
    claims_mechanics=_claims_mechanics,
    blacklist=_blacklist,
    variant_features=None,
)


# ---------------------------------------------------------------------------
# 3. Schedule — from THIS user's Insurance Certificate (pages 4-6)
# ---------------------------------------------------------------------------

_members = [
    InsuredMember(
        relationship=verified(
            "father",
            span(
                6,
                "Mr. Gambhirsingh Bhandari 50 24/04/1975 Male Father 29/03/2025 0 None None",
                clause="Insured Person Details, row 1",
                layer=SourceLayer.SCHEDULE,
            ),
        ),
        age_at_inception=verified(
            50,
            span(
                6,
                "Mr. Gambhirsingh Bhandari 50 24/04/1975 Male Father",
                clause="Insured Person Details, row 1",
                layer=SourceLayer.SCHEDULE,
            ),
        ),
        # PED column on the certificate reads "None" — i.e. no PED declared.
        # This is a VALUE (empty list), not absence of evidence.
        declared_pre_existing_diseases=verified(
            [],
            span(
                6,
                "Pre Existing Condition#: None",
                clause="Insured Person Details, row 1",
                layer=SourceLayer.SCHEDULE,
            ),
        ),
    ),
    InsuredMember(
        relationship=verified(
            "mother",
            span(
                6,
                "Ms. Kastura Bhandari 50 18/09/1975 Female Mother 29/03/2025 0 None None",
                clause="Insured Person Details, row 2",
                layer=SourceLayer.SCHEDULE,
            ),
        ),
        age_at_inception=verified(
            50,
            span(
                6,
                "Ms. Kastura Bhandari 50 18/09/1975 Female Mother",
                clause="Insured Person Details, row 2",
                layer=SourceLayer.SCHEDULE,
            ),
        ),
        declared_pre_existing_diseases=verified(
            [],
            span(
                6,
                "Pre Existing Condition#: None",
                clause="Insured Person Details, row 2",
                layer=SourceLayer.SCHEDULE,
            ),
        ),
    ),
]


_schedule = PolicySchedule(
    plan_variant=verified(
        "Platinum+",
        span(
            4,
            "Variant Opted Platinum+",
            clause="Insurance Certificate",
            layer=SourceLayer.SCHEDULE,
        ),
    ),
    sum_insured=verified(
        1000000,
        span(
            4,
            "Base Sum Insured INR 10,00,000",
            clause="Insurance Certificate",
            layer=SourceLayer.SCHEDULE,
        ),
    ),
    policy_start_date=verified(
        "2026-03-29",
        span(
            4,
            "Policy Commencement Date and Time From 29/03/2026 00:00",
            clause="Insurance Certificate",
            layer=SourceLayer.SCHEDULE,
        ),
    ),
    policy_end_date=verified(
        "2027-03-28",
        span(
            4,
            "Policy Expiry Date and Time To 28/03/2027 23:59",
            clause="Insurance Certificate",
            layer=SourceLayer.SCHEDULE,
        ),
    ),
    members=_members,
    copay_opted=verified(
        "Not Opted",
        span(
            5,
            "Co-payment | Not Opted",
            clause="Optional Benefit/Feature Details",
            layer=SourceLayer.SCHEDULE,
        ),
    ),
    room_modification_opted=verified(
        "Not Opted",
        span(
            5,
            "Room Type Modification | Not Opted",
            clause="Optional Benefit/Feature Details",
            layer=SourceLayer.SCHEDULE,
        ),
    ),
    optional_benefits_opted=verified(
        {
            "hospital_cash": "Not Opted",
            "safeguard": "Not opted",
            "safeguard_plus": "Not Opted",
            "personal_accident": "Not Opted",
            "smart_health_plus_disease_management": "Not Opted",
            "smart_health_plus_acute_care": "Not Opted",
            "ped_waiting_modification": "Not Opted",
            "co_payment": "Not Opted",
            "room_type_modification": "Not Opted",
            "annual_aggregate_deductible": "Not Opted",
            "tiered_network": "Not Opted",
            "prolonged_treatment_assistance": "Not Opted",
        },
        span(
            5,
            "Hospital Cash Not Opted | Safeguard Not opted | Safeguard+ Not Opted | Personal Accident Not Opted | Smart Health+ (Disease Management) Not Opted | Smart Health+ (Acute Care) Not Opted | Pre Existing Disease Waiting Time Modification Not Opted | Co-payment Not Opted | Room Type Modification Not Opted | Annual Aggregate Deductible Not Opted | Tiered Network Not Opted | Prolonged treatment assistance cover Not Opted",
            clause="Optional Benefit/Feature Details",
            layer=SourceLayer.SCHEDULE,
        ),
    ),
)


# ---------------------------------------------------------------------------
# 4. Resolved — wording × schedule joined for THIS user
# ---------------------------------------------------------------------------

# These are multi-span LAYER_JOIN evidences because the *answer for this user*
# is what we get when we read the schedule THROUGH the wording rule.

_resolved = ResolvedFacts(
    effective_ped_waiting_months=verified(
        0,
        # Schedule first (primary/authoritative for this user's input).
        span(
            6,
            "Pre Existing Condition#: None",
            clause="Insured Person Details",
            layer=SourceLayer.SCHEDULE,
        ),
        # Wording supporting the rule we joined against.
        span(
            36,
            "Expenses related to the treatment of a Pre-existing Disease (PED) and its direct complications shall be excluded until the expiry of 36 months of continuous coverage after the date of inception of the first Policy.",
            clause="5.1.1 (Excl01)",
        ),
        method=ResolutionMethod.LAYER_JOIN,
        reasoning=(
            "Schedule declares no PEDs for either insured member. The 36-month "
            "PED waiting (clause 5.1.1) therefore has no condition to attach "
            "to, so the effective PED waiting for this user is 0 months. "
            "NOTE: a separately-listed specific disease may still carry its "
            "own 24-month wait (clause 5.1.2); the 'longer applies' meta-rule "
            "(5.1.2(c)) governs joint cases."
        ),
    ),
    effective_copay_percentage=verified(
        0,
        span(
            5,
            "Co-payment | Not Opted",
            clause="Optional Benefit/Feature Details",
            layer=SourceLayer.SCHEDULE,
        ),
        span(
            36,
            "Co-Payment: It is the percentage of admissible claim amount You would have to bear, Rest we will pay.",
            clause="4.19",
        ),
        method=ResolutionMethod.LAYER_JOIN,
        reasoning=(
            "Schedule shows co-payment Not Opted and no age-based mandatory "
            "co-pay is stated in this Platinum+ wording, so the effective "
            "co-pay for this user is 0%."
        ),
        confidence=0.9,
    ),
    room_rent_proportionate_deduction_applies=verified(
        False,
        span(
            5,
            "Room Type Modification | Not Opted",
            clause="Optional Benefit/Feature Details",
            layer=SourceLayer.SCHEDULE,
        ),
        span(
            47,
            "If you opt for a Hospital room which is higher than the eligible room category as specified in your Policy Schedule, then We will pay only a pro-rated portion of the total Associated Medical Expenses",
            clause="6.2.4(d)",
        ),
        span(
            36,
            "You can choose between a Single Private Room and a Sharing Room. Irrespective of the Room type you choose, ICU admission will always be paid up to Base Sum Insured.",
            clause="4.21 Room Type Modification",
        ),
        method=ResolutionMethod.LAYER_JOIN,
        reasoning=(
            "Room Type Modification is Not Opted on this Platinum+ policy, so "
            "there is no narrowed 'eligible room category' that the user can "
            "exceed, and the proportionate-deduction clause (6.2.4(d)) does "
            "not bite for this user."
        ),
        confidence=0.9,
    ),
)


# ---------------------------------------------------------------------------
# Module-level export
# ---------------------------------------------------------------------------

NIVA_BUPA_POLICY: Policy = Policy(
    identity=_identity,
    rules=_rules,
    schedule=_schedule,
    resolved=_resolved,
    extracted_at=date(2026, 6, 4),
)
