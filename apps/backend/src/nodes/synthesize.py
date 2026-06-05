"""
Structured grounded synthesis (CONTRACT 2).

The LLM is asked to answer the user's question using ONLY a provided list of
evidence records — each carrying a stable `key`, a value, a verification
status, and a span. The output is a tiny Pydantic structure:

    {
      "lede":       "Yes — covered, with a 24-month waiting period.",
      "lede_cites": "ev_specific_wait",
      "claims": [
        {"text": "Knee replacement falls under the 24-month specific-disease waiting.",
         "cites": "ev_specific_wait"},
        ...
      ],
    }

Two prompt modes:
  * default — covers the demo question reliably.
  * strict  — the regenerate path the grounding gate triggers when the LEDE is
              ungrounded; it adds an explicit instruction to cite a VERIFIED
              key on the lede claim AND on every claim.

After the model returns, a **deterministic cite-guard** repairs the most
common malformed-cite failure: a single `cites` (or `lede_cites`) value that
packs MULTIPLE keys (e.g. "ev_specific_wait,ev_room_rent_cap"). We split on
common separators and, if exactly one of the split tokens is a known key —
preferring a verified key for the lede — we collapse the cite to that single
key. Only when the guard can't resolve do we ask the model for a one-shot
repair. The gate is unchanged: it still receives one-key-per-cite and applies
its drop-and-note / regenerate / degrade rules.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from pydantic import BaseModel, Field

from src.llms.gateway import ChatResult, chat_json


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class SynthesisClaim(BaseModel):
    """One discrete statement the model wants to make about the policy."""

    text: str = Field(..., min_length=1)
    cites: str = Field(
        ...,
        min_length=1,
        description="The evidence key (e.g. 'ev_specific_wait') this claim is grounded in. "
        "MUST be exactly ONE of the keys in the evidence list — never comma-joined, "
        "never multi-key.",
    )


class SynthesisAnswer(BaseModel):
    """The structured cited answer. `lede` is one short sentence; `claims` are
    the specific assertions, each carrying ONE citation key."""

    lede: str = Field(..., min_length=1)
    lede_cites: str = Field(
        ...,
        min_length=1,
        description="The evidence key that grounds the lede. The grounding gate "
        "treats this specially: if it's ungrounded, the answer regenerates.",
    )
    claims: list[SynthesisClaim] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Evidence record passed to the LLM
# ---------------------------------------------------------------------------


def collect_evidence_records(tool_results: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten the per-tool keyed-Evidence dicts into ONE list of citation
    candidates the LLM can choose from.

    `tool_results` is `{tool_name: keyed_dict}`. We walk the keyed-dicts and
    emit one record per Evidence-shaped entry (those with a `key` field).
    """
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "key" in node and "status" in node:
                key = str(node["key"])
                if key in seen:
                    return
                seen.add(key)
                span = node.get("span") or {}
                records.append(
                    {
                        "key": key,
                        "value": node.get("value"),
                        "status": node.get("status"),
                        "clause": span.get("clause") if isinstance(span, dict) else None,
                        "page": span.get("page") if isinstance(span, dict) else None,
                        "notes": node.get("notes"),
                    }
                )
                return
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(tool_results)
    return records


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_BASE_SYSTEM = (
    "You are PolicyDesk, a health-insurance-policy Q&A assistant. "
    "You answer ONLY from the evidence list the user provides. "
    "You NEVER assert a policy fact that is not backed by an evidence record. "
    "If the evidence does not support a confident answer, say so honestly "
    "instead of guessing.\n"
    "\n"
    "Output requirements:\n"
    "  - Return a SINGLE JSON object, no prose, no markdown fences.\n"
    "  - Shape: {\"lede\": str, \"lede_cites\": str, \"claims\": [{\"text\": str, \"cites\": str}, ...]}\n"
    "  - `lede` is ONE short sentence — the headline answer.\n"
    "  - `lede_cites` is the evidence `key` that grounds the lede.\n"
    "  - Each item in `claims` is one short supporting sentence with ONE `cites` key.\n"
    "\n"
    "ONE-KEY-PER-CITE rule (this is the rule we enforce most strictly):\n"
    "  - Each `cites` value AND `lede_cites` MUST be EXACTLY ONE evidence key from "
    "the provided list. NEVER combine keys. NEVER comma-join, space-join, slash-join, "
    "or semicolon-join. NEVER invent a key.\n"
    "  - WRONG:  \"cites\": \"ev_specific_wait,ev_room_rent_cap\"  ← rejected\n"
    "  - WRONG:  \"cites\": \"ev_specific_wait ev_longer_rule\"    ← rejected\n"
    "  - RIGHT:  \"cites\": \"ev_specific_wait\"                    ← single key\n"
    "\n"
    "DECOMPOSITION rule (when the question asks about multiple facts):\n"
    "  - The lede states ONE grounded headline fact with ONE cite — pick the "
    "fact you CAN ground (status=verified) as the headline.\n"
    "  - Every other fact — including ones you cannot find in the evidence — "
    "must be a SEPARATE entry in `claims`, each with its OWN single `cites`.\n"
    "  - Do NOT merge two facts into one sentence to make one cite cover both.\n"
    "  - If a fact is FLAGGED_UNKNOWN / not in the evidence, you may still raise "
    "it as a separate claim citing its closest evidence key; the downstream gate "
    "will drop ungrounded claims with an honest note. Better to be a separate "
    "claim that gets dropped than to bundle.\n"
    "\n"
    "EXAMPLE (two-fact question — 'waiting period AND room rent cap?'):\n"
    "  Evidence keys available: ev_specific_wait (verified), ev_room_rent_cap (flagged_unknown).\n"
    "  Correct response shape:\n"
    "    {\"lede\": \"The specific-disease waiting period is 24 months.\",\n"
    "     \"lede_cites\": \"ev_specific_wait\",\n"
    "     \"claims\": [\n"
    "       {\"text\": \"The specific-disease waiting is 24 months from inception.\",\n"
    "        \"cites\": \"ev_specific_wait\"},\n"
    "       {\"text\": \"The room-rent per-day cap is not stated for this variant.\",\n"
    "        \"cites\": \"ev_room_rent_cap\"}\n"
    "     ]}\n"
    "  ← one cite per field, decomposed into separate claims, no merging.\n"
    "\n"
    "Other rules:\n"
    "  - Do NOT invent keys. Do NOT cite a key whose status is not verified if you "
    "have a verified alternative for the SAME fact.\n"
    "  - If you cannot find a verified citation for a fact AND there is no "
    "flagged_unknown evidence key for it either, OMIT that claim rather than "
    "inventing one."
)


_STRICT_ADDENDUM = (
    "\n\nSTRICT MODE (the previous answer's headline could not be grounded):\n"
    "  - Choose your `lede_cites` from a record whose status is 'verified'.\n"
    "  - If no record in the evidence list supports a confident headline, return a "
    "single claim that honestly says you cannot confirm it, citing the most relevant "
    "available verified record.\n"
    "  - The most common previous mistake to AVOID: packing multiple keys into one "
    "`cites` field (e.g. \"ev_a,ev_b\"). Each cite must be exactly ONE key."
)


# Splitter for the cite-guard. Common separators the model may slip in.
_CITE_SPLIT_RE = re.compile(r"[\s,;/|]+")


def _user_prompt(question: str, records: Iterable[dict[str, Any]]) -> str:
    rec_list = list(records)
    return (
        f"Question: {question}\n\n"
        f"Evidence list (each `key` is a citable id):\n"
        f"{json.dumps(rec_list, indent=2, default=str)}\n\n"
        "Reply with ONLY the JSON object."
    )


# ---------------------------------------------------------------------------
# Cite-guard — deterministic single-key repair
# ---------------------------------------------------------------------------


def _resolve_cite(
    raw: str,
    *,
    valid_keys: set[str],
    status_by_key: dict[str, str],
    prefer_verified: bool,
) -> tuple[str, str | None]:
    """Resolve `raw` to a single known key. Returns (resolved_key, event).

    `event` is a one-line description of what the guard did, or None if no
    repair was needed. `resolved_key` is "" when the guard couldn't resolve;
    the caller is expected to either trigger a model repair or hand the
    original string off to the gate (which will then route correctly).
    """
    if raw in valid_keys:
        return raw, None

    tokens = [t for t in _CITE_SPLIT_RE.split(raw) if t]
    known = [t for t in tokens if t in valid_keys]

    if not known:
        return "", None  # nothing to do here

    if len(known) == 1:
        return known[0], (
            f"cite-guard: repaired multi/extra-token cite {raw!r} -> "
            f"{known[0]!r} (status={status_by_key.get(known[0], '?')})"
        )

    # Multiple valid tokens in one cite. Prefer verified when asked.
    if prefer_verified:
        verified = [k for k in known if status_by_key.get(k) == "verified"]
        chosen = verified[0] if verified else known[0]
    else:
        chosen = known[0]
    return chosen, (
        f"cite-guard: split multi-key cite {raw!r} -> {chosen!r} "
        f"(picked from {known}; status={status_by_key.get(chosen, '?')})"
    )


def _apply_cite_guard(
    answer: SynthesisAnswer,
    records: list[dict[str, Any]],
) -> tuple[SynthesisAnswer, list[str], bool]:
    """Repair multi-key cites in `answer` where deterministic.

    Returns (new_answer, events, all_resolved). `all_resolved` is True when
    every cite (lede + claims) is now a single known key.
    """
    valid_keys = {str(r["key"]) for r in records if "key" in r}
    status_by_key = {str(r["key"]): str(r.get("status") or "") for r in records if "key" in r}

    events: list[str] = []
    all_resolved = True

    new_lede_cites, ev = _resolve_cite(
        answer.lede_cites,
        valid_keys=valid_keys,
        status_by_key=status_by_key,
        prefer_verified=True,
    )
    if ev:
        events.append(ev)
    if not new_lede_cites:
        all_resolved = False
        new_lede_cites = answer.lede_cites  # leave as-is; gate will handle

    new_claims: list[SynthesisClaim] = []
    for c in answer.claims:
        resolved, ev = _resolve_cite(
            c.cites,
            valid_keys=valid_keys,
            status_by_key=status_by_key,
            prefer_verified=False,
        )
        if ev:
            events.append(ev)
        if not resolved:
            all_resolved = False
            resolved = c.cites
        new_claims.append(SynthesisClaim(text=c.text, cites=resolved))

    return (
        SynthesisAnswer(
            lede=answer.lede,
            lede_cites=new_lede_cites,
            claims=new_claims,
        ),
        events,
        all_resolved,
    )


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def run_synthesis(
    question: str,
    tool_results: dict[str, Any],
    *,
    strict: bool = False,
    model: str | None = None,
) -> tuple[SynthesisAnswer, ChatResult, list[dict[str, Any]], list[str]]:
    """Generate a structured cited answer.

    Returns the parsed `SynthesisAnswer`, the underlying `ChatResult` (so the
    receipt can surface resolved_model + finish_reason), the evidence records
    that were shown to the model (the grounding gate uses these as its
    citation truth source), and a list of guard events for the resilience log.
    """
    records = collect_evidence_records(tool_results)
    system = _BASE_SYSTEM + (_STRICT_ADDENDUM if strict else "")
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": _user_prompt(question, records)},
    ]
    parsed, result = chat_json(
        messages=messages,
        schema=SynthesisAnswer,
        model=model,
        temperature=0.0,
        max_tokens=2048,
    )
    assert isinstance(parsed, SynthesisAnswer)  # for type checkers

    # Deterministic cite-guard FIRST.
    guarded, guard_events, all_resolved = _apply_cite_guard(parsed, records)

    if all_resolved:
        return guarded, result, records, guard_events

    # One-shot model-side repair, telling the model exactly which cite(s)
    # violated the one-key-per-cite rule.
    valid_keys = sorted({str(r["key"]) for r in records if "key" in r})
    bad_lede = guarded.lede_cites not in valid_keys
    bad_claims = [c.cites for c in guarded.claims if c.cites not in valid_keys]
    feedback = (
        "Your previous JSON broke the ONE-KEY-PER-CITE rule. "
        "Each `cites` value (and `lede_cites`) must be EXACTLY ONE of these keys: "
        f"{valid_keys}. "
        + (f"`lede_cites` was malformed ({guarded.lede_cites!r}). " if bad_lede else "")
        + (f"These claim cites were malformed: {bad_claims}. " if bad_claims else "")
        + "Reply with ONLY a corrected JSON object. Decompose multi-fact answers "
        "into separate claims rather than packing multiple keys into one cite."
    )
    guard_events.append(
        "cite-guard: deterministic split insufficient; requesting one-shot model repair"
    )

    repair_messages = messages + [
        {"role": "assistant", "content": json.dumps(guarded.model_dump())},
        {"role": "user", "content": feedback},
    ]
    repaired, repair_result = chat_json(
        messages=repair_messages,
        schema=SynthesisAnswer,
        model=model,
        temperature=0.0,
        max_tokens=2048,
    )
    assert isinstance(repaired, SynthesisAnswer)

    # Run the guard ONCE more on the repaired answer (cheap insurance).
    final, more_events, _ = _apply_cite_guard(repaired, records)
    guard_events.extend(more_events)
    return final, repair_result, records, guard_events
