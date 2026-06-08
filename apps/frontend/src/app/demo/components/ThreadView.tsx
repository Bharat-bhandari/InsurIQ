"use client";

import { useRef, useEffect, Fragment, useState, useCallback } from "react";
import type { ClauseInfo } from "../constants";
import ModelBadge from "./ModelBadge";

// ---- Message types ----

export interface UserMessage {
  role: "user";
  text: string;
  timestamp: string;
}

export interface ThinkingMessage {
  role: "thinking";
  label: string;
}

export interface AgentMessage {
  role: "agent";
  variant: "clean" | "degraded" | "blocked" | "crash-interrupted" | "crash-resumed";
  lede: string;
  prose: ProseParagraph[];
  gap?: string;
  sources: string;
  model: { kind: "primary" | "failover"; resolved: string; down?: string };
  degradedNote?: string;
  resumeBanner?: { title: string; sub: string };
  // crash-interrupted state: tools completed before the process stopped
  interruptedTools?: string[];
  // cached fallback (backend unreachable) — must never masquerade as a live answer
  cached?: boolean;
  cachedReason?: string;
  // blocked state
  blockedText?: string;
  blockedIntegration?: string;
}

export type Message = UserMessage | ThinkingMessage | AgentMessage;

// A paragraph that may contain inline citation references
export interface CitationRef {
  id: string;
  clause: ClauseInfo;
}

export interface ProseParagraph {
  // The HTML text with {{cite:KEY}} already replaced by a placeholder marker
  html: string;
  citations: CitationRef[];
}

// ---- Inline citation chip (button only — panel rendered separately) ----

function InlineCiteButton({
  clause,
  isOpen,
  onToggle,
}: {
  clause: ClauseInfo;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      className="cite-chip"
      type="button"
      aria-expanded={isOpen}
      onClick={onToggle}
    >
      {clause.page}
      <span className="chev">▾</span>
    </button>
  );
}

function CitePanel({ id, clause }: { id: string; clause: ClauseInfo }) {
  return (
    <div className="cite-panel open" id={id}>
      <div className="layer">
        <span className="verified-tick">✓</span>
        {clause.layer}
      </div>
      <div className="quote">&ldquo;{clause.text}&rdquo;</div>
    </div>
  );
}

// ---- Gap callout ----

function GapCallout({ html }: { html: string }) {
  return (
    <div className="callout-gap">
      <svg
        className="ico"
        width={17}
        height={17}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.9}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
        <path d="M12 9v4M12 17h.01" />
      </svg>
      <div className="body" dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}

// ---- Resume banner ----

function ResumeBanner({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="resume-banner">
      <svg
        className="ico"
        width={17}
        height={17}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.9}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
        <path d="M3 3v5h5" />
      </svg>
      <div className="body">
        <b>{title}</b>
        <span className="sub">{sub}</span>
      </div>
    </div>
  );
}

// ---- Render prose with inline citation chips ----
// The prose HTML contains %%CITE:idx%% markers placed by the parent.
// We split on those and render React components inline.

function ProseWithCitations({ paragraphs }: { paragraphs: ProseParagraph[] }) {
  // Track which citation IDs are open
  const [openCites, setOpenCites] = useState<Set<string>>(new Set());
  const toggleCite = useCallback((id: string) => {
    setOpenCites((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  return (
    <div className="prose">
      {paragraphs.map((p, pi) => (
        <ProsePara
          key={pi}
          paragraph={p}
          openCites={openCites}
          onToggleCite={toggleCite}
        />
      ))}
    </div>
  );
}

function ProsePara({
  paragraph,
  openCites,
  onToggleCite,
}: {
  paragraph: ProseParagraph;
  openCites: Set<string>;
  onToggleCite: (id: string) => void;
}) {
  const { html, citations } = paragraph;
  // Split the html on %%CITE:N%% markers
  const parts = html.split(/(%%CITE:\d+%%)/);
  return (
    <>
      <p>
        {parts.map((part, i) => {
          const m = part.match(/^%%CITE:(\d+)%%$/);
          if (m) {
            const idx = parseInt(m[1], 10);
            const cite = citations[idx];
            if (cite) {
              return (
                <InlineCiteButton
                  key={i}
                  clause={cite.clause}
                  isOpen={openCites.has(cite.id)}
                  onToggle={() => onToggleCite(cite.id)}
                />
              );
            }
            return null;
          }
          return <Fragment key={i}><span dangerouslySetInnerHTML={{ __html: part }} /></Fragment>;
        })}
      </p>
      {/* Render citation panels OUTSIDE the <p> to avoid div-in-p hydration error */}
      {citations.map((cite) =>
        openCites.has(cite.id) ? (
          <CitePanel key={cite.id} id={cite.id} clause={cite.clause} />
        ) : null,
      )}
    </>
  );
}

// ---- Blocked answer (Scene C) ----

function BlockedAnswer({ msg }: { msg: AgentMessage }) {
  return (
    <div className="msg agent">
      <div className="answer answer--degraded">
        <div className="lede">Blocked by an input safety guardrail.</div>
        <div className="callout-gap">
          <svg
            className="ico"
            width={17}
            height={17}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.9}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 2 4 5v6c0 5 3.4 8.5 8 11 4.6-2.5 8-6 8-11V5z" />
            <path d="M9 12h6M12 9v6" transform="rotate(45 12 12)" />
          </svg>
          <div className="body">
            {msg.blockedText || "That request was blocked before reaching the agent."}
          </div>
        </div>
        <div className="answer-meta">
          <span className="meta-sources">
            Stopped at the input guardrail — the agent never ran.
          </span>
          <span className="meta-spacer" />
          <span className="degraded-note">
            ⚠ {msg.blockedIntegration || "input guardrail"}
          </span>
        </div>
      </div>
    </div>
  );
}

// ---- Cached fallback banner (backend unreachable) ----
// Loud, unmistakable: a cached mock must NEVER look like a live grounded answer.

function CachedBanner({ reason }: { reason?: string }) {
  return (
    <div
      className="cached-banner"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 12px",
        marginBottom: 10,
        borderRadius: 8,
        background: "#7c2d12",
        color: "#fff7ed",
        border: "1px solid #ea580c",
        fontWeight: 600,
        fontSize: 13,
      }}
    >
      <span aria-hidden>⚠</span>
      <span>
        Showing a CACHED answer — backend unreachable.{" "}
        <span style={{ fontWeight: 400, opacity: 0.9 }}>
          {reason || "This is not a live response."}
        </span>
      </span>
    </div>
  );
}

// ---- Standard answer rendering ----

function AnswerBlock({ msg }: { msg: AgentMessage }) {
  const isDegraded = msg.variant === "degraded";
  const isCrashResumed = msg.variant === "crash-resumed";
  const cls = msg.cached
    ? " answer--cached"
    : isDegraded
    ? " answer--degraded"
    : isCrashResumed
    ? " answer--crash"
    : "";

  return (
    <div className="msg agent">
      <div className={`answer${cls}`}>
        {msg.cached && <CachedBanner reason={msg.cachedReason} />}
        {isCrashResumed && msg.resumeBanner && (
          <ResumeBanner title={msg.resumeBanner.title} sub={msg.resumeBanner.sub} />
        )}
        <div className="lede">{msg.lede}</div>
        <ProseWithCitations paragraphs={msg.prose} />
        {msg.gap && <GapCallout html={msg.gap} />}
        <div className="answer-meta">
          <span className="meta-sources">{msg.sources}</span>
          <span className="meta-spacer" />
          {msg.degradedNote && (
            <span className="degraded-note">⚠ {msg.degradedNote} </span>
          )}
          <ModelBadge model={msg.model} />
        </div>
      </div>
    </div>
  );
}

// ---- Interrupted answer (crash partial) ----

function InterruptedAnswer({
  msg,
  onResume,
  resuming,
}: {
  msg: AgentMessage;
  onResume?: () => void;
  resuming?: boolean;
}) {
  const tools = msg.interruptedTools || [];
  return (
    <div className="msg agent">
      <div className="answer answer--crash">
        <div className="lede">{msg.lede}</div>
        <div className="callout-gap">
          <svg
            className="ico"
            width={17}
            height={17}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.9}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 9v4M12 17h.01" />
            <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
          </svg>
          <div className="body">
            <b>Process crashed after tool calls. Checkpoint saved.</b>
            <span style={{ display: "block", marginTop: 4 }}>
              {tools.length
                ? `Tools completed and checkpointed: ${tools
                    .map((t) => t)
                    .join(", ")}. Synthesis never ran.`
                : "Tool results were checkpointed before the crash. Synthesis never ran."}
            </span>
          </div>
        </div>
        <div className="answer-meta">
          <span className="interrupted-tag">
            ● process interrupted — synthesis incomplete
          </span>
          <span className="meta-spacer" />
          {onResume && (
            <button
              className="trigger-btn"
              disabled={resuming}
              onClick={onResume}
            >
              {resuming ? "Resuming…" : "Resume from checkpoint"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ---- Main ThreadView ----

interface ThreadViewProps {
  messages: Message[];
  inputValue: string;
  onInputChange: (v: string) => void;
  onSend: () => void;
  busy: boolean;
  onResume?: () => void;
  resuming?: boolean;
  suggestions?: string[];
  onSuggestion?: (text: string) => void;
  showSuggestions?: boolean;
}

export default function ThreadView({
  messages,
  inputValue,
  onInputChange,
  onSend,
  busy,
  onResume,
  resuming,
  suggestions,
  onSuggestion,
  showSuggestions,
}: ThreadViewProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length]);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") onSend();
  };

  return (
    <main className="main-region">
      <div className="thread-scroll" ref={scrollRef}>
        <div className="thread">
          {/* Context banner */}
          <div className="context-banner">
            <svg
              className="doc-ico"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.7}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <path d="M14 2v6h6" />
              <path d="M8 13h8M8 17h6" />
            </svg>
            <span>
              Asking about <b>Niva Bupa ReAssure 2.0</b> — Platinum+ · policy active
              since 29 March 2023.
            </span>
          </div>

          {/* Messages */}
          {messages.map((msg, i) => {
            if (msg.role === "user") {
              return (
                <div key={i} className="msg user">
                  <div className="bubble-user">{msg.text}</div>
                  <div className="timestamp">{msg.timestamp}</div>
                </div>
              );
            }
            if (msg.role === "thinking") {
              return (
                <div key={i} className="msg agent">
                  <div className="thinking">
                    <span className="dots">
                      <i />
                      <i />
                      <i />
                    </span>
                    <span>{msg.label}</span>
                  </div>
                </div>
              );
            }
            // Agent messages
            if (msg.variant === "blocked") {
              return <BlockedAnswer key={i} msg={msg} />;
            }
            if (msg.variant === "crash-interrupted") {
              return (
                <InterruptedAnswer
                  key={i}
                  msg={msg}
                  onResume={onResume}
                  resuming={resuming}
                />
              );
            }
            return <AnswerBlock key={i} msg={msg} />;
          })}
        </div>
      </div>

      {/* Input dock */}
      <div className="input-dock">
        <div className="dock-inner">
          {showSuggestions && suggestions && suggestions.length > 0 && (
            <div className="suggestion-group">
              <div className="suggestion-caption">Try asking</div>
              <div className="suggestion-chips">
                {suggestions.map((s, i) => (
                  <button
                    key={i}
                    type="button"
                    className="suggestion-chip"
                    disabled={busy}
                    onClick={() => onSuggestion?.(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="input-row">
            <input
              id="ask-input"
              type="text"
              placeholder="Ask about your coverage…"
              autoComplete="off"
              value={inputValue}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={handleKey}
            />
            <button className="send-btn" disabled={busy} onClick={onSend}>
              Send
              <svg
                width={14}
                height={14}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </button>
          </div>
          <div className="dock-note">
            Answers come from your policy, with citations. The agent never guesses.
          </div>
        </div>
      </div>
    </main>
  );
}
