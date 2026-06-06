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
    # When true, /ask interrupts the graph at crash_point (after the tool
    # checkpoint commits, before synthesis) and returns the interrupted state;
    # /resume then finishes the same thread. See the /ask crash branch.
    crash_after_tools: bool = False


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    chaos: ChaosFlags = Field(default_factory=ChaosFlags)


class ResumeRequest(BaseModel):
    thread_id: str = Field(..., min_length=1)


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
# Local-only tool resolution (bypass the TrueFoundry MCP Gateway)
# ---------------------------------------------------------------------------
#
# The tool registry routes a tool through the remote MCP Gateway iff USE_MCP_FOR
# names it (src.tools.mcp_client.use_mcp_for, read at call time). This API surface
# pins tool resolution to LOCAL: every tool node runs its canonical body straight
# out of src.tools.registry with no gateway hop. We do that by clearing
# USE_MCP_FOR from the process environment, so use_mcp_for() always returns False
# and registry._get_waiting_periods_dispatch falls through to the in-process
# _get_waiting_periods_body(). Chaos + bounded retry are untouched — those were
# always client-side (CONTEXT.md §A4); only the transport hop is removed.

_MCP_ROUTING_ENV = "USE_MCP_FOR"


def _enforce_local_tool_resolution() -> None:
    """Neutralize remote MCP routing for this process (idempotent).

    mcp_client.load_dotenv() may have populated USE_MCP_FOR from apps/backend/.env
    at import; we drop it here so no tool is dispatched to the gateway. Called once
    at app construction (env-loading config) and re-asserted at the start of each
    graph run so a stray runtime mutation can't reintroduce a remote hop mid-flight.
    """
    if os.environ.pop(_MCP_ROUTING_ENV, None):
        # Make it explicit in logs that this is a deliberate policy, not a
        # missing-config accident.
        print(
            f"[api] local tool resolution enforced — cleared {_MCP_ROUTING_ENV}; "
            "all tools run from src.tools.registry (MCP Gateway bypassed)",
            flush=True,
        )


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


def _full_response(
    final_state: dict[str, Any],
    *,
    thread_id: str,
    resumed: bool,
    break_model: bool,
    latency_ms: int,
) -> dict[str, Any]:
    """The complete answer+receipt payload the demo renders. Shared by /ask
    (clean path) and /resume so both speak one contract."""
    receipt = _build_receipt(
        final_state,
        thread_id=thread_id,
        resumed=resumed,
        break_model=break_model,
    )
    structured = _structured_answer(final_state)
    return {
        **structured,
        "receipt": receipt,
        "latency_ms": latency_ms,
    }


# Where the API "crashes" the run. Instead of os._exit (which would kill the
# uvicorn worker — see Phase 3 brief), we interrupt the graph BEFORE crash_point.
# call_tools has already run and its checkpoint is committed (durability="sync"),
# so the SQLite checkpoint is genuinely on disk between the two HTTP calls and the
# tools do NOT re-run on /resume. The CLI keeps its literal os._exit crash path
# (run.py) untouched; only the trigger differs.
_CRASH_INTERRUPT_BEFORE = ["crash_point"]


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
    # Pin tool resolution to local BEFORE the graph runs (after mcp_client's
    # load_dotenv at import). Every tool node executes its canonical src.tools
    # body; the remote MCP Gateway proxy layer is bypassed entirely.
    _enforce_local_tool_resolution()

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

        # --- Crash scene (Phase 3) -------------------------------------------
        # Halt the graph at crash_point via an interrupt (NOT os._exit) so the
        # API worker stays alive. plan → call_tools run and the post-tools
        # checkpoint commits; synthesis does NOT run. The browser gets a real,
        # demoable "interrupted" response and /resume picks up the same thread.
        if req.chaos.crash_after_tools:
            with _GRAPH_LOCK:
                # crash is represented by the interrupt, not a chaos toggle — so
                # the other toggles stay off and crash_after_tools is never set
                # on the controller (that would arm the CLI's os._exit path).
                _enforce_local_tool_resolution()
                configure()
                started = time.perf_counter()
                try:
                    for _ in graph.stream(
                        graph_input,
                        config=config,
                        stream_mode="updates",
                        durability="sync",
                        interrupt_before=_CRASH_INTERRUPT_BEFORE,
                    ):
                        pass
                    partial_state = graph.get_state(config).values
                finally:
                    CHAOS.reset()
                latency_ms = int((time.perf_counter() - started) * 1000)

            return {
                "thread_id": thread_id,
                "interrupted": True,
                "partial_receipt": {
                    "tool_status": partial_state.get("tool_status"),
                    "tool_attempts": partial_state.get("tool_attempts") or {},
                    "events": list(partial_state.get("resilience_events") or []),
                    "checkpoint_committed": True,
                },
                "message": "crashed after tool calls — checkpoint saved",
                "latency_ms": latency_ms,
            }

        # --- Normal path (unchanged) -----------------------------------------
        # set → run → reset, serialized, so chaos never leaks across requests.
        with _GRAPH_LOCK:
            _enforce_local_tool_resolution()
            configure(
                fail_tool=req.chaos.fail_tool,
                fail_tool_once=req.chaos.fail_tool_once,
                break_model=req.chaos.break_model,
                # crash_after_tools handled by the branch above (interrupt-based).
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

        return _full_response(
            final_state,
            thread_id=thread_id,
            resumed=False,
            break_model=req.chaos.break_model,
            latency_ms=latency_ms,
        )

    @app.post("/resume")
    def resume(req: ResumeRequest) -> dict[str, Any]:
        """Resume an interrupted run from its committed SQLite checkpoint.

        stream(None, config) continues the SAME thread from crash_point:
        crash_point (pass-through, chaos disarmed) → synthesize → grounding_gate
        → END. The tools do NOT re-run — tool_attempts come straight off the
        checkpoint untouched and the tool proof-print never reappears. Returns
        the SAME shape as /ask with receipt.checkpoint_resumed = true.
        """
        config = {"configurable": {"thread_id": req.thread_id}}
        graph = _graph()

        state = graph.get_state(config)
        if not state.values and not state.next:
            return {
                "error": "no_checkpoint",
                "thread_id": req.thread_id,
                "message": f"no checkpoint found for thread_id={req.thread_id}",
            }

        with _GRAPH_LOCK:
            # Clean controller so resume runs the real synthesis with no chaos.
            _enforce_local_tool_resolution()
            configure()
            started = time.perf_counter()
            try:
                for _ in graph.stream(
                    None,
                    config=config,
                    stream_mode="updates",
                    durability="sync",
                ):
                    pass
                final_state = graph.get_state(config).values
            finally:
                CHAOS.reset()
            latency_ms = int((time.perf_counter() - started) * 1000)

        return _full_response(
            final_state,
            thread_id=req.thread_id,
            resumed=True,
            break_model=False,
            latency_ms=latency_ms,
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8082"))
    uvicorn.run("src.api.app:app", host=host, port=port)
