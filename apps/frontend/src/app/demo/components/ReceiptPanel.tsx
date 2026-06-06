"use client";

import { useState } from "react";
import type { ReceiptData } from "../constants";

interface ReceiptPanelProps {
  receipt: ReceiptData | null;
}

function K({ children }: { children: React.ReactNode }) {
  return <span className="rcp-k">{children}</span>;
}
function P({ children }: { children: React.ReactNode }) {
  return <span className="rcp-punct">{children}</span>;
}
function Str({ children }: { children: React.ReactNode }) {
  return <span className="rcp-str">&quot;{children}&quot;</span>;
}

function StatusSpan({ status }: { status: string }) {
  const cls = status === "ok" ? "rcp-s" : status === "degraded" ? "rcp-warn" : "rcp-down";
  const mark = status === "ok" ? "✓" : status === "degraded" ? "⚠" : "✕";
  return (
    <span className={cls}>
      &quot;{status}&quot; {mark}
    </span>
  );
}

export default function ReceiptPanel({ receipt }: ReceiptPanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <section className={`receipt${collapsed ? " collapsed" : ""}`}>
      <div className="receipt-head" onClick={() => setCollapsed((v) => !v)}>
        <div className="rt">
          <svg
            className="seal"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 2 4 5v6c0 5 3.4 8.5 8 11 4.6-2.5 8-6 8-11V5z" />
            <path d="m9 12 2 2 4-4" />
          </svg>
          Resilience receipt — last query
        </div>
        <svg
          className="chev"
          width={16}
          height={16}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </div>
      <div className="receipt-body">
        <div className="receipt-card">
          {receipt ? <ReceiptContent receipt={receipt} /> : <span className="rcp-k">No query yet</span>}
        </div>
      </div>
    </section>
  );
}

function ReceiptContent({ receipt: r }: { receipt: ReceiptData }) {
  return (
    <>
      <span className="rcp-row">
        <P>{"{"}</P>
      </span>

      {/* query */}
      <span className="rcp-indent">
        <K>query</K>
        <P>: </P>
        <Str>{r.query}</Str>
        <P>,</P>
      </span>

      {/* models_tried */}
      <span className="rcp-indent">
        <K>models_tried</K>
        <P>: [</P>
      </span>
      {r.models_tried.map((m, i) => {
        const dead = m.status !== "ok";
        return (
          <span key={i} className="rcp-indent" style={{ paddingLeft: 32 }}>
            {dead ? (
              <span className="rcp-down">
                &quot;{m.name} — {m.status}&quot;
              </span>
            ) : (
              <>
                <span className="rcp-str">&quot;{m.name}&quot;</span>{" "}
                <span className="rcp-s">✓</span>
              </>
            )}
            {i < r.models_tried.length - 1 && <P>,</P>}
          </span>
        );
      })}
      <span className="rcp-indent">
        <P>],</P>
      </span>

      {/* tools */}
      <span className="rcp-indent">
        <K>tools</K>
        <P>: [</P>
      </span>
      {r.tools.map((t, i) => (
        <span key={i} className="rcp-indent" style={{ paddingLeft: 32 }}>
          <P>{"{ "}</P>
          <K>name</K>
          <P>: </P>
          <Str>{t.name}</Str>
          <P>, </P>
          <K>status</K>
          <P>: </P>
          <StatusSpan status={t.status} />
          <P>{" }"}</P>
          {i < r.tools.length - 1 && <P>,</P>}
        </span>
      ))}
      <span className="rcp-indent">
        <P>],</P>
      </span>

      {/* checkpoint_resumed */}
      <span className="rcp-indent">
        <K>checkpoint_resumed</K>
        <P>: </P>
        <span className={r.checkpoint_resumed ? "rcp-bool-t" : "rcp-bool-f"}>
          {String(r.checkpoint_resumed)}
        </span>
        <P>,</P>
      </span>

      {/* guardrails_fired */}
      <span className="rcp-indent">
        <K>guardrails_fired</K>
        <P>: [</P>
      </span>
      {r.guardrails_fired.map((g, i) => (
        <span key={i} className="rcp-indent" style={{ paddingLeft: 32 }}>
          <Str>{g}</Str>
          {i < r.guardrails_fired.length - 1 && <P>,</P>}
        </span>
      ))}
      <span className="rcp-indent">
        <P>],</P>
      </span>

      {/* latency_ms */}
      <span className="rcp-indent">
        <K>latency_ms</K>
        <P>: </P>
        <span className="rcp-num">{r.latency_ms}</span>
        <P>,</P>
      </span>

      {/* grounded */}
      <span className="rcp-indent">
        <K>grounded</K>
        <P>: </P>
        <span className="rcp-bool-t">{String(r.grounded)}</span>
      </span>

      <span className="rcp-row">
        <P>{"}"}</P>
      </span>

      {/* footer */}
      <div className="receipt-foot">
        <svg
          width={13}
          height={13}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M20 6 9 17l-5-5" />
        </svg>
        Every stated fact traced to a verified clause.
      </div>
    </>
  );
}
