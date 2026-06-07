"use client";

import type { LogLine, ReceiptData } from "../constants";
import EventLog from "./EventLog";
import ReceiptPanel from "./ReceiptPanel";

export interface ChaosState {
  breakModel: boolean;
  failTool: boolean;
}

interface ChaosRailProps {
  chaos: ChaosState;
  onToggle: (key: keyof ChaosState) => void;
  onTriggerCrash: () => void;
  onTriggerInjection: () => void;
  busy: boolean;
  logLines: LogLine[];
  logTimestamps: number[];
  queryStart: number;
  onClearLog: () => void;
  receipt: ReceiptData | null;
}

export default function ChaosRail({
  chaos,
  onToggle,
  onTriggerCrash,
  onTriggerInjection,
  busy,
  logLines,
  logTimestamps,
  queryStart,
  onClearLog,
  receipt,
}: ChaosRailProps) {
  return (
    <aside className="chaos-rail">
      {/* Header */}
      <div className="rail-section rail-head">
        <div className="title">
          Chaos controls <span className="badge-chaos">demo</span>
        </div>
        <div className="subtitle">Break things. Watch it recover.</div>
      </div>

      {/* Controls */}
      <div className="rail-section" style={{ paddingTop: 4 }}>
        {/* 1 · Break primary model */}
        <div className={`ctrl${chaos.breakModel ? " armed" : ""}`}>
          <div className="ctrl-top">
            <div className="ctrl-label">Break primary model</div>
            <button
              className="switch"
              role="switch"
              aria-checked={chaos.breakModel}
              aria-label="Break primary model"
              onClick={() => onToggle("breakModel")}
            />
          </div>
          <div className="ctrl-desc">
            Primary LLM goes down. Next answer fails over to the backup model — same
            answer quality.
          </div>
        </div>

        {/* 2 · Fail policy-lookup tool */}
        <div className={`ctrl${chaos.failTool ? " armed" : ""}`}>
          <div className="ctrl-top">
            <div className="ctrl-label">Fail policy-lookup tool</div>
            <button
              className="switch"
              role="switch"
              aria-checked={chaos.failTool}
              aria-label="Fail policy-lookup tool"
              onClick={() => onToggle("failTool")}
            />
          </div>
          <div className="ctrl-desc">
            The <code>get_room_rent_rule</code> tool times out. The agent answers what
            it can verify and flags the gap.
          </div>
        </div>

        {/* 3 · Crash mid-answer */}
        <div className="ctrl">
          <div className="ctrl-top">
            <div className="ctrl-label">Crash mid-answer</div>
            <button
              className="trigger-btn"
              disabled={busy}
              onClick={onTriggerCrash}
            >
              Trigger
            </button>
          </div>
          <div className="ctrl-desc">
            Kill the process during synthesis. The agent resumes from its last
            checkpoint — no work repeated.
          </div>
        </div>

        {/* 4 · Prompt injection */}
        <div className="ctrl">
          <div className="ctrl-top">
            <div className="ctrl-label">Prompt injection</div>
            <button
              className="trigger-btn"
              disabled={busy}
              onClick={onTriggerInjection}
            >
              Attempt
            </button>
          </div>
          <div className="ctrl-desc">
            Send an &ldquo;ignore your instructions&rdquo; attack. The gateway&apos;s{" "}
            <code>insuriq-prompt-injection</code> guardrail blocks it before the agent
            runs.
          </div>
        </div>
      </div>

      <div className="rail-divider" />

      {/* Event log */}
      <EventLog
        lines={logLines}
        timestamps={logTimestamps}
        queryStart={queryStart}
        onClear={onClearLog}
      />

      {/* Receipt */}
      <ReceiptPanel receipt={receipt} />
    </aside>
  );
}
