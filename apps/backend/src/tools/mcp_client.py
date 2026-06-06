"""
MCP client path for the graph (Step 5.2 SPIKE).

Routes selected tools THROUGH the TrueFoundry MCP Gateway instead of their local
function. Only `get_waiting_periods` moves for the spike; the other three tools
stay local (5.3 promotes the rest).

CRITICAL (CONTEXT.md §A4): chaos + bounded retry STAY client-side. This module
is only the transport. It is invoked from INSIDE `registry._wrap`, so:
  * `CHAOS.maybe_fail_tool()` has already fired (so `--fail-tool` simulates the
    now-remote call failing, before any network I/O),
  * the single `[tool] ...` proof-of-execution print has already happened
    (checkpoint-resume proof intact),
  * `call_tool_with_retry` (max 2) still owns retry + the degrade routing.
To keep that envelope working, ANY remote failure here is normalized to
`TimeoutError` — the one exception `call_tool_with_retry` catches — so a gateway
hiccup degrades identically to a local tool timeout.

Switchable via env (default OFF — full local regression):
  USE_MCP_FOR    comma-separated tool names to route remotely
                 (e.g. "get_waiting_periods")
  TFY_MCP_URL    the gateway MCP endpoint. Streamable-HTTP (…/mcp) is used
                 unless the URL path contains "/sse", in which case SSE is used.
  TFY_MCP_TOKEN  bearer token the gateway authenticates + scopes the call with.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from dotenv import load_dotenv

# Backend .env sits next to pyproject.toml; load once at import.
load_dotenv()


def use_mcp_for(tool_name: str) -> bool:
    """True when USE_MCP_FOR names this tool. Unset/empty → always False."""
    raw = os.getenv("USE_MCP_FOR", "")
    names = {n.strip() for n in raw.split(",") if n.strip()}
    return tool_name in names


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set, but USE_MCP_FOR routes a tool through the MCP "
            f"Gateway. Set it in apps/backend/.env (TFY_MCP_URL / TFY_MCP_TOKEN), "
            f"or remove the tool from USE_MCP_FOR to fall back to the local "
            f"function (CONTEXT.md §A6 / Step 5.2)."
        )
    return value


def _parse_result(result: Any) -> dict[str, Any]:
    """Pull the keyed-Evidence dict back out of a CallToolResult.

    FastMCP serializes a dict return as a TextContent block of JSON; newer
    clients also surface it as `structuredContent`. Prefer the JSON text (it is
    exactly the tool's return), fall back to structuredContent.
    """
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            return json.loads(text)

    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured

    raise ValueError(f"MCP tool returned no parseable content: {result!r}")


async def _call_remote(tool_name: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    url = _require("TFY_MCP_URL")
    token = _require("TFY_MCP_TOKEN")
    headers = {"Authorization": f"Bearer {token}"}

    from mcp import ClientSession

    if "/sse" in url:
        from mcp.client.sse import sse_client

        async with sse_client(url, headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, kwargs or {})
    else:
        from mcp.client.streamable_http import streamablehttp_client

        async with streamablehttp_client(url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, kwargs or {})

    if getattr(result, "isError", False):
        raise TimeoutError(f"[mcp] gateway reported tool error for {tool_name}: {result!r}")

    return _parse_result(result)


def fetch_via_mcp(tool_name: str, kwargs: dict[str, Any] | None = None) -> dict[str, Any]:
    """Sync entry point for the registry.

    Returns the same keyed-Evidence dict the local body would. Any remote/
    transport failure is re-raised as TimeoutError so the EXISTING
    `call_tool_with_retry` envelope retries (max 2) then degrades — identical
    behavior to a local tool timeout.
    """
    try:
        return asyncio.run(_call_remote(tool_name, kwargs or {}))
    except TimeoutError:
        raise
    except Exception as e:  # noqa: BLE001 — normalize to the retry envelope's currency
        raise TimeoutError(f"[mcp] remote call {tool_name} failed: {e}") from e
