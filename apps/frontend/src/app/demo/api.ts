/* ============================================================
   PolicyDesk — API client for the /ask endpoint
   ============================================================ */

export const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8082"
).replace(/\/$/, "");

// ---- Request types ----

export interface ChaosPayload {
  break_model?: boolean;
  fail_tool?: boolean | string;
  fail_tool_once?: boolean;
  crash_after_tools?: boolean;
}

// ---- Response types (mirrors backend app.py) ----

export interface CitationInfo {
  cite_key: string;
  value?: string;
  cite_status?: string;
  clause?: string;
  page?: number;
  quote?: string;
  notes?: string;
}

export interface Claim {
  text: string;
  cite_key: string;
  value?: string;
  cite_status?: string;
  clause?: string;
  page?: number;
  quote?: string;
  notes?: string;
}

export interface GuardrailBlocked {
  stage: string;
  integrations: string[];
  action: string;
}

export interface GroundingInfo {
  action?: string;
  reason?: string;
  lede_cites?: string;
  lede_status?: string;
  kept_claim_cites?: string[];
  dropped?: Array<{ text: string; cites?: string }>;
}

export interface Receipt {
  thread_id: string;
  checkpoint_resumed: boolean;
  resolved_model?: string;
  guardrail_blocked?: GuardrailBlocked;
  tool_status?: string;
  tool_attempts?: Record<string, number>;
  grounding?: GroundingInfo;
  regenerate_count?: number;
  events?: string[];
  chaos_mode?: string;
}

export interface AskResponse {
  answer_text: string;
  lede?: string;
  lede_cite?: CitationInfo | null;
  claims: Claim[];
  receipt: Receipt;
  latency_ms: number;
}

// ---- Chaos mapping (matches reference app.js exactly) ----

export function chaosForMode(mode: string): ChaosPayload {
  if (mode === "fallback") return { break_model: true };            // Scene A
  if (mode === "degraded") return { fail_tool: "get_room_rent_rule" }; // Scene B (selective)
  return {};                                                         // clean / injection
}

// ---- API call ----

export async function askBackend(
  question: string,
  chaos: ChaosPayload,
): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, chaos }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
