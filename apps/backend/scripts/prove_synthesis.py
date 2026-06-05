"""
4.3 isolation proof: feed known evidence to the synthesis call and confirm
the model reliably returns the {lede, lede_cites, claims[{text,cites}]}
structure with VALID citation keys.

Run from apps/backend/:
    uv run python -m scripts.prove_synthesis            # 1 iteration
    uv run python -m scripts.prove_synthesis 5          # 5 iterations
"""

from __future__ import annotations

import json
import sys

from src.nodes.synthesize import collect_evidence_records, run_synthesis
from src.tools import ToolCallSpec, call_tool_with_retry

DEMO_QUESTION = (
    "My mother has a cataract and needs surgery. Is it covered, and is there a waiting period?"
)


def gather_demo_tool_results() -> dict[str, dict]:
    """The deterministic plan for the demo question."""
    plan = [
        ToolCallSpec("get_waiting_periods"),
        ToolCallSpec("resolve_for_user", {"condition": "cataract surgery"}),
        ToolCallSpec("get_room_rent_rule"),
    ]
    out: dict[str, dict] = {}
    for spec in plan:
        outcome = call_tool_with_retry(spec)
        assert outcome.ok, f"tool {spec.name} failed in isolation harness"
        out[spec.name] = outcome.value or {}
    return out


def run_once(iteration: int, tool_results: dict[str, dict]) -> bool:
    print(f"\n=== iteration {iteration} ===")
    parsed, result, records, guard_events = run_synthesis(DEMO_QUESTION, tool_results)
    valid_keys = {r["key"] for r in records}
    for ev in guard_events:
        print(f"guard       : {ev}")

    print(f"resolved_model: {result.resolved_model}")
    print(f"lede        : {parsed.lede}")
    print(f"lede_cites  : {parsed.lede_cites} "
          f"(known={parsed.lede_cites in valid_keys})")
    print(f"claims      : {len(parsed.claims)}")
    all_keys_valid = True
    for c in parsed.claims:
        known = c.cites in valid_keys
        all_keys_valid = all_keys_valid and known
        print(f"  - cites={c.cites:<35} known={known}   text={c.text[:80]}")

    lede_ok = parsed.lede_cites in valid_keys
    return lede_ok and all_keys_valid


def main() -> int:
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    tool_results = gather_demo_tool_results()
    records = collect_evidence_records(tool_results)
    print(f"[harness] collected {len(records)} evidence records")
    print(f"[harness] valid keys: {[r['key'] for r in records]}")

    passes = 0
    for i in range(1, iterations + 1):
        if run_once(i, tool_results):
            passes += 1
    print(f"\n[harness] {passes}/{iterations} iterations had all-valid citation keys")
    return 0 if passes == iterations else 1


if __name__ == "__main__":
    raise SystemExit(main())
