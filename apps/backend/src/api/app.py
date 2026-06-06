"""
FastAPI surface for PolicyDesk (Phase 1 — one live happy-path round-trip).

POST /ask runs the real Q&A graph for one question and returns the same data
the demo screen needs to render a grounded answer + the resilience receipt.

Per-request chaos isolation (CONTEXT.md §A11 — chaos must be reliable):
the chaos controller is a process-wide singleton, so we serialize /ask behind
a lock and follow a strict set → run → reset cycle. A plain /ask after a chaos
/ask therefore always starts from a clean controller — state never leaks.

The `receipt` field is byte-for-byte the same shape as `python -m src.graphs.run
--receipt-json` (built by the shared `_build_receipt`), so the CLI and the API
stay one source of truth.
"""

from __future__ import annotations

import os
import secrets
import threading
import time
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.chaos import CHAOS, configure
from src.graphs.qa_graph import build_graph, open_checkpointer
from src.graphs.run import _build_receipt


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChaosFlags(BaseModel):
    # bool True fails every tool; a tool-name string fails only that tool.
    fail_tool: bool | str = False
    break_model: bool = False
    fail_tool_once: bool = False
    # crash_after_tools is handled in Phase 3; accepted but ignored here so the
    # screen can send a uniform payload.
    crash_after_tools: bool = False


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    chaos: ChaosFlags = Field(default_factory=ChaosFlags)


# ---------------------------------------------------------------------------
# Graph singleton (one compiled graph + checkpointer for the process; each
# request gets a fresh thread_id so nothing collides).
# ---------------------------------------------------------------------------

_GRAPH = None
_GRAPH_LOCK = threading.Lock()  # serializes chaos set→run→reset


def _graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph(open_checkpointer())
    return _GRAPH


# ---------------------------------------------------------------------------
# Evidence extraction — full per-key spans (incl. verbatim text) straight off
# tool_results, so the citation panels can show the real clause wording. This
# reads state the graph already produced; it does not touch synthesis logic.
# ---------------------------------------------------------------------------


def _evidence_index(tool_results: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "key" in node and "status" in node:
                key = str(node["key"])
                if key not in index:
                    span = node.get("span") or {}
                    span = span if isinstance(span, dict) else {}
                    index[key] = {
                        "cite_key": key,
                        "value": node.get("value"),
                        "cite_status": node.get("status"),
                        "clause": span.get("clause"),
                        "page": span.get("page"),
                        "quote": span.get("text"),
                        "notes": node.get("notes"),
                    }
                return
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(tool_results or {})
    return index


_GROUNDED = {"verified", "user_corrected"}


def _structured_answer(final_state: dict[str, Any]) -> dict[str, Any]:
    """Decompose the finalized answer into a lede + per-claim citation chips.

    Mirrors what `grounding_gate_node._format_finalized_answer` renders: only
    grounded claims survive into the bullet list, each carrying its (clause,
    page). We additionally surface the verbatim span text for the panel.
    """
    synthesis = final_state.get("synthesis") or {}
    index = _evidence_index(final_state.get("tool_results"))

    def cite(cite_key: str | None) -> dict[str, Any]:
        if not cite_key:
            return {}
        return index.get(cite_key, {"cite_key": cite_key})

    lede = synthesis.get("lede")
    lede_cite = cite(synthesis.get("lede_cites")) or None

    claims: list[dict[str, Any]] = []
    for c in synthesis.get("claims") or []:
        info = cite(c.get("cites"))
        # Keep only grounded claims — the same set the gate kept and rendered.
        if info.get("cite_status") in _GROUNDED:
            claims.append({"text": c.get("text"), **info})

    return {
        "answer_text": final_state.get("answer") or "",
        "lede": lede,
        "lede_cite": lede_cite,
        "claims": claims,
    }


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


def _cors_origins() -> list[str]:
    """Allowed browser origins, from CORS_ORIGINS (comma-separated).

    MUST be the single source of CORS headers. Earlier the app emitted
    `Access-Control-Allow-Origin: *` while nginx ALSO added the specific origin,
    so a browser saw two ACAO headers and rejected the response (`TypeError:
    Failed to fetch`) — the demo-killer. We now reflect the exact configured
    origins (never "*"), so the header is valid with credentials and there is
    one authoritative source. The reverse proxy must NOT add its own CORS headers.
    """
    raw = os.getenv("CORS_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    # Local-dev fallback so running without the env still works from the demo.
    return origins or ["http://localhost:3002", "http://127.0.0.1:3002"]


def create_app() -> FastAPI:
    app = FastAPI(title="PolicyDesk backend")

    # Single CORS authority (see _cors_origins). Specific origins + credentials,
    # never a wildcard — `ACAO: *` with `allow-credentials: true` is itself an
    # illegal combination that browsers reject.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "policydesk-backend"}

    @app.post("/ask")
    def ask(req: AskRequest) -> dict[str, Any]:
        thread_id = f"qa-{secrets.token_hex(4)}"
        config = {"configurable": {"thread_id": thread_id}}
        graph = _graph()

        graph_input = {
            "question": req.question,
            "resilience_events": [f"run: thread_id={thread_id} fresh start (api)"],
            "regenerate_count": 0,
        }

        # set → run → reset, serialized, so chaos never leaks across requests.
        with _GRAPH_LOCK:
            configure(
                fail_tool=req.chaos.fail_tool,
                fail_tool_once=req.chaos.fail_tool_once,
                break_model=req.chaos.break_model,
                # crash_after_tools intentionally NOT set in Phase 1.
            )
            started = time.perf_counter()
            try:
                for _ in graph.stream(
                    graph_input,
                    config=config,
                    stream_mode="updates",
                    durability="sync",
                ):
                    pass
                final_state = graph.get_state(config).values
            finally:
                CHAOS.reset()
            latency_ms = int((time.perf_counter() - started) * 1000)

        receipt = _build_receipt(
            final_state,
            thread_id=thread_id,
            resumed=False,
            break_model=req.chaos.break_model,
        )

        structured = _structured_answer(final_state)
        return {
            **structured,
            "receipt": receipt,
            "latency_ms": latency_ms,
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8082"))
    uvicorn.run("src.api.app:app", host=host, port=port)
