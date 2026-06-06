"""
PolicyDesk MCP server — Step 5.2 SPIKE (one tool through the MCP Gateway).

Exposes EXACTLY ONE tool, `get_waiting_periods` (no args), over HTTP/SSE so the
TrueFoundry MCP Gateway (cloud) can reach it over HTTPS. The tool handler is a
THIN wrapper: it calls the EXISTING `_get_waiting_periods_body()` from
src.tools.registry and returns the SAME keyed-Evidence dict (CONTRACT 2). It
does NOT reimplement tool logic, and it does NOT carry chaos or retry — those
stay client-side in the graph (CONTEXT.md §A4: orchestration-tier resilience is
our code, the gateway only makes the transport resilient).

Transport: SSE (Starlette ASGI). The MCP endpoint is GET /sse (+ POST
/messages/); a plain GET /health is added for the reverse proxy. Binds 0.0.0.0,
port from MCP_PORT (default 8081).

Run (shares the backend image / Python env):
    uv run python -m src.mcp_server.server
"""

from __future__ import annotations

import os
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from src.tools.registry import _get_waiting_periods_body

MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8081"))

# FastMCP holds the tool manifest. host/port only matter for its own stdio/sse
# runner; we drive uvicorn ourselves so we can add /health alongside the SSE app.
mcp = FastMCP("policydesk-mcp", host=MCP_HOST, port=MCP_PORT)


@mcp.tool(
    name="get_waiting_periods",
    description=(
        "Return the policy's waiting-period group as keyed-Evidence records: "
        "initial / pre-existing-disease / specific-disease waiting months, the "
        "listed specific diseases, and the 'longer applies' meta-rule. Takes no "
        "arguments. Each value carries {key, value, status, span, notes} so the "
        "caller's grounding gate can verify every cited fact."
    ),
)
def get_waiting_periods() -> dict[str, Any]:
    # THIN wrapper — delegate to the canonical body. Do NOT reimplement, do NOT
    # add chaos/retry (those live in the graph client-side).
    return _get_waiting_periods_body()


async def health(_: Request) -> JSONResponse:
    """Liveness probe for the reverse proxy / compose healthcheck."""
    return JSONResponse(
        {"status": "ok", "service": "policydesk-mcp", "tool": "get_waiting_periods"}
    )


def build_app() -> Starlette:
    """SSE MCP app (/sse + /messages/) plus a plain /health route."""
    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Mount("/", app=mcp.sse_app()),
        ]
    )


def main() -> None:
    print(f"[mcp_server] serving SSE on http://{MCP_HOST}:{MCP_PORT}/sse", flush=True)
    uvicorn.run(build_app(), host=MCP_HOST, port=MCP_PORT)


if __name__ == "__main__":
    main()
