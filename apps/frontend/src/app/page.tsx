import type { Metadata } from "next";
import Link from "next/link";
import "./landing.css";

export const metadata: Metadata = {
  title: "InsurIQ — Insurance answers that survive failure",
  description:
    "InsurIQ answers questions about your health policy with a citation for every fact — and keeps answering when the model goes down, a tool fails, or the process crashes mid-question.",
};

/* ---- Inline SVG helpers (tiny, keeps the file self-contained) ---- */

function ArrowRight({ size = 15 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

function ArrowDown() {
  return (
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
      <path d="M12 5v14M6 13l6 6 6-6" />
    </svg>
  );
}

function DocIcon() {
  return (
    <svg
      className="doc"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}

/* ---- Feature icon components ---- */

function IcoFallback() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
      <path d="M3 21v-5h5" />
    </svg>
  );
}

function IcoShield() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 2 4 5v6c0 5 3.4 8.5 8 11 4.6-2.5 8-6 8-11V5z" />
    </svg>
  );
}

function IcoLock() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x={3} y={11} width={18} height={11} rx={2} />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

function IcoWarning() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9v4M12 17h.01" />
    </svg>
  );
}

function IcoResume() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
      <path d="M3 3v5h5" />
      <path d="M12 8v4l3 2" />
    </svg>
  );
}

function IcoCheck() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

/* ============================================================
   LANDING PAGE
   ============================================================ */

export default function LandingPage() {
  return (
    <div className="landing-root">
      {/* ---- Top bar ---- */}
      <header className="topbar">
        <div className="wrap">
          <Link className="wordmark" href="/">
            <span className="mark">I</span>InsurIQ
          </Link>
          <Link className="btn btn-primary btn-sm" href="/demo">
            Open the demo
            <ArrowRight size={14} />
          </Link>
        </div>
      </header>

      {/* ---- Hero ---- */}
      <section className="hero" id="top">
        <div className="wrap">
          <div className="hero-left">
            <div className="eyebrow hero-eyebrow">
              TrueFoundry · Resilient Agents
            </div>
            <h1>Insurance answers that survive failure.</h1>
            <p className="lead">
              InsurIQ answers questions about your health policy with a citation
              for every fact — and keeps answering when the model goes down, a
              tool fails, or the process crashes mid-question.
            </p>
            <div className="hero-cta">
              <Link className="btn btn-primary btn-lg" href="/demo">
                Break it yourself
                <ArrowRight />
              </Link>
              <a className="link-quiet" href="#how">
                See how it stays up
                <ArrowDown />
              </a>
            </div>
          </div>

          {/* Hero artifact card */}
          <div className="hero-right">
            <div className="artifact">
              <div className="artifact-head">
                <DocIcon />
                <span>
                  Niva Bupa ReAssure 2.0 · <b>Platinum+</b>
                </span>
                <span className="pill">
                  <span className="dot" />
                  Healthy
                </span>
              </div>
              <div className="artifact-body">
                <div className="artifact-q">
                  <span>Is my knee replacement covered?</span>
                </div>
                <div className="artifact-lede">
                  Yes — after a 24-month waiting period.
                  <span className="cite-chip" style={{ marginLeft: 7 }}>
                    p.37
                  </span>
                </div>
                <div className="artifact-clause">
                  <div className="layer">
                    <span className="tick">✓</span>Wording · clause 5.1.2(f) ·
                    page 37
                  </div>
                  <div className="quote">
                    &ldquo;List of specific diseases/procedures … vii.
                    Osteoarthritis, joint replacement, osteoporosis, …
                    intervertebral disc disorders, arthroscopic surgeries for
                    ligament repair.&rdquo;
                  </div>
                </div>
                <div className="artifact-foot">
                  <span className="ok">✓</span>answered by mistral.devstral ·
                  primary
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---- Problem ---- */}
      <section className="problem">
        <div className="wrap">
          <div className="eyebrow">Why this is hard</div>
          <h2>Most agents are built for the happy path.</h2>
          <p className="lead">
            They crash when a provider rate-limits, a tool times out, or the
            process dies mid-task. And worse — when they can&apos;t find an
            answer, many just <b>hallucinate a confident one</b>. In insurance,
            a confident wrong answer about a waiting period or an exclusion can
            cost someone their claim. Reliability isn&apos;t a nice-to-have
            here; it&apos;s the whole point.
          </p>
        </div>
      </section>

      {/* ---- Two-tier resilience ---- */}
      <section className="tiers" id="how">
        <div className="wrap">
          <div className="tiers-head">
            <div className="eyebrow">How it stays up</div>
            <h2>Two tiers of resilience.</h2>
          </div>

          <div className="tier-grid">
            {/* Tier 1 */}
            <div className="tier tier--one">
              <div className="tier-tag">
                Tier 1 <span className="badge">handled by TrueFoundry</span>
              </div>
              <h3>Gateway resilience</h3>
              <div className="tier-sub">
                Keeps the model calls themselves alive.
              </div>

              <div className="feat">
                <div className="feat-ico">
                  <IcoFallback />
                </div>
                <div className="feat-body">
                  <div className="ft">Model fallback</div>
                  <div className="fd">
                    Primary model down or rate-limited → automatically routes to
                    another provider, mid-conversation.
                  </div>
                </div>
              </div>
              <div className="feat">
                <div className="feat-ico">
                  <IcoShield />
                </div>
                <div className="feat-body">
                  <div className="ft">Guardrails</div>
                  <div className="fd">
                    Strips personal info before it reaches any model, and blocks
                    prompt-injection attempts.
                  </div>
                </div>
              </div>
              <div className="feat">
                <div className="feat-ico">
                  <IcoLock />
                </div>
                <div className="feat-body">
                  <div className="ft">Scoped tools</div>
                  <div className="fd">
                    The agent can only call read-only lookups — it physically
                    can&apos;t mutate data or reach identity fields.
                  </div>
                </div>
              </div>
            </div>

            {/* Tier 2 */}
            <div className="tier tier--two">
              <div className="tier-tag">
                Tier 2 <span className="badge">InsurIQ&apos;s own layer</span>
              </div>
              <h3>Orchestration resilience</h3>
              <div className="tier-sub">
                Keeps the agent&apos;s own state alive — the part the gateway
                can&apos;t see.
              </div>

              <div className="feat">
                <div className="feat-ico">
                  <IcoCheck />
                </div>
                <div className="feat-body">
                  <div className="ft">Grounding gate</div>
                  <div className="fd">
                    It refuses to state any fact it can&apos;t trace to a
                    verified clause in the actual policy.
                  </div>
                </div>
              </div>
              <div className="feat">
                <div className="feat-ico">
                  <IcoResume />
                </div>
                <div className="feat-body">
                  <div className="ft">Checkpoint resume</div>
                  <div className="fd">
                    If the process crashes mid-question, it resumes from the
                    last good step. No repeated work, no lost progress.
                  </div>
                </div>
              </div>

              <div className="feat">
                <div className="feat-ico">
                  <IcoWarning />
                </div>
                <div className="feat-body">
                  <div className="ft">Honest degradation</div>
                  <div className="fd">
                    When a lookup tool fails, the agent answers what it can
                    verify and openly flags what it couldn&apos;t — instead of
                    guessing.
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="tiers-kicker">
            <p className="q">
              &ldquo;The gateway makes model calls resilient. We make the
              agent&apos;s own state resilient.&rdquo;
            </p>
          </div>
        </div>
      </section>

      {/* ---- Honesty ---- */}
      <section className="honesty">
        <div className="wrap">
          <div className="eyebrow">What makes it different</div>
          <h2>It says so when it doesn&apos;t know.</h2>
          <p className="lead">
            Every answer is tied to a verbatim clause from your actual policy.
            When a fact can&apos;t be found or verified, InsurIQ <b>flags it</b>{" "}
            rather than filling the gap with what &lsquo;usually&rsquo; applies.
            Under failure, that honesty is exactly what keeps it trustworthy — a
            degraded answer you can trust beats a complete answer you
            can&apos;t.
          </p>
          <div className="proof-line">
            <span className="dot" />
            Every answer carries the <b>page number</b> and the{" "}
            <b>verbatim text</b> it came from.
          </div>
        </div>
      </section>

      {/* ---- Stack badges ---- */}
      <section className="stack">
        <div className="wrap">
          <div className="eyebrow">Built with</div>
          <div className="badge-row">
            <div className="stack-badge">
              <span className="sb-dot" style={{ background: "#FF9900" }} />
              AWS Bedrock
            </div>
            <div className="stack-badge">
              <span className="sb-dot" style={{ background: "#1788E5" }} />
              TrueFoundry AI Gateway
            </div>
            <div className="stack-badge">
              <span className="sb-dot" style={{ background: "#1788E5" }} />
              TrueFoundry MCP Gateway
            </div>
            <div className="stack-badge">
              <span className="sb-dot" style={{ background: "#36B37E" }} />
              LangGraph
            </div>
            <div className="stack-badge">
              <span className="sb-dot" style={{ background: "#DC2626" }} />
              Guardrails
            </div>
          </div>
        </div>
      </section>

      {/* ---- Final CTA ---- */}
      <section className="final">
        <div className="wrap">
          <h2>Watch it break — and keep working.</h2>
          <p className="lead">
            Open the demo and trigger the failures yourself: kill the model,
            fail a tool, crash the process. Then watch the agent recover —
            without ever making something up.
          </p>
          <Link className="btn btn-primary btn-lg" href="/demo">
            See it survive failure
            <ArrowRight />
          </Link>
        </div>
      </section>

      {/* ---- Footer ---- */}
      <footer className="footer">
        <div className="wrap">
          <a className="wordmark" href="#top">
            <span className="mark">I</span>InsurIQ
          </a>
          <div className="credit">
            <span>
              Built for the TrueFoundry Resilient Agents hackathon · 2026
            </span>
            <span className="mono">@himalayan_dev</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
