# PolicyDesk — Hackathon Context (Resilient Agents)

> **Purpose of this file:** Living decision spine for the **TrueFoundry Resilient
> Agents hackathon** build. Any collaborator (Bharat, or an AI assistant in a
> fresh session) can reload full hackathon state from this file alone.
> Keep it updated after any meaningful decision.
>
> **Scope note:** This file covers the _hackathon project_ only. The full
> InsurIQ product context (extraction pipeline, three-layer doc model rationale,
> storage architecture, the long-form decision log) is preserved separately in
> Bharat's notes. The schema we reuse here (`src/states/policy.py`,
> `src/states/evidence.py`) is unchanged and authoritative.

_Last updated: 2026-06-07_

---

## A1. The event

- **Hackathon:** Resilient Agents — TrueFoundry, fully online.
- **Dates:** June 1 (kickoff 22:30 IST) → submission June 7 23:59 PT (= June 8 12:00 IST).
- **Registered:** Yes. Open hackathon, just build + submit.
- **Coordination:** Discord (`june-1-2026-resilient-agents-online-hackathon`). Submission link drops there.
- **Required stack (all four must be used meaningfully):**
  - **AWS Bedrock** — foundation models
  - **TrueFoundry AI Gateway** — routing + fallback
  - **TrueFoundry MCP Gateway** — scoped tool access, auth, audit
  - **Guardrails** — input/output safety
- **Judging:** routing/fallback setup · MCP scoped usage · guardrail coverage ·
  **resilience** (retries, state preservation, graceful degradation) · real-world
  usefulness · **demo clarity** (show _what failed and how it recovered_).
- **Prizes:** 1st $3k / 2nd $2k / 3rd $1k (+ TFY & Bedrock credits) · $1k social
  prize (most impressions — Bharat is @himalayan_dev, build-in-public is a free
  second shot).

---

## A2. The pivot — why we are NOT building the InsurIQ product this week

|                       | InsurIQ product                                           | This hackathon                    |
| --------------------- | --------------------------------------------------------- | --------------------------------- |
| **Hard part**         | Structured extraction from 40–80pp adversarial legal PDFs | **Resilience** under failure      |
| **Timeline**          | Weeks/months                                              | 7 days                            |
| **What judges score** | (n/a)                                                     | Survival, not extraction accuracy |

**The extraction pipeline (upload → segment → extract → verify → human-review) is
explicitly OUT of scope.** Building it would eat the whole week and score nothing.

**Strategy:** the `Policy` schema already defines a fully-structured, fully-grounded
policy object. We **seed** one (hand-assembled, Niva Bupa ReAssure 2.0) as a fixture
and build the **resilient Q&A tier that sits on top of an already-extracted policy.**
We start exactly where extraction would have ended.

**Seed provenance (real):** policy `34884769202601`, Platinum+ variant, period
29/03/2026 → 28/03/2027, base sum insured ₹10,00,000, 2 insured members, co-pay
and room-type-modification both Not Opted, no PEDs declared. Built + validated
(see A5 / A13).

**Nothing is throwaway:** a resilient, grounded Q&A layer over a `Policy` object is
_literally_ InsurIQ's Q&A tier. This advances the real product — just seeded, not extracted.

---

## A3. PolicyDesk — the hackathon project

**One-liner:** A resilient health-insurance-policy Q&A agent. Ask a real question
about your policy, get a _cited_ answer — and it keeps answering correctly when the
model goes down, a tool fails, and the process crashes mid-question.

**Thesis sentence (say this in the demo, 3×, different words):**

> _"Grounding is resilience: never state a policy fact you can't trace to a clause —
> even when the model, the tool, and the process all fail. In a domain where a
> confident wrong answer costs someone their claim, grounding IS the resilience story."_

**Demo question (the canonical multi-step, non-local one):**

> "I'm having knee replacement surgery next month. Is it covered, and is there a
> waiting period?" → needs: specific-disease 24mo wait + PED wait + 'longer applies'
> meta-rule + room-rent interaction. Genuinely multi-step → perfect for checkpoint-resume.

---

## A4. Two-tier resilience model (the core framing)

**Tier 1 — Gateway resilience (declarative; TrueFoundry enforces, we configure):**

- Model fallback chain (PROVEN — see A5)
- Input guardrail: PII redaction + prompt-injection block (LIVE — see A5/A7)
- MCP scoped tool access + audit log (registered + traced; run-local for the demo — see A13 2026-06-07)

**Tier 2 — Orchestration resilience (our LangGraph code — THE DIFFERENTIATOR):**

- Tool-failure conditional branch → **honest degradation** using existing verification states
- **Checkpoint resume** after a mid-graph crash (no rework)
- **Grounding gate** node — refuse to assert any fact not backed by a VERIFIED Evidence span

**The gap we exploit (our Aegis-style insight):** the gateway makes _model calls_
resilient but knows nothing about _agent state_. Orchestration-layer resilience
(tool-fail degradation, checkpoint resume, grounding gate) is the ground the prior
winners (Aegis = runtime, Unsinkable = library) left open. Neither built a stateful
LangGraph agent. We do.

---

## A5. Proven so far (gateway + orchestration tiers)

- AWS Bedrock account configured in TrueFoundry; region **us-east-1**; **60 models passing**.
- **Fallback works, traced:** priority-based routing; rate-limited Llama-3-70B →
  fell to DeepSeek R1 (`target_attempt_count: 2`). Save that trace — it's demo evidence.
- **Anthropic models blocked:** expired AWS Marketplace agreement (support case raised).
  NOT blocking — built on Llama/Nova/DeepSeek/Mistral; current primary resolves to
  `mistral.devstral-2-123b`, fails over to `us.deepseek.r1`.
- **Plan:** free **Developer** tier (50k gateway requests/mo). Tokens bill to own AWS
  account (~$10 billing alert; cap retries).

**Break-model button LIVE:** chaos virtual model group `insuriq-production-chaos`
(priority-0 broken → 403 → working fallback); `--break-model` / `chaos.break_model`
routes synthesis there via `TFY_MODEL_CHAOS`; confirmed answering via DeepSeek with
`chaos_mode: break_model`, 403+failover visible in server Request Traces.

**Input guardrails LIVE + firing server-side:** group `insuriq-input-guardrails` —
`insuriq-pii` (mutate; masks policy number + name before the model) and
`insuriq-prompt-injection` (Azure/Bedrock `shieldPrompt`, block → 400). Both seen in
Request Traces. KNOWN LIMITATION: PII guardrail also redacts the trusted evidence
payload → false positives on clause prose (Hernia/Platinum+/etc). Cosmetic only (gate
checks keys+status, not prose); proper fix = scope guardrail to user message only.
Frame as a named limitation.

**Orchestration tier — PROVEN (Step 3 slice + Step 4 real graph + Phase-3 API, see A13):**
tool-fail → honest-degradation branch, crash → checkpoint-resume with no tool re-run
(CLI via `os._exit`; API via `interrupt_before=["crash_point"]`), AND the
deterministic grounding gate (drop-and-note / regenerate / degrade) all working.

**Tier-1 fallback seen firing in the wild (not staged):** synthesis calls have
resolved to `us.deepseek.r1` instead of the primary mid-run with grounding intact.

**Checkpointer learning (hard-won, environment-specific — a fresh session MUST know this):**

- Stack: `langgraph 1.1.3`, `langgraph-checkpoint 4.1.1`, `langgraph-checkpoint-sqlite 3.1.0`, `aiosqlite 0.22.1`.
- Use `langgraph.checkpoint.sqlite.SqliteSaver` over `sqlite3.connect(..., check_same_thread=False)`.
- **`durability="sync"` is REQUIRED** on `graph.stream(...)` (LangGraph 1.x defaults `"async"` → would lose the pre-crash checkpoint).
- Resume: `graph.stream(None, config={"configurable":{"thread_id":...}})`; detect existing checkpoint via `graph.get_state(config).values`/`.next`.
- API crash variant: `interrupt_before=["crash_point"]` (NOT `os._exit`, which would kill the uvicorn worker). CLI keeps its literal `os._exit`. Same graph + checkpointer, different trigger.

---

## A6. MCP scoping — DEPRIORITIZED (both denial demos cut for time)

Original plan was two scoping-denial demos (write-scope + PII read-scope). Both
DEPRIORITIZED — one tool genuinely registered + called through the MCP Gateway
already satisfies "MCP scoped usage." Evidence: earlier Request Traces showing
`MCPGateway: initialize / tools/list (insuriq-vps-engine)` with Bharat's identity.
(Kept here for post-hackathon.)

---

## A7. Tools, guardrails, receipt

**Tools (read-only over the seed `Policy`; each returns keyed-Evidence `{key, value, status, span, notes}`):**

- `get_waiting_periods()` → waiting-period group (initial / PED / specific-disease months, listed diseases, 'longer applies' meta-rule).
- `get_room_rent_rule()` → `room_rent_limit` is honestly `FLAGGED_UNKNOWN`; `proportionate_deduction` VERIFIED (6.2.4(d), p47) — a real degradation hook.
- `resolve_for_user(condition)` → `ResolvedFacts` (multi-span LAYER_JOIN; e.g. effective PED waiting = 0).
- `get_sub_limit(condition)` → `SubLimit` (Cataract sub-limit value is a genuine `FLAGGED_UNKNOWN` — the true gate drop-and-note hook).
- **Return-shape contract:** synthesis reads named keys off each tool result; grounding gate resolves cite keys against this.

**Guardrails:**

- **Input (gateway-native, LIVE):** `insuriq-pii` redaction + `insuriq-prompt-injection` block. Guardrail-block 400 handled client-side → `GuardrailBlocked` → honest refusal naming the guardrail (no retry), receipt records `guardrail_blocked`.
- **Output (our graph node):** grounding gate — every claim must trace to a VERIFIED span; ungrounded → drop-and-note / regenerate / degrade.
- **TWO DISTINCT HONEST BEATS (narrate separately — don't conflate):**
  1. **Tool-failure degradation:** a tool times out → its evidence is absent → agent answers what it can, flags the gap. `tool_status=degraded`, `grounding.action=pass` (gate has nothing to drop).
  2. **Gate drop-and-note:** a tool SUCCEEDS but returns a `FLAGGED_UNKNOWN` field (e.g. cataract sub-limit) → gate genuinely drops the claim + notes it. `grounding.action=drop_and_note`, `grounding.dropped` populated.
- **Honesty in writeup:** be explicit which guardrails are gateway-native (PII, injection) vs our grounding node. Don't manufacture a gate-drop from a tool failure.

**Resilience receipt (the proof artifact):** per-query JSON showing models tried +
which answered · which tool degraded · checkpoint resume yes/no · which guardrails
fired · grounding verdict · latency. `--receipt-json` CLI flag + the screen's receipt
panel both emit it. End the demo on this.

---

## A8. Demo flow (5 scenes, ~3 min)

1. **Framing line** (10s): what it does + resilience is the point + "watch me break all three."
2. **Happy path:** knee-surgery question → PII redacted → scoped tool calls → cited answer → grounding gate passes.
3. **Model down (Tier 1):** break-primary toggle → gateway falls over → same answer, different model (DeepSeek). Point at resolved-model badge.
4. **Tool fails (Tier 2 — differentiator):** selective tool timeout → honest degraded answer (answers what's verified, flags the gap). Side-by-side vs a naive agent.
5. **Crash mid-graph (Tier 2 — showstopper):** Trigger crash → checkpoint-saved interrupted state → Resume → resumes from checkpoint, no rework. Close on the **receipt**.

- (Optional 6th micro-beat: cataract question with no chaos → the TRUE gate drop-and-note on the FLAGGED_UNKNOWN sub-limit.)

---

## A9. Scope — final status

- ✅ Seed `Policy` fixture — DONE
- ✅ Vertical slice — DONE
- ✅ LangGraph Q&A graph + grounding gate — DONE
- ✅ MCP tool registered + traced through gateway; run-local for demo stability — DONE (Step 5.2)
- ✅ Guardrails: input PII/injection (gateway) + output grounding node — DONE
- ✅ Break-model chaos virtual model — DONE
- ✅ All 4 chaos toggles wired + live
- ✅ Per-query resilience receipt (`--receipt-json` + screen panel)
- ✅ Demo screen wired to live backend (Next.js `/demo`) — happy + 3 gateway scenes + crash-resume
- ⏳ Phase-3 crash-resume: backend PROVEN; browser click-through + prod `/resume` deploy PENDING
- ⏳ Curate 5 demo questions (lock clean takes)
- ⏳ Record demo
- Landing page — buffer only
- MCP scoping-denial demos (5.4/5.5) — CUT (deprioritized)

---

## A10. Build order (status)

| #   | Step                                                          | Status                                                 |
| --- | ------------------------------------------------------------- | ------------------------------------------------------ |
| 1   | Update CONTEXT.md                                             | ✅ ongoing                                             |
| 2   | Seed `Policy` fixture                                         | ✅ DONE                                                |
| 3   | Vertical slice (chaos → tool-fail → checkpoint resume)        | ✅ DONE                                                |
| 4   | Real LangGraph Q&A graph + grounding gate                     | ✅ DONE                                                |
| 5   | MCP tool + guardrails + break-model chaos model               | ✅ DONE (scoping denials cut)                          |
| 6   | The ONE demo screen + receipt (Next.js `/demo`, all 5 scenes) | ✅ DONE (pending browser verify + prod /resume deploy) |
| 7   | Curate questions + record demo + (buffer) landing page        | ◀ NEXT — the deliverable                               |

---

## A11. Risks & discipline (read before every session)

- **#1 risk — over-engineering, under-recording.** The build is essentially DONE.
  Remaining score lives in the RECORDING. Do not add features; record what works.
- **Chaos triggers must be reliable.** Execution + demo clarity ≈ 60% of score.
- **Curate demo questions** — the gate decision is deterministic but model prose
  varies; run each scene a few times, pick clean correctly-cited takes.
- **Honest degradation must look visibly different from a plain error** (side-by-side vs naive agent in scene 4).
- **Two honest beats are distinct** (A7) — narrate tool-failure-degrade and gate-drop-and-note separately; never fake a gate-drop from a tool failure.
- **Frame run-local MCP honestly:** "runs through the MCP Gateway (here are the traces); local for recording stability."

---

## A12. Reused assets (unchanged, authoritative)

- `src/states/policy.py`, `src/states/evidence.py` — schema + 6-state `VerificationStatus` enum.
- `src/chaos.py` — chaos controller. 4 toggles: `fail_tool` (bool|str, selective), `fail_tool_once`, `crash_after_tools`, `break_model` — all live.
- `src/llms/gateway.py` — OpenAI-compatible TFY client. `chat()` + `chat_json()` (structured output + repair). Catches guardrail-block 400 → `GuardrailBlocked`. `break_model` → `TFY_MODEL_CHAOS`. Env: `TFY_BASE_URL`, `TFY_API_KEY`, `TFY_MODEL`, `TFY_MODEL_CHAOS`.
- `src/tools/registry.py` — 4 read-only tools (keyed-Evidence); `_wrap()` = chaos hook + proof print; `call_tool_with_retry` (max 2). MCP-vs-local via `USE_MCP_FOR` env (empty = local, current demo setting).
- `src/mcp_server/server.py` — streamable-HTTP MCP server (POST `/mcp` + GET `/health`), thin wrapper over `_get_waiting_periods_body()`. Deployed on VPS; gateway URL `https://gateway.truefoundry.ai/himalayan-dev/mcp/insuriq-vps-engine/server`. NOTE: gateway↔server live link had an SSE/streamable-HTTP transport+registration mismatch (Resync 404); run-local for the demo, gateway usage evidenced by earlier traces.
- `src/nodes/synthesize.py` / `synthesize_node.py` — `SynthesisAnswer {lede, lede_cites, claims[{text,cites}]}`; ONE-KEY-PER-CITE + deterministic cite-guard; catches `GuardrailBlocked` → honest refusal; `synthesize_degraded` for tool-degrade + gate-degrade.
- `src/nodes/call_tools.py` + `crash_point.py` — partial-degrade (keep successful tools' results on partial failure; route on usable results); `crash_point` = CLI `os._exit`, API uses `interrupt_before`.
- `src/nodes/grounding_gate.py` — pure-function `evaluate()` → `GateVerdict{PASS/DROP_AND_NOTE/REGENERATE/DEGRADE}`.
- `src/graphs/qa_graph.py` + `run.py` — wired graph; SqliteSaver `.qa_checkpoints.sqlite` (gitignored) + `durability="sync"`.
- `src/api/app.py` — FastAPI. `POST /ask` (question + chaos), `POST /resume` ({thread_id}), `GET /health`. Shared `_full_response()` / `_build_receipt`. Re-exported via `main.py`. CORS for the frontend.
- `apps/frontend/src/app/demo/` — Next.js demo (PolicyDesk.tsx, api.ts, policydesk.css, constants.ts, components/). Receipt-driven rendering of all 5 scenes. Env `NEXT_PUBLIC_API_BASE_URL`. Reference UI (now wired-port source) lives at `insuriq-resilient/` (HTML/JS) — recording fallback surface.
- `scripts/` — `smoke_gateway.py`, `prove_synthesis.py`, `prove_grounding_gate.py`.
- Deployed: frontend `https://insuriq.himalayandev.tech/demo`, API `https://api.insuriq.himalayandev.tech`. ~1-min Docker deploy via VPS.

---

## A13. Decision log (hackathon, append-only, dated)

- **2026-06-01** — Registered for TrueFoundry Resilient Agents hackathon (June 1–7). Open, no selection round.
- **2026-06-02** — Gateway tier proven: Bedrock via TFY (us-east-1, 60 models); priority-based fallback Llama-3-70B → DeepSeek R1 traced on rate-limit. Anthropic blocked on expired AWS Marketplace agreement; non-blocking.
- **2026-06-03** — **PIVOT:** project = **PolicyDesk**, resilient Q&A tier over a SEEDED `Policy`. Extraction OUT of scope. Two-tier resilience framing. Risk-first build order.
- **2026-06-04** — **Seed fixture DONE.** `NIVA_BUPA_POLICY` hand-assembled from the real Niva Bupa ReAssure 2.0 PDF. Verbatim spans for demo-critical facts; honest `FLAGGED_UNKNOWN`s (room-rent cap, Cataract sub-limit). CAVEAT: scrub real member names from schedule spans before public push (§6 PII).
- **2026-06-04** — **Step 3 (slice) DONE.** Both Tier-2 unknowns proven on a 5-node CLI graph. `durability="sync"` learning. Resume = `stream(None, same thread_id)`.
- **2026-06-04** — **Step 4 (real graph) DONE.** Gateway synthesis (Tier-1 live), deterministic grounding gate, drop-and-note policy. cite-guard fix (multi-key cites → single verified key). Combined question DROP_AND_NOTE confirmed across DeepSeek + Llama. Fully closed.
- **2026-06-06** — **Step 5 gateway pieces DONE.** Break-model chaos virtual model; both input guardrails live + traced; Issue-1 fix (guardrail-block 400 → honest refusal, no crash). PII evidence-payload false-positive logged as a known limitation.
- **2026-06-06** — **Step 5.2 MCP DONE (then run-local).** `get_waiting_periods` exposed via MCP server `insuriq-vps-engine` on the VPS, registered in TFY MCP Gateway; Request Traces confirmed the agent called it THROUGH the gateway (initialize/tools/list with identity) — satisfies "MCP scoped usage." Scoping-denial demos (5.4/5.5) and promoting the other 3 tools CUT for time.
- **2026-06-07** — **MCP switched to run-local** (`USE_MCP_FOR` empty) for demo stability. The streamable-HTTP transport fix (server now POST `/mcp`, was SSE `/sse`) is correct in code, but the gateway registration/proxy still pointed at SSE → Resync 404. DECISION: run tools locally for the recording; evidence MCP-through-gateway from the earlier traces; narrate honestly. (Live gateway link = post-hackathon.)
- **2026-06-07** — **Demo screen DONE (Steps 6).** `/ask` + live happy path, then 3 gateway scenes (break-model, selective fail-tool, injection-block), then **Phase 3 crash-resume** via two endpoints: `/ask` with `crash_after_tools` interrupts before `crash_point` (checkpoint commits, worker survives) + `/resume` resumes from the committed checkpoint. PROVEN at backend: exactly 2 tool proof-prints across both calls (tools NOT re-run), `tool_attempts` identical, `checkpoint_resumed: true`. Ported into Next.js `/demo`. **PENDING:** browser click-through against local, and deploy `/resume` to production. No regression on other scenes. **NEXT: curate questions + record.**
