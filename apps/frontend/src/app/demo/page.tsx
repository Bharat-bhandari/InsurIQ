import type { Metadata } from "next";
import PolicyDesk from "./PolicyDesk";

export const metadata: Metadata = {
  title: "PolicyDesk — Resilient policy Q&A",
  description:
    "Ask a real question about your health insurance policy, get a cited answer — and watch it keep answering correctly when the model, a tool, or the process fails.",
};

export default function DemoPage() {
  return <PolicyDesk />;
}
