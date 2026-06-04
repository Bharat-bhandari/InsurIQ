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

_Last updated: 2026-06-04_

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
- Input guardrail: PII redaction + prompt-injection block
- MCP scoped tool access + audit log

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

## A5. Proven so far (gateway tier)

- AWS Bedrock account configured in TrueFoundry; region **us-east-1**; **60 models passing**.
- **Fallback works, traced:** priority-based routing; rate-limited Llama-3-70B →
  fell to DeepSeek R1 (`target_attempt_count: 2`, `applied_ratelimit_rule_ids`). Save that trace — it's demo evidence.
- **Anthropic models blocked:** expired/zero-duration AWS Marketplace agreement
  (start = end timestamp). AWS support case raised. NOT blocking — we build on Llama/Nova/DeepSeek and slot Claude in as primary (one-line config change) if/when it clears.
- **Plan:** free **Developer** tier is enough — 50k gateway requests/mo (each LLM
  call AND each MCP tool call counts as 1). Tokens bill to **own AWS account**
  (set a ~$10 billing alert; cap retries so failure-testing loops don't burn budget). Admin (Sai) confirmed: exceed the 50k and they'll extend.

**Working fallback chain (until Claude clears):**
`us.meta.llama3-3-70b-instruct` (primary) → `us.amazon.nova-pro` → `us.amazon.nova-micro` → `openai.gpt-oss-120b`. 3+ providers = real cross-provider story.

**Orchestration tier — also PROVEN now (Step 3 slice, see A13):** tool-fail →
honest-degradation branch, and real-kill (`os._exit`) crash → checkpoint-resume
with no tool re-run.

**Checkpointer learning (hard-won, environment-specific — a fresh session MUST know this):**
- Stack: `langgraph 1.1.3`, `langgraph-checkpoint 4.1.1`, `langgraph-checkpoint-sqlite 3.1.0`, `aiosqlite 0.22.1`.
- Use `langgraph.checkpoint.sqlite.SqliteSaver` over a `sqlite3.connect(..., check_same_thread=False)` connection (so the saver outlives a `with` block).
- **`durability="sync"` is REQUIRED** on `graph.stream(...)`. LangGraph 1.x defaults to `"async"`, which would NOT have committed the post-`call_tool` checkpoint to disk before `os._exit(1)` fires → the tool would wrongly re-run on resume. This single flag is what makes the crash/resume proof real.
- Resume convention (LangGraph 1.x): `graph.stream(None, config={"configurable": {"thread_id": ...}})` — pass `None` as input with the same `thread_id`. Detect an existing checkpoint via `graph.get_state(config).values` / `.next`.

---

## A6. MCP scoping — BOTH demos (they complement each other)

1. **Write-scope denial.** Register a genuinely dangerous tool (e.g. `delete_policy` /
   `update_user_record`) in the MCP Gateway that the Q&A agent's token **cannot** call.
   Demo: a prompt-injection tries to make the agent call it → gateway **denies** →
   audit log shows the blocked attempt. Proves scoping is real, not theater.
2. **PII read-scope denial.** Identity fields (names/DOB/CKYC) live in a separate
   store (per InsurIQ §6 PII rule). Register `get_member_identity` that the Q&A agent
   is **not** scoped for. Demo: agent answers the coverage question fully but
   physically cannot surface identity. Turns the existing PII-separation decision
   into a live safety demo.

---

## A7. Tools, guardrails, receipt

**Tools (read-only over the seed `Policy`; each returns Evidence WITH spans intact):**

- `get_waiting_periods()` → the whole `WaitingPeriods` group (initial / PED / specific-disease months, the listed diseases, and the 'longer applies' meta-rule). Slice proved this one.
- `get_room_rent_rule()` → `RoomRentRule` (NOTE: in the seed, `room_rent_limit` is honestly `FLAGGED_UNKNOWN` — Platinum+ states no per-day cap; `proportionate_deduction` is VERIFIED at clause 6.2.4(d), p47). This is a real gap the degradation scene can point at.
- `resolve_for_user(condition)` → relevant `ResolvedFacts` (multi-span LAYER_JOIN, e.g. effective PED waiting = 0 because no PED declared).
- `get_sub_limit(condition)` → matching `SubLimit` (NOTE: Cataract sub-limit is a genuine `FLAGGED_UNKNOWN` in the seed — another real degradation hook).
- Tools return value + spans (page + clause + verification status) — grounding flows through the tool layer.
- **Return-shape contract:** the slice's `synthesize` reads named keys off the tool result (`specific_disease_months`, `pre_existing_disease_months`, `longer_waiting_rule`, each `{value, span:{clause,page}}`). Step 4's real tools + synthesis must keep this contract in agreement.

**Guardrails:**

- **Input (gateway-native):** PII redaction; prompt-injection block.
- **Output (our graph node — domain-specific):** grounding gate. Every policy claim
  must trace to a VERIFIED Evidence span; ungrounded → block / regenerate / honest
  "can't confirm." This is the runtime enforcement of the project's founding rule
  (the placeholder node that hallucinated policy facts is exactly what this catches).
- **Honesty in writeup:** be explicit which guardrails are gateway-native (PII,
  injection) vs our own grounding logic (graph verification node). Don't overclaim.

**Resilience receipt (the proof artifact — Aegis Receipt lesson):** per-query JSON /
panel showing: models tried + which answered · which tool degraded · checkpoint
resume yes/no · which guardrails fired · total latency. End the demo on this.

---

## A8. Demo flow (5 scenes, ~3 min)

1. **Framing line** (10s): what it does + resilience is the point + "watch me break all three."
2. **Happy path:** ask the knee-surgery question → PII redacted badge → plan → scoped
   tool calls → cited answer → output grounding gate passes. Establish "working."
3. **Model down (Tier 1):** chaos toggle breaks primary → gateway falls over → same
   answer, different model. Point at resolved-model badge.
4. **Tool fails (Tier 2 — differentiator):** toggle tool timeout → conditional branch →
   **honest degraded answer** (answers what's verified, flags what it couldn't confirm).
   **Show side-by-side vs a naive agent** (which hallucinates or 500s) — the contrast
   is what makes the sophistication legible.
5. **Crash mid-graph (Tier 2 — showstopper):** kill process after tools, before
   synthesis → restart → **resume from checkpoint**, no rework. Then close on the **receipt**.

---

## A9. Scope

**IN (build this week):**

- ✅ Seed `Policy` fixture (one Niva Bupa object, hand-assembled once) — DONE
- ✅ Vertical slice (chaos toggle → tool-fail branch → checkpoint-resume) — DONE
- LangGraph Q&A graph: plan → tool → synthesize → grounding gate; with checkpointer + one conditional branch (Step 4 — promote the slice)
- MCP tools (read-only) + BOTH scoping demos
- Guardrails: input (PII/injection, gateway) + output (grounding node, ours)
- **Chaos controls** — toggle each failure on demand (pre-broken virtual model trick) — slice has all 4 toggles wired (`break_model` stubbed)
- Per-query resilience receipt — slice emits a basic events log already
- **ONE demo screen** (Q&A + citations + chaos toggles + receipt) — design comp done, not yet wired

**OUT (explicitly NOT this week — remains real InsurIQ future, untouched):**

- Upload flow · document-type segmentation · extraction LLM jobs · OCR ·
  human-review correction UI · multi-PDF · real auth · full product design system ·
  Postgres extraction store (stub/minimize) · curated policy DB

---

## A10. Build order (risk-first)

| #   | Step                                                                                            | Why here                                                       |
| --- | ----------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| 1   | Update CONTEXT.md                                                                               | ✅ DONE (this file)                                            |
| 2   | Seed `Policy` fixture                                                                           | ✅ DONE — built + validated (`src/fixtures/`)                  |
| 3   | **Vertical slice: chaos toggle → tool-fail branch → checkpoint resume** (CLI only)              | ✅ DONE — both unknowns proven (`src/slice/`)                  |
| 4   | Real LangGraph Q&A graph + grounding gate                                                       | ◀ NEXT — build on proven foundations                          |
| 5   | MCP tools (both scoping demos) + guardrails via gateway                                         | Required-tool integrations                                     |
| 6   | The ONE demo screen + receipt display                                                           | Design once, correctly, knowing exactly what to show           |
| 7   | Polish chaos controls + record demo                                                             | The ~60%-of-score part gets dedicated time                     |

---

## A11. Risks & discipline (read before every session)

- **#1 risk — over-engineering the domain, under-engineering the demo.** The schema
  is DONE. Touch it only to seed the fixture. Every hour gold-plating Pydantic is an
  hour not making the demo fire. Guard against own strength.
- **Chaos triggers must be reliable** — build early. A flaky demo of a brilliant idea
  loses to a clean demo of a simple one. Execution + demo clarity ≈ 60% of score.
- **"Single seeded policy"** — frame confidently as focused scope ("the resilient Q&A
  tier on top of an extracted policy"), never apologetically.
- **Honest degradation must look visibly different from a plain error** — hence the
  side-by-side vs a naive agent in scene 4.
- **Cap retries.** Infinite retry is itself a resilience failure AND burns gateway-request budget.
- **Judge self-rating:** idea ~7.5–8/10; final lands 6–9 _entirely_ on execution + demo reliability.

---

## A12. Reused assets (unchanged, authoritative)

- `src/states/policy.py` — the `Policy` schema (rules / schedule / resolved regions).
- `src/states/evidence.py` — the `Evidence` wrapper: multi-span, resolution trail,
  6-state `VerificationStatus` enum (the vocabulary that makes honest degradation principled).
- `src/{graphs,llms,nodes,states}` — proven backend layout. Keep it.
- LLM layer (`src/llms/`) gets repointed at the TFY gateway virtual model `resilient-agent`
  (was Groq direct) — one change, every node inherits fallback.
- `src/fixtures/` — `_builders.py` (validator-safe Evidence constructors: `span`, `verified`, `flagged_unknown`), `niva_bupa_seed.py` (exports `NIVA_BUPA_POLICY`), `validate.py` (constructs + prints status-count summary; run `python -m src.fixtures.validate`).
- `src/slice/` — Step-3 spike (`state`, `chaos`, `tools`, `nodes`, `graph`, `run`). Hardens into the real graph in Step 4; the chaos module + retry wrapper + checkpointer setup carry forward, the stubbed synthesis gets replaced by a real gateway call + grounding gate.
- Checkpointer deps added: `langgraph-checkpoint-sqlite` (+ `aiosqlite`). Sqlite file `apps/backend/.slice_checkpoints.sqlite*` is gitignored.

---

## A13. Decision log (hackathon, append-only, dated)

- **2026-06-01** — Registered for TrueFoundry Resilient Agents hackathon (June 1–7). Open, no selection round.
- **2026-06-02** — Gateway tier proven: Bedrock via TFY (us-east-1, 60 models passing); priority-based fallback Llama-3-70B → DeepSeek R1 traced on rate-limit. Anthropic models blocked on expired AWS Marketplace agreement (support case raised); non-blocking, build on Llama/Nova/DeepSeek.
- **2026-06-03** — **PIVOT:** hackathon project = **PolicyDesk**, a resilient Q&A tier over a **SEEDED** `Policy` object. Extraction pipeline explicitly OUT of scope. Adopted **two-tier resilience** framing (gateway = config; orchestration = our code). Orchestration tier (tool-fail honest degradation, checkpoint resume, grounding gate) is the differentiator vs prior winners (Aegis/Unsinkable left stateful agents open). Both MCP scoping demos (write-scope denial + PII read-scope denial). Build order is risk-first: seed → vertical-slice de-risk → graph → MCP/guardrails → one demo screen → polish+record.
- **2026-06-04** — **Seed fixture DONE.** `NIVA_BUPA_POLICY` hand-assembled in `src/fixtures/` from the real Niva Bupa ReAssure 2.0 PDF (policy 34884769202601). Tier-A verbatim spans for the demo-critical facts (24mo specific-disease incl. knee/joint replacement, 36mo PED, 'longer applies' meta-rule 5.1.2(c), proportionate-deduction 6.2.4(d), schedule values, LAYER_JOIN resolved facts). Honest `FLAGGED_UNKNOWN`s where the policy is silent (room-rent cap, Cataract sub-limit) — these double as real hooks for the degradation scene. `validate.py` constructs cleanly; all Evidence validators pass. CAVEAT: real member names sit in schedule `span.text` — scrub to neutral placeholders before recording/public push (per §6 PII).
- **2026-06-04** — **Step 3 (vertical slice) DONE.** Both Tier-2 unknowns proven on a 5-node CLI graph (`src/slice/`): (1) tool-fail → bounded retry (max 2) → honest-degradation branch; (2) real-kill (`os._exit(1)`) crash → SQLite checkpoint → resume with the tool NOT re-run (proven by the single `[call_tool]` print across both commands). Key environment learning: `durability="sync"` required (LangGraph 1.x defaults async → would lose the pre-crash checkpoint). Resume = `stream(None, same thread_id)`. Bonus `--fail-tool-once` transient mode also works (recovers on attempt 2). Chaos module has all 4 toggles; `break_model` stubbed for Step 4. Verified against the actual files — resume is a true resume, not a fresh run.
