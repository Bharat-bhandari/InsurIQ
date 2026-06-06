"use client";

import { useState, useCallback } from "react";
import type { ClauseInfo } from "../constants";

interface CitationChipProps {
  id: string;
  clause: ClauseInfo;
}

export default function CitationChip({ id, clause }: CitationChipProps) {
  const [open, setOpen] = useState(false);
  const toggle = useCallback(() => setOpen((v) => !v), []);

  return (
    <>
      <button
        className="cite-chip"
        type="button"
        aria-expanded={open}
        onClick={toggle}
      >
        {clause.page}
        <span className="chev">▾</span>
      </button>
      <div className={`cite-panel${open ? " open" : ""}`} id={id}>
        <div className="layer">
          <span className="verified-tick">✓</span>
          {clause.layer}
        </div>
        <div className="quote">&ldquo;{clause.text}&rdquo;</div>
      </div>
    </>
  );
}
