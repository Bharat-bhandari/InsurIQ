"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import "./policydesk.css";

import TopBar from "./components/TopBar";
import ThreadView from "./components/ThreadView";
import ChaosRail from "./components/ChaosRail";
import type { ChaosState } from "./components/ChaosRail";
import type { Message, ProseParagraph, AgentMessage } from "./components/ThreadView";
import type { LogLine, ReceiptData, ClauseInfo } from "./constants";
import { QUESTIONS, CLAUSES, ANSWERS, RECEIPTS, LOG_SCRIPTS } from "./constants";
import { askBackend, chaosForMode, API_BASE } from "./api";
import type { AskResponse, Claim } from "./api";

const API_BASE_LABEL = API_BASE;

// ---- Mock clock (matches reference: reads cleaner in demos) ----

function useMockClock() {
  const clock = useRef(new Date(2026, 5, 6, 14, 2, 50));
  const tick = useCallback((sec: number) => {
    clock.current = new Date(clock.current.getTime() + sec * 1000);
  }, []);
  const stamp = useCallback(() => {
    const p = (n: number) => String(n).padStart(2, "0");
    const d = clock.current;
    return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  }, []);
  return { tick, stamp };
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
    rateLimit: false,
  });
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [statusMode, setStatusMode] = useState<"healthy" | "degraded" | "recovering">("healthy");
  const [logLines, setLogLines] = useState<LogLine[]>([]);
  const [logTimestamps, setLogTimestamps] = useState<string[]>([]);
  const [receipt, setReceipt] = useState<ReceiptData | null>(null);
  const [inputValue, setInputValue] = useState(QUESTIONS.clean);

  const { tick, stamp } = useMockClock();

  // ---- Log helpers ----
  const addLog = useCallback(
    (line: LogLine, advance: number = 1) => {
      if (advance) tick(advance);
      setLogLines((prev) => [...prev, line]);
      setLogTimestamps((prev) => [...prev, stamp()]);
    },
    [tick, stamp],
  );

  const addLogs = useCallback(
    (lines: LogLine[], baseAdvance: number = 1) => {
      lines.forEach((l, i) => {
        addLog(l, i === 0 ? baseAdvance : l.indent ? 0 : 1);
      });
    },
    [addLog],
  );

  const clearLog = useCallback(() => {
    setLogLines([]);
    setLogTimestamps([]);
  }, []);

  // ---- Status helpers ----
  const refreshStatusFromChaos = useCallback(() => {
    setChaos((c) => {
      const armed = c.breakModel || c.failTool || c.rateLimit;
      setStatusMode(armed ? "degraded" : "healthy");
      return c;
    });
  }, []);

  // ---- Mode from chaos ----
  const modeFromChaos = useCallback((): string => {
    if (chaos.failTool) return "degraded";
    if (chaos.breakModel || chaos.rateLimit) return "fallback";
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
  const send = useCallback(() => {
    if (busy) return;
    const mode = modeFromChaos();
    const text = inputValue.trim() || QUESTIONS[mode];
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { role: "user" as const, text, timestamp: stamp() },
    ]);
    setInputValue("");

    if (mode !== "clean") setStatusMode("recovering");
    runLive(text, chaosForMode(mode));
  }, [busy, modeFromChaos, inputValue, stamp, runLive]);

  // ---- Injection trigger ----
  const triggerInjection = useCallback(() => {
    if (busy) return;
    const text = QUESTIONS.injection;
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { role: "user" as const, text, timestamp: stamp() },
    ]);
    setInputValue("");
    setStatusMode("recovering");
    runLive(text, {});
  }, [busy, stamp, runLive]);

  // ---- Crash trigger (client-side mock, Phase 3) ----
  const triggerCrash = useCallback(() => {
    if (busy) return;
    setBusy(true);
    const text = QUESTIONS.crash;
    setMessages((prev) => [
      ...prev,
      { role: "user" as const, text, timestamp: stamp() },
    ]);
    setInputValue("");

    // Log pre-crash lines
    const crashLines = LOG_SCRIPTS.crash_seq;
    crashLines.slice(0, 3).forEach((l, i) => addLog(l, i === 0 ? 1 : 1));

    // Show thinking briefly, then interrupted, then resumed
    setMessages((prev) => [
      ...prev,
      { role: "thinking" as const, label: "Synthesizing answer…" },
    ]);

    setTimeout(() => {
      // Remove thinking, show interrupted
      setMessages((prev) => {
        const without = prev.filter((m) => m.role !== "thinking");
        const a = ANSWERS.crash;
        const interruptedMsg: AgentMessage = {
          role: "agent",
          variant: "crash-interrupted",
          lede: a.lede,
          prose: parseProse(a.partial || []),
          sources: "",
          model: a.model,
        };
        return [...without, interruptedMsg];
      });
      setStatusMode("degraded");
    }, 900);

    // Recovery log lines
    setTimeout(() => {
      crashLines.slice(3).forEach((l, i) => addLog(l, i === 0 ? 1 : l.indent ? 0 : 1));
    }, 1600);

    // Replace interrupted with full resumed answer
    setTimeout(() => {
      setStatusMode("recovering");
      setMessages((prev) => {
        // Remove the interrupted message (last agent message)
        const idx = prev.findLastIndex(
          (m) => m.role === "agent" && (m as AgentMessage).variant === "crash-interrupted",
        );
        if (idx < 0) return prev;

        const a = ANSWERS.crash;
        const resumedMsg: AgentMessage = {
          role: "agent",
          variant: "crash-resumed",
          lede: a.lede,
          prose: parseProse(a.paras),
          sources: a.sources,
          model: a.model,
          resumeBanner: a.resume,
        };
        const next = [...prev];
        next[idx] = resumedMsg;
        return next;
      });
      setReceipt(RECEIPTS.crash);

      setTimeout(() => {
        setBusy(false);
        refreshStatusFromChaos();
      }, 900);
    }, 2200);
  }, [busy, stamp, addLog, refreshStatusFromChaos]);

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
              : key === "failTool"
              ? LOG_SCRIPTS.arm_failTool
              : LOG_SCRIPTS.arm_rateLimit;
          script.forEach((l, i) => addLog(l, i === 0 ? 1 : 1));
        } else {
          const label =
            key === "breakModel"
              ? "primary model break"
              : key === "failTool"
              ? "tool failure"
              : "rate-limit";
          addLog({ kind: "info", text: `${label} cleared` }, 1);
        }
        // Update status
        const armed = next.breakModel || next.failTool || next.rateLimit;
        setStatusMode(armed ? "degraded" : "healthy");
        // Prefill input
        if (next.failTool) setInputValue(QUESTIONS.degraded);
        else if (next.breakModel || next.rateLimit) setInputValue(QUESTIONS.fallback);
        else setInputValue(QUESTIONS.clean);

        return next;
      });
    },
    [addLog],
  );

  // ---- Seed: fire one clean /ask on mount ----
  const seeded = useRef(false);
  useEffect(() => {
    if (seeded.current) return;
    seeded.current = true;

    addLog({ kind: "info", text: "policy loaded · clauses indexed" }, 0);

    const text = QUESTIONS.clean;
    setBusy(true);
    setMessages([{ role: "user", text, timestamp: stamp() }]);
    runLive(text, {});
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
        />
        <ChaosRail
          chaos={chaos}
          onToggle={toggleChaos}
          onTriggerCrash={triggerCrash}
          onTriggerInjection={triggerInjection}
          busy={busy}
          logLines={logLines}
          logTimestamps={logTimestamps}
          onClearLog={clearLog}
          receipt={receipt}
        />
      </div>
    </div>
  );
}
