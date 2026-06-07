"use client";

import { useRef, useEffect } from "react";
import type { LogLine } from "../constants";

interface EventLogProps {
  lines: LogLine[];
  // Absolute event times (epoch ms). Rendered as elapsed since queryStart.
  timestamps: number[];
  queryStart: number;
  onClear: () => void;
}

// Elapsed seconds since the current query started, e.g. "+0.0s", "+1.2s".
function fmtElapsed(ts: number | undefined, start: number): string {
  if (ts == null) return "";
  const d = Math.max(0, (ts - start) / 1000);
  return `+${d.toFixed(1)}s`;
}

export default function EventLog({ lines, timestamps, queryStart, onClear }: EventLogProps) {
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [lines.length]);

  return (
    <div className="rail-section" style={{ paddingTop: 8 }}>
      <div className="log-head">
        <span>Live event log</span>
        <span className="clear" onClick={onClear}>
          clear
        </span>
      </div>
      <div className="event-log" ref={logRef}>
        {lines.map((ln, i) => (
          <div key={i} className={`ln ${ln.kind}`}>
            <span className="t">{fmtElapsed(timestamps[i], queryStart)}</span>
            <span className="m">
              {ln.indent && <span className="indent">↳ </span>}
              {ln.text}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
