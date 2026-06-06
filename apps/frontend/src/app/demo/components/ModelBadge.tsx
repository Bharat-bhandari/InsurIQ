"use client";

interface ModelBadgeProps {
  model: {
    kind: "primary" | "failover";
    resolved: string;
    down?: string;
  };
}

export default function ModelBadge({ model }: ModelBadgeProps) {
  if (model.kind === "failover") {
    return (
      <span className="model-badge">
        <span className="chain">
          <span className="down">
            primary{model.down ? ` ${model.down}` : ""} unavailable
          </span>
          <span className="arrow">↳</span>
          <span className="ok">✓</span>
          <span className="resolved">{model.resolved}</span>
        </span>{" "}
        <span className="failover-tag">failover</span>
      </span>
    );
  }
  return (
    <span className="model-badge">
      <span className="ok">✓</span>
      {model.resolved} (primary)
    </span>
  );
}
