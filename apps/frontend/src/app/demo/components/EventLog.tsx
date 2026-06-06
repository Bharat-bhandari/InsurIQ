"use client";

import { useRef, useEffect } from "react";
import type { LogLine } from "../constants";

interface EventLogProps {
  lines: LogLine[];
  timestamps: string[];
  onClear: () => void;
}

export default function EventLog({ lines, timestamps, onClear }: EventLogProps) {
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
            <span className="t">{timestamps[i] ?? ""}</span>
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
