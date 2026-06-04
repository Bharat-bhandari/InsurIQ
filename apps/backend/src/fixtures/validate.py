"""
Construct + smoke-test the seed Policy fixture.

Run from `apps/backend/`:
    python -m src.fixtures.validate

Exits 0 if every Evidence validator passes and the Policy assembles. Prints a
short human-readable summary so a reader can spot-check what was grounded vs
left FLAGGED_UNKNOWN.
"""

from __future__ import annotations

import sys
from collections import Counter

from src.fixtures.niva_bupa_seed import NIVA_BUPA_POLICY
from src.states.evidence import Evidence, VerificationStatus
from src.states.policy import Policy


def _walk_evidence(obj: object) -> list[Evidence]:
    """Collect every Evidence anywhere in the Policy tree."""
    found: list[Evidence] = []
    seen: set[int] = set()

    def visit(x: object) -> None:
        if id(x) in seen:
            return
        seen.add(id(x))
        if isinstance(x, Evidence):
            found.append(x)
            for s in x.spans:
                visit(s)
            return
        # Pydantic models — read model_fields off the CLASS to avoid the
        # deprecation that fires when read off an instance.
        cls = type(x)
        model_fields = getattr(cls, "model_fields", None)
        if model_fields is not None:
            for name in model_fields:
                visit(getattr(x, name))
            return
        if isinstance(x, list):
            for item in x:
                visit(item)
            return
        if isinstance(x, dict):
            for v in x.values():
                visit(v)
            return

    visit(obj)
    return found


def _summary(p: Policy) -> str:
    facts = _walk_evidence(p)
    status_counts: Counter[str] = Counter(f.status.value for f in facts)

    wp = p.rules.waiting_periods
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("PolicyDesk seed fixture — Niva Bupa ReAssure 2.0")
    lines.append("=" * 72)
    lines.append("")
    lines.append("IDENTITY")
    lines.append(f"  insurer:        {p.identity.insurer_name.value}")
    lines.append(f"  product:        {p.identity.product_name.value}")
    lines.append(f"  uin:            {p.identity.uin.value if p.identity.uin else '—'}")
    lines.append(f"  document_id:    {p.identity.document_id}")
    lines.append(f"  policy_id:      {p.identity.policy_id}")
    lines.append("")
    lines.append("SCHEDULE (this user)")
    lines.append(f"  variant:        {p.schedule.plan_variant.value}")
    lines.append(f"  sum insured:    INR {p.schedule.sum_insured.value:,}")
    lines.append(f"  policy period:  {p.schedule.policy_start_date.value} → {p.schedule.policy_end_date.value}")
    lines.append(f"  members:        {len(p.schedule.members)}")
    for m in p.schedule.members:
        lines.append(
            f"                    - {m.relationship.value}, age {m.age_at_inception.value}, "
            f"declared PEDs: {m.declared_pre_existing_diseases.value}"
        )
    lines.append(f"  co-pay opted:           {p.schedule.copay_opted.value}")
    lines.append(f"  room mod opted:         {p.schedule.room_modification_opted.value}")
    lines.append("")
    lines.append("RULES — waiting periods (wording layer)")
    lines.append(f"  initial waiting (days):       {wp.initial_waiting_days.value}")
    lines.append(f"  PED waiting (months):         {wp.pre_existing_disease_months.value}")
    lines.append(f"  specific disease (months):    {wp.specific_disease_months.value}")
    lines.append(f"  specific disease list size:   {len(wp.specific_diseases_listed.value or [])}")
    lines.append(f"  'longer applies' meta-rule:   {'present' if wp.longer_waiting_rule else 'missing'}")
    lines.append("")
    lines.append("RULES — claims mechanics")
    cm = p.rules.claims_mechanics
    lines.append(f"  cashless intimation (hrs):    {cm.cashless_intimation_hours.value if cm.cashless_intimation_hours else '—'}")
    lines.append(f"  reimbursement window (days):  {cm.reimbursement_submission_days.value if cm.reimbursement_submission_days else '—'}")
    lines.append(f"  pre-hospitalization days:     {cm.pre_hospitalization_days.value if cm.pre_hospitalization_days else '—'}")
    lines.append(f"  post-hospitalization days:    {cm.post_hospitalization_days.value if cm.post_hospitalization_days else '—'}")
    lines.append(f"  moratorium (months):          {cm.moratorium_months.value if cm.moratorium_months else '—'}")
    lines.append("")
    lines.append("RULES — room rent")
    lines.append(f"  room rent limit:              {p.rules.room_rent.room_rent_limit.value if p.rules.room_rent.room_rent_limit else '—'}")
    lines.append(f"  proportionate deduction:      {'present' if p.rules.room_rent.proportionate_deduction else 'missing'}")
    lines.append("")
    lines.append("RULES — counts")
    lines.append(f"  standard exclusions:          {len(p.rules.standard_exclusions)}")
    lines.append(f"  sub-limits:                   {len(p.rules.sub_limits)}")
    lines.append(f"  blacklist entries:            {len(p.rules.blacklist)}")
    lines.append("")
    lines.append("RESOLVED (for this user)")
    lines.append(f"  effective PED waiting (mo):       {p.resolved.effective_ped_waiting_months.value}")
    lines.append(f"  effective co-pay (%):             {p.resolved.effective_copay_percentage.value}")
    lines.append(f"  proportionate deduction applies:  {p.resolved.room_rent_proportionate_deduction_applies.value}")
    lines.append("")
    lines.append("EVIDENCE STATUS COUNTS")
    for status in VerificationStatus:
        n = status_counts.get(status.value, 0)
        if n:
            lines.append(f"  {status.value:<22} {n}")
    lines.append(f"  {'TOTAL':<22} {len(facts)}")
    lines.append("")
    lines.append("FLAGGED_UNKNOWN facts (expected — grounding-honest):")
    for f in facts:
        if f.status == VerificationStatus.FLAGGED_UNKNOWN:
            primary = f.spans[0]
            lines.append(
                f"  · page {primary.page_start} ({primary.source_type.value}, "
                f"clause {primary.clause_ref}): {f.notes or '(no note)'}"
            )
    lines.append("")
    lines.append("OK — Policy constructed; all Evidence validators passed.")
    return "\n".join(lines)


def main() -> int:
    try:
        report = _summary(NIVA_BUPA_POLICY)
    except Exception as e:  # noqa: BLE001
        print(f"FAILED to construct seed Policy: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
