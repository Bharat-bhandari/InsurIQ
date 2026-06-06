"""
TrueFoundry AI Gateway client (OpenAI-compatible).

Every model call in the real graph routes through one virtual model
(`resilient-agent`-style) so the gateway's priority fallback chain is live for
the whole graph without any node knowing about it. Per CONTEXT.md §A4 this is
the entire Tier-1 resilience story; orchestration-layer resilience (Tier-2) is
the graph's own job.

What this module exposes:

  * `gateway_client()` — a cached `openai.OpenAI` pointed at the gateway.
  * `chat(messages, ...)` — plain chat call. Returns the assistant string AND
    the resolved-model metadata the receipt cares about.
  * `chat_json(messages, schema, ...)` — structured output. Asks the gateway
    for a JSON object and validates it against a Pydantic model. Done at the
    SDK level (response_format=json_object) rather than function-calling so
    every routed model — Llama, Nova, DeepSeek — can produce it.

No API keys are hardcoded; everything reads from `.env`. Errors raise (the
graph layer decides whether to retry / degrade).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from openai import BadRequestError, OpenAI
from pydantic import BaseModel, ValidationError

from src.chaos import CHAOS

# Load .env once at import time. The backend's .env sits next to pyproject.toml.
load_dotenv()


# ---------------------------------------------------------------------------
# Guardrail exception
# ---------------------------------------------------------------------------


class GuardrailBlocked(Exception):
    """Raised when the TrueFoundry gateway rejects a request via an input guardrail.

    The gateway returns HTTP 400 with error.type == "guardrail_checks_failed".
    This is an expected, deterministic outcome — do NOT retry; route to an
    honest refusal instead.
    """

    def __init__(self, stage: str, integrations: list[str], message: str) -> None:
        self.stage = stage
        self.integrations = integrations
        self.message = message
        super().__init__(f"Guardrail blocked [{stage}]: {integrations} — {message}")


def _try_parse_guardrail(e: BadRequestError) -> GuardrailBlocked | None:
    """Return a GuardrailBlocked if the 400 is a guardrail block; else None."""
    try:
        body: Any = (
            e.response.json()
            if (hasattr(e, "response") and e.response is not None)
            else (e.body or {})
        )
    except Exception:
        return None

    if not isinstance(body, dict):
        return None

    error_info = body.get("error") or {}
    error_type = error_info.get("type", "") if isinstance(error_info, dict) else ""
    is_block = (
        body.get("error_origin_level") == "guardrails_input"
        or error_type == "guardrail_checks_failed"
    )
    if not is_block:
        return None

    guardrail_checks = body.get("guardrail_checks") or {}
    input_guardrails = guardrail_checks.get("input_guardrails") or []
    integrations = [
        g.get("guardrail_integration", "unknown")
        for g in input_guardrails
        if isinstance(g, dict) and g.get("result") == "failed"
    ]
    return GuardrailBlocked(
        stage="input",
        integrations=integrations,
        message=body.get("message", "Input guardrail check failed."),
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


def _require(env_name: str) -> str:
    value = os.getenv(env_name)
    if not value:
        raise RuntimeError(
            f"{env_name} is not set. Add it to apps/backend/.env "
            f"(see CONTEXT.md §A5 for the gateway tier setup)."
        )
    return value


@lru_cache(maxsize=1)
def gateway_client() -> OpenAI:
    """OpenAI-compatible client pointed at the TrueFoundry gateway.

    The PAT (TFY_API_KEY) and base URL come from .env so this module never
    holds credentials in source. `lru_cache` keeps one client per process.
    """
    return OpenAI(
        api_key=_require("TFY_API_KEY"),
        # TrueFoundry's OpenAI-compatible surface lives under /api/llm/api/inference/openai/v1.
        # If TFY_BASE_URL already includes that path it's used as-is; otherwise
        # we append the canonical suffix so .env can stay short.
        base_url=_resolved_base_url(),
    )


def _resolved_base_url() -> str:
    raw = _require("TFY_BASE_URL").rstrip("/")
    # Already an OpenAI-style /v1 endpoint? Trust it.
    if raw.endswith("/v1") or "/openai/v1" in raw:
        return raw
    return f"{raw}/api/llm/api/inference/openai"


def default_model() -> str:
    """The virtual fallback model. One change in .env switches the whole graph."""
    return _require("TFY_MODEL")


def _active_model() -> str:
    """Return the chaos model group when break_model is armed, else the normal model."""
    if CHAOS.break_model:
        return _require("TFY_MODEL_CHAOS")
    return _require("TFY_MODEL")


# ---------------------------------------------------------------------------
# Plain chat
# ---------------------------------------------------------------------------


@dataclass
class ChatResult:
    """What the receipt cares about from a single call."""

    text: str
    resolved_model: str | None  # the actual model the gateway routed to
    finish_reason: str | None
    raw: Any  # full SDK response, kept around for the receipt's events log


def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = 1024,
) -> ChatResult:
    """One chat completion through the gateway.

    `model` defaults to the gateway virtual model (`TFY_MODEL`). Returns the
    assistant text plus enough metadata for the resilience receipt.
    """
    client = gateway_client()
    try:
        resp = client.chat.completions.create(
            model=model or _active_model(),
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except BadRequestError as e:
        blocked = _try_parse_guardrail(e)
        if blocked is not None:
            raise blocked from e
        raise
    choice = resp.choices[0]
    return ChatResult(
        text=(choice.message.content or "").strip(),
        resolved_model=getattr(resp, "model", None),
        finish_reason=choice.finish_reason,
        raw=resp,
    )


# ---------------------------------------------------------------------------
# Structured output
# ---------------------------------------------------------------------------


# Reasoning models (DeepSeek R1, others routed through the gateway) sometimes
# wrap their JSON in ```json ... ``` even though we asked for response_format
# json_object. The fence varies (```json, ```JSON, plain ```). Strip it before
# json.loads. Falls back to the first {...} block as a last resort.
_FENCED_JSON_RE = re.compile(
    r"```(?:json|JSON)?\s*(\{.*?\})\s*```", re.DOTALL
)
_RAW_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_text(raw: str | None) -> str:
    """Best-effort: return the JSON-object portion of a model reply.

    1. If wrapped in a ```json fenced block → return its contents.
    2. Else if the trimmed string starts with `{` → return as-is.
    3. Else find the first `{...}` span in the reply → return it.
    4. Else return the raw string (json.loads will surface a clean error).
    """
    text = (raw or "").strip()
    if not text:
        return ""
    m = _FENCED_JSON_RE.search(text)
    if m:
        return m.group(1).strip()
    if text.startswith("{"):
        return text
    m = _RAW_JSON_OBJECT_RE.search(text)
    if m:
        return m.group(0).strip()
    return text


def chat_json(
    messages: list[dict[str, str]],
    schema: type[BaseModel],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = 1024,
    max_repair_attempts: int = 1,
) -> tuple[BaseModel, ChatResult]:
    """Chat completion that returns a validated Pydantic instance.

    Uses `response_format={"type": "json_object"}` (universal across routed
    providers) and validates the JSON against `schema`. If validation fails we
    take one bounded repair pass — telling the model what the validator
    complained about — and then give up. The grounding gate is what decides
    whether the resulting structure is *trustworthy*; this only enforces that
    it parses.
    """
    client = gateway_client()
    repair_feedback: str | None = None
    last_raw: Any = None

    for attempt in range(max_repair_attempts + 1):
        attempt_messages = list(messages)
        if repair_feedback:
            attempt_messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous JSON failed validation. "
                        f"Errors: {repair_feedback}\n"
                        "Reply with ONLY a corrected JSON object, no prose."
                    ),
                }
            )

        try:
            resp = client.chat.completions.create(
                model=model or _active_model(),
                messages=attempt_messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
        except BadRequestError as e:
            blocked = _try_parse_guardrail(e)
            if blocked is not None:
                raise blocked from e
            raise
        choice = resp.choices[0]
        text = _extract_json_text(choice.message.content)
        last_raw = resp

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as e:
            repair_feedback = f"not valid JSON: {e}"
            continue

        try:
            parsed = schema.model_validate(payload)
        except ValidationError as e:
            repair_feedback = e.json(include_url=False)
            continue

        return parsed, ChatResult(
            text=text,
            resolved_model=getattr(resp, "model", None),
            finish_reason=choice.finish_reason,
            raw=resp,
        )

    raise RuntimeError(
        f"chat_json: model did not produce schema-valid JSON after "
        f"{max_repair_attempts + 1} attempts. Last feedback: {repair_feedback}. "
        f"Last raw text: {(last_raw.choices[0].message.content if last_raw else '')[:400]}"
    )
