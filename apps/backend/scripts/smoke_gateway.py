"""
4.1 smoke test: one real call through the TFY gateway.

Run from apps/backend/:
    uv run python -m scripts.smoke_gateway

Prints the resolved model + a short answer. If this fails, the .env values
(TFY_BASE_URL, TFY_API_KEY, TFY_MODEL) are the first thing to check.
"""

from __future__ import annotations

from src.llms.gateway import chat, default_model


def main() -> int:
    print(f"[smoke] gateway virtual model: {default_model()}")
    result = chat(
        messages=[
            {"role": "system", "content": "You are a terse assistant."},
            {"role": "user", "content": "Reply with exactly: PolicyDesk gateway OK."},
        ],
        max_tokens=64,
    )
    print(f"[smoke] resolved_model : {result.resolved_model}")
    print(f"[smoke] finish_reason  : {result.finish_reason}")
    print(f"[smoke] text           : {result.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
