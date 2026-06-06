"use client";

import { POLICY } from "../constants";

interface TopBarProps {
  statusMode: "healthy" | "degraded" | "recovering";
}

const statusLabels: Record<string, string> = {
  healthy: "Healthy",
  degraded: "Degraded",
  recovering: "Recovering",
};

export default function TopBar({ statusMode }: TopBarProps) {
  return (
    <header className="topbar">
      <div className="wordmark">
        <span className="mark">P</span>
        <span>{POLICY.wordmark}</span>
      </div>
      <nav className="breadcrumb">
        <span className="doc">{POLICY.insurer}</span>
        <span className="sep">·</span>
        <span>{POLICY.tier}</span>
        <span className="sep">·</span>
        <span>{POLICY.sumInsured}</span>
        <span className="sep">·</span>
        <span>{POLICY.members}</span>
      </nav>
      <div className="topbar-right">
        <div className="status-pill" data-status={statusMode}>
          <span className="dot" />
          <span className="label">{statusLabels[statusMode]}</span>
        </div>
      </div>
    </header>
  );
}
