"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import "./policydesk.css";

import TopBar from "./components/TopBar";
import ThreadView from "./components/ThreadView";
import ChaosRail from "./components/ChaosRail";
import type { ChaosState } from "./components/ChaosRail";
import type { Message, ProseParagraph, AgentMessage } from "./components/ThreadView";
import type { LogLine, ReceiptData, ClauseInfo } from "./constants";
import { QUESTIONS, SUGGESTIONS, CLAUSES, ANSWERS, RECEIPTS, LOG_SCRIPTS } from "./constants";
import { askBackend, crashBackend, resumeBackend, chaosForMode, API_BASE } from "./api";
import type { AskResponse, Claim } from "./api";

const API_BASE_LABEL = API_BASE;

// ---- Real clock: chat bubbles stamp the actual local send/receive time (IST). ----

function nowStampIST(): string {
  return new Date().toLocaleTimeString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// ---- Utility: classify event line kind (from reference) ----

function classifyEvent(ev: string): LogLine["kind"] {
  const s = ev.toLowerCase();
  if (/exhaust|fail|crash|error|degrad|block|unavailable/.test(s)) return "warn";
  if (/ ok|pass|recovered|grounded|resumed|failover|fell to/.test(s)) return "ok";
  return "info";
}

// ---- Utility: extract failed tools from events ----

function failedTools(events: string[]): string[] {
  const out: string[] = [];
  events.forEach((e) => {
    const m = /([A-Za-z_]\w*)\s+(?:EXHAUSTED|exhausted)/.exec(e);
    if (m) out.push(m[1]);
  });
  return Array.from(new Set(out));
}

// ---- Utility: pretty model name ----

function prettyModel(m?: string): string {
  if (!m) return "model";
  return String(m).split("/").pop() || m;
}

// ---- Utility: uid counter ----

let _uid = 0;
function nextUid() {
  return `cite-${++_uid}`;
}

// ---- Prose parsing: replace {{cite:KEY}} with markers ----

// We maintain a mutable runtime clause registry that merges the static CLAUSES
// with any clauses received from the live backend (keyed by cite_key).
const runtimeClauses: Record<string, ClauseInfo> = { ...CLAUSES };

function parseProse(rawParas: string[]): ProseParagraph[] {
  return rawParas.map((p) => {
    const citations: ProseParagraph["citations"] = [];
    const html = p.replace(/\{\{cite:(\w+)\}\}/g, (_, key: string) => {
      const c = runtimeClauses[key];
      if (!c) return "";
      const id = nextUid();
      const idx = citations.length;
      citations.push({ id, clause: c });
      return `%%CITE:${idx}%%`;
    });
    return { html, citations };
  });
}

// ---- Build real-receipt-driven ReceiptData ----

function buildReceiptData(
  data: AskResponse,
  query: string,
): ReceiptData {
  const rc = data.receipt || {};
  const g = rc.grounding || {};
  const blocked = !!rc.guardrail_blocked;
  const isFailover = rc.chaos_mode === "break_model";
  const grounded = blocked ? false : g.action === "pass" || g.action === "drop_and_note";

  const attempts = rc.tool_attempts || {};
  const failed = new Set(failedTools(rc.events || []));
  const tools = Object.keys(attempts).map((name) => ({
    name,
    status: (failed.has(name) ? "degraded" : "ok") as "ok" | "degraded",
  }));

  const resolved = prettyModel(rc.resolved_model);
  let models_tried: ReceiptData["models_tried"];
  if (isFailover) {
    models_tried = [
      { name: "primary", status: "unavailable" as const },
      { name: resolved, status: "ok" as const },
    ];
  } else if (rc.resolved_model) {
    models_tried = [{ name: resolved, status: "ok" as const }];
  } else {
    models_tried = [];
  }

  const guardrails: string[] = [];
  if (blocked) {
    guardrails.push(
      "input: " + (rc.guardrail_blocked!.integrations || []).join(", ") + " → blocked",
    );
  }
  if (g.action === "pass") {
    guardrails.push("output: grounding gate passed · all claims traced");
  } else if (g.action === "drop_and_note") {
    guardrails.push(
      "output: grounding gate · dropped " + (g.dropped || []).length + " unverified",
    );
  }

  return {
    query,
    models_tried,
    tools,
    checkpoint_resumed: !!rc.checkpoint_resumed,
    guardrails_fired: guardrails,
    latency_ms: data.latency_ms || 0,
    grounded,
  };
}

// ---- Register claim panels from live response (like reference's registerClaimPanels) ----

function registerClaimPanels(claims: Claim[]): string[] {
  return claims.map((c) => {
    runtimeClauses[c.cite_key] = {
      page: "p" + c.page,
      layer: "Policy wording · clause " + (c.clause || "—") + " · p" + c.page,
      text: c.quote || c.value || c.text,
    };
    return `${c.text} {{cite:${c.cite_key}}}`;
  });
}

// ---- Build agent message from live response ----

function buildLiveAgentMessage(data: AskResponse): AgentMessage {
  const rc = data.receipt || {};

  // Blocked?
  if (rc.guardrail_blocked) {
    const gb = rc.guardrail_blocked;
    const integ = (gb.integrations || []).join(", ") || "input guardrail";
    return {
      role: "agent",
      variant: "blocked",
      lede: "Blocked by an input safety guardrail.",
      prose: [],
      sources: "Stopped at the input guardrail — the agent never ran.",
      model: { kind: "primary", resolved: "" },
      blockedText: data.answer_text || "That request was blocked before reaching the agent.",
      blockedIntegration: integ,
    };
  }

  const claims = data.claims || [];
  const paras = registerClaimPanels(claims);
  const degraded = rc.tool_status === "degraded";
  const isFailover = rc.chaos_mode === "break_model";
  const resolved = prettyModel(rc.resolved_model);

  // Honest gap note
  let gap = "";
  if (degraded) {
    const ft = failedTools(rc.events || []);
    const toolStr = ft.length
      ? ft.map((t) => `<code>${t}</code>`).join(", ")
      : "a policy-lookup tool";
    gap =
      `I answered the parts I could trace to a verified clause. The ${toolStr} lookup timed out, ` +
      `so I'm leaving that part unconfirmed rather than guessing on it.`;
  }
  const dropped = (rc.grounding && rc.grounding.dropped) || [];
  if (dropped.length) {
    const d = dropped.map((x) => x.text).join("; ");
    gap =
      (gap ? gap + " " : "") +
      `I also dropped a claim I couldn't verify against the policy: ${d}.`;
  }

  return {
    role: "agent",
    variant: degraded ? "degraded" : "clean",
    lede: data.lede || (data.answer_text || "").split("\n")[0],
    prose: parseProse(paras),
    gap: gap || undefined,
    sources: degraded
      ? `Answered from ${claims.length} verified clause${claims.length === 1 ? "" : "s"} — 1 lookup degraded.`
      : `Answered from ${claims.length} clause${claims.length === 1 ? "" : "s"} in your policy.`,
    model: isFailover
      ? { kind: "failover", down: "", resolved }
      : { kind: "primary", resolved },
    degradedNote: degraded
      ? "1 tool degraded → answered with partial verification."
      : undefined,
  };
}

// ---- Build cached fallback agent message ----

function buildCachedAgentMessage(stateKey: string, reason?: string): AgentMessage {
  const a = ANSWERS[stateKey] || ANSWERS.clean;
  const isDegraded = stateKey === "degraded";

  return {
    role: "agent",
    variant: isDegraded ? "degraded" : "clean",
    lede: a.lede,
    prose: parseProse(a.paras),
    gap: a.gap,
    sources: a.sources,
    model: a.model,
    degradedNote: a.degradedNote,
    // Mark loudly so a cached mock can never masquerade as a live grounded answer.
    cached: true,
    cachedReason: reason,
  };
}

// ============================================================
// MAIN COMPONENT
// ============================================================

export default function PolicyDesk() {
  const [chaos, setChaos] = useState<ChaosState>({
    breakModel: false,
    failTool: false,
  });
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [statusMode, setStatusMode] = useState<"healthy" | "degraded" | "recovering">("healthy");
  const [logLines, setLogLines] = useState<LogLine[]>([]);
  // Absolute event times (epoch ms); the log renders them as elapsed since queryStart.
  const [logTimestamps, setLogTimestamps] = useState<number[]>([]);
  const [queryStart, setQueryStart] = useState<number>(() => Date.now());
  const [receipt, setReceipt] = useState<ReceiptData | null>(null);
  const [inputValue, setInputValue] = useState("");
  // Crash scene: holds the interrupted thread awaiting /resume. eventCount is
  // how many resilience events were already logged at crash time, so resume
  // only appends the new (synthesis-phase) events instead of re-logging.
  const [crash, setCrash] = useState<{ threadId: string; eventCount: number } | null>(null);
  const [resuming, setResuming] = useState(false);

  // ---- Log helpers ----
  // The `advance` arg is retained for call-site compatibility but ignored:
  // timestamps are now real wall-clock event times.
  const addLog = useCallback(
    (line: LogLine, advance: number = 1) => {
      void advance;
      setLogLines((prev) => [...prev, line]);
      setLogTimestamps((prev) => [...prev, Date.now()]);
    },
    [],
  );

  const clearLog = useCallback(() => {
    setLogLines([]);
    setLogTimestamps([]);
  }, []);

  // ---- Status helpers ----
  const refreshStatusFromChaos = useCallback(() => {
    setChaos((c) => {
      const armed = c.breakModel || c.failTool;
      setStatusMode(armed ? "degraded" : "healthy");
      return c;
    });
  }, []);

  // ---- Mode from chaos ----
  const modeFromChaos = useCallback((): string => {
    if (chaos.failTool) return "degraded";
    if (chaos.breakModel) return "fallback";
    return "clean";
  }, [chaos]);

  // ---- Real events from backend ----
  const renderRealEvents = useCallback(
    (events: string[]) => {
      events.forEach((ev) => {
        addLog({ kind: classifyEvent(ev), text: ev }, 1);
      });
    },
    [addLog],
  );

  // ---- Run live /ask ----
  const runLive = useCallback(
    (text: string, chaosPayload: ReturnType<typeof chaosForMode>) => {
      // Show thinking
      const thinkLabel = chaosPayload.break_model
        ? "Primary unavailable — failing over…"
        : "Checking your policy…";

      setMessages((prev) => [
        ...prev,
        { role: "thinking" as const, label: thinkLabel },
      ]);
      addLog({ kind: "info", text: "query received · routing to agent" }, 1);

      askBackend(text, chaosPayload)
        .then((data) => {
          // Remove thinking
          setMessages((prev) => prev.filter((m) => m.role !== "thinking"));
          // Log real events
          if (data.receipt?.events) renderRealEvents(data.receipt.events);
          // Build + append answer
          const agentMsg = buildLiveAgentMessage(data);
          setMessages((prev) => [...prev, agentMsg]);
          // Build + set receipt
          setReceipt(buildReceiptData(data, text));
          setBusy(false);
          refreshStatusFromChaos();
        })
        .catch((err) => {
          // Safety net: backend unreachable → show cached answer, clearly marked.
          setMessages((prev) => prev.filter((m) => m.role !== "thinking"));
          addLog(
            { kind: "err", text: `backend unreachable (${err}) — showing cached answer` },
            1,
          );
          const cachedMsg = buildCachedAgentMessage(
            "clean",
            `Could not reach ${API_BASE_LABEL} (${err}).`,
          );
          setMessages((prev) => [...prev, cachedMsg]);
          setReceipt(RECEIPTS.clean);
          setBusy(false);
          refreshStatusFromChaos();
        });
    },
    [addLog, renderRealEvents, refreshStatusFromChaos],
  );

  // ---- Send ----
  // `submit` is the single send path. `send` (Enter/Send button) reads the
  // input; `sendChip` fills the input with a suggestion and sends that text.
  const submit = useCallback(
    (explicit?: string) => {
      if (busy) return;
      const mode = modeFromChaos();
      const raw = typeof explicit === "string" ? explicit : inputValue;
      const text = raw.trim() || QUESTIONS[mode];
      setBusy(true);
      setQueryStart(Date.now());
      setMessages((prev) => [
        ...prev,
        { role: "user" as const, text, timestamp: nowStampIST() },
      ]);
      setInputValue("");

      if (mode !== "clean") setStatusMode("recovering");
      runLive(text, chaosForMode(mode));
    },
    [busy, modeFromChaos, inputValue, runLive],
  );

  const send = useCallback(() => submit(), [submit]);

  const sendChip = useCallback(
    (text: string) => {
      setInputValue(text);
      submit(text);
    },
    [submit],
  );

  // ---- Injection trigger ----
  const triggerInjection = useCallback(() => {
    if (busy) return;
    const text = QUESTIONS.injection;
    setBusy(true);
    setQueryStart(Date.now());
    setMessages((prev) => [
      ...prev,
      { role: "user" as const, text, timestamp: nowStampIST() },
    ]);
    setInputValue("");
    setStatusMode("recovering");
    runLive(text, {});
  }, [busy, runLive]);

  // ---- Crash trigger (Phase 3 — REAL backend, step 1 of 2) ----
  // Calls /ask with crash_after_tools: the graph runs the tools, commits the
  // SQLite checkpoint, then interrupts at crash_point (NO os._exit — the worker
  // stays alive). We render the honest interrupted state and surface a Resume
  // affordance. /resume (step 2) finishes the SAME thread from the checkpoint.
  const triggerCrash = useCallback(() => {
    if (busy) return;
    setBusy(true);
    setCrash(null);
    setQueryStart(Date.now());
    const text = QUESTIONS.crash;
    setMessages((prev) => [
      ...prev,
      { role: "user" as const, text, timestamp: nowStampIST() },
      { role: "thinking" as const, label: "Running tools…" },
    ]);
    setInputValue("");
    addLog({ kind: "info", text: "query received · routing to agent" }, 1);

    crashBackend(text)
      .then((data) => {
        setMessages((prev) => prev.filter((m) => m.role !== "thinking"));
        // Real pre-crash events straight off the partial receipt.
        renderRealEvents(data.partial_receipt.events || []);
        addLog(
          { kind: "warn", text: "process crashed after tool calls — checkpoint saved" },
          1,
        );
        const tools = Object.keys(data.partial_receipt.tool_attempts || {});
        const interruptedMsg: AgentMessage = {
          role: "agent",
          variant: "crash-interrupted",
          lede: "Answering…",
          prose: [],
          sources: "",
          model: { kind: "primary", resolved: "" },
          interruptedTools: tools,
        };
        setMessages((prev) => [...prev, interruptedMsg]);
        setStatusMode("degraded");
        setCrash({
          threadId: data.thread_id,
          eventCount: (data.partial_receipt.events || []).length,
        });
        setBusy(false);
      })
      .catch((err) => {
        // Safety net: backend unreachable → cached crash mock, clearly marked.
        setMessages((prev) => prev.filter((m) => m.role !== "thinking"));
        addLog(
          { kind: "err", text: `backend unreachable (${err}) — showing cached crash demo` },
          1,
        );
        const a = ANSWERS.crash;
        const resumedMsg: AgentMessage = {
          role: "agent",
          variant: "crash-resumed",
          lede: a.lede,
          prose: parseProse(a.paras),
          sources: a.sources,
          model: a.model,
          resumeBanner: a.resume,
          cached: true,
          cachedReason: `Could not reach ${API_BASE_LABEL} (${err}).`,
        };
        setMessages((prev) => [...prev, resumedMsg]);
        setReceipt(RECEIPTS.crash);
        setBusy(false);
        refreshStatusFromChaos();
      });
  }, [busy, addLog, renderRealEvents, refreshStatusFromChaos]);

  // ---- Resume from checkpoint (Phase 3 — REAL backend, step 2 of 2) ----
  const resumeCrash = useCallback(() => {
    if (!crash || resuming) return;
    const { threadId, eventCount } = crash;
    setResuming(true);
    setQueryStart(Date.now());
    setStatusMode("recovering");
    addLog({ kind: "ok", text: "checkpoint found → resuming at synthesis" }, 1);
    // Swap the interrupted message for a thinking indicator.
    setMessages((prev) => [
      ...prev.filter(
        (m) => !(m.role === "agent" && (m as AgentMessage).variant === "crash-interrupted"),
      ),
      { role: "thinking" as const, label: "Resuming from checkpoint…" },
    ]);

    resumeBackend(threadId)
      .then((data) => {
        setMessages((prev) => prev.filter((m) => m.role !== "thinking"));
        // Only the NEW (synthesis-phase) events — the tool events were already
        // logged at crash time. This visibly proves no tool re-ran.
        renderRealEvents((data.receipt?.events || []).slice(eventCount));
        addLog({ kind: "ok", text: "answer completed · no work repeated" }, 1);

        const agentMsg = buildLiveAgentMessage(data);
        if (data.receipt?.checkpoint_resumed) {
          agentMsg.variant = "crash-resumed";
          agentMsg.resumeBanner = {
            title: "Resumed from checkpoint — no work repeated",
            sub: "Process crashed after the tool calls completed. Resumed at synthesis; the tools were not re-run.",
          };
        }
        setMessages((prev) => [...prev, agentMsg]);
        setReceipt(buildReceiptData(data, QUESTIONS.crash));
        setCrash(null);
        setResuming(false);
        setBusy(false);
        refreshStatusFromChaos();
      })
      .catch((err) => {
        setMessages((prev) => prev.filter((m) => m.role !== "thinking"));
        addLog(
          { kind: "err", text: `resume failed (${err}) — showing cached crash demo` },
          1,
        );
        const a = ANSWERS.crash;
        const resumedMsg: AgentMessage = {
          role: "agent",
          variant: "crash-resumed",
          lede: a.lede,
          prose: parseProse(a.paras),
          sources: a.sources,
          model: a.model,
          resumeBanner: a.resume,
          cached: true,
          cachedReason: `Could not reach ${API_BASE_LABEL} (${err}).`,
        };
        setMessages((prev) => [...prev, resumedMsg]);
        setReceipt(RECEIPTS.crash);
        setCrash(null);
        setResuming(false);
        setBusy(false);
        refreshStatusFromChaos();
      });
  }, [crash, resuming, addLog, renderRealEvents, refreshStatusFromChaos]);

  // ---- Toggle chaos ----
  const toggleChaos = useCallback(
    (key: keyof ChaosState) => {
      setChaos((prev) => {
        const next = { ...prev, [key]: !prev[key] };
        // Log arm/disarm
        if (next[key]) {
          const script =
            key === "breakModel"
              ? LOG_SCRIPTS.arm_breakModel
              : LOG_SCRIPTS.arm_failTool;
          script.forEach((l) => addLog(l, 1));
        } else {
          const label =
            key === "breakModel" ? "primary model break" : "tool failure";
          addLog({ kind: "info", text: `${label} cleared` }, 1);
        }
        // Update status
        const armed = next.breakModel || next.failTool;
        setStatusMode(armed ? "degraded" : "healthy");
        // Prefill input
        if (next.failTool) setInputValue(QUESTIONS.degraded);
        else if (next.breakModel) setInputValue(QUESTIONS.fallback);
        else setInputValue("");

        return next;
      });
    },
    [addLog],
  );

  // ---- Mount: index the policy, but do NOT auto-send. The chat starts empty
  // with suggestion chips; the user picks one (or types) to begin. ----
  const mounted = useRef(false);
  useEffect(() => {
    if (mounted.current) return;
    mounted.current = true;

    setQueryStart(Date.now());
    addLog({ kind: "info", text: "policy loaded · clauses indexed" }, 0);
    setStatusMode("healthy");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="policydesk-root">
      <TopBar statusMode={statusMode} />
      <div className="workspace">
        <ThreadView
          messages={messages}
          inputValue={inputValue}
          onInputChange={setInputValue}
          onSend={send}
          busy={busy}
          onResume={crash ? resumeCrash : undefined}
          resuming={resuming}
          suggestions={SUGGESTIONS}
          onSuggestion={sendChip}
          showSuggestions={messages.length === 0}
        />
        <ChaosRail
          chaos={chaos}
          onToggle={toggleChaos}
          onTriggerCrash={triggerCrash}
          onTriggerInjection={triggerInjection}
          busy={busy}
          logLines={logLines}
          logTimestamps={logTimestamps}
          queryStart={queryStart}
          onClearLog={clearLog}
          receipt={receipt}
        />
      </div>
    </div>
  );
}
