"use client";

import { FormEvent, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8082";
const SUMMARY_ENDPOINT = `${API_BASE_URL.replace(/\/$/, "")}/api/generate_summary`;

interface SummarySuccessPayload {
  summary?: string;
  data?: {
    policy_summary?: {
      policy_summary?: string;
    };
  };
}

function extractSummary(payload: unknown): string | null {
  if (typeof payload !== "object" || payload === null) {
    return null;
  }

  const topLevelSummary = (payload as Record<string, unknown>).summary;
  if (
    typeof topLevelSummary === "string" &&
    topLevelSummary.trim().length > 0
  ) {
    return topLevelSummary;
  }

  const nestedSummary = (payload as SummarySuccessPayload).data?.policy_summary
    ?.policy_summary;
  if (typeof nestedSummary === "string" && nestedSummary.trim().length > 0) {
    return nestedSummary;
  }

  return null;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return "Something went wrong while generating the summary. Please try again.";
}

export default function Home() {
  const [policyName, setPolicyName] = useState<string>("");
  const [summary, setSummary] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string>("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const trimmedPolicyName = policyName.trim();
    if (!trimmedPolicyName) {
      setErrorMessage("Please enter a policy name.");
      setSummary("");
      return;
    }

    setIsLoading(true);
    setErrorMessage("");

    try {
      const response = await fetch(SUMMARY_ENDPOINT, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ policy_name: trimmedPolicyName }),
      });

      if (!response.ok) {
        const responseText = await response.text();
        throw new Error(
          responseText ||
            `Request failed with status ${response.status}. Please try again.`,
        );
      }

      const payload = (await response.json()) as SummarySuccessPayload;
      const parsedSummary = extractSummary(payload);

      if (!parsedSummary) {
        throw new Error("The API response did not include a valid summary.");
      }

      setSummary(parsedSummary);
    } catch (error: unknown) {
      setSummary("");
      setErrorMessage(getErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12 sm:px-6">
      <section className="w-full max-w-2xl rounded-3xl border border-(--card-border) bg-(--card-bg) p-6 shadow-[0_16px_60px_-32px_rgba(33,69,96,0.55)] backdrop-blur-sm sm:p-10">
        <header className="mb-8 space-y-2 text-center sm:text-left">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-(--muted-text)">
            Agentic Care
          </p>
          <h1 className="text-2xl font-semibold tracking-tight text-(--headline) sm:text-3xl">
            Health Insurance Policy Summarizer
          </h1>
          <p className="text-sm text-(--muted-text) sm:text-base">
            Enter a policy name to generate a clear, easy-to-read summary.
          </p>
        </header>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label
              htmlFor="policy-name"
              className="block text-sm font-medium text-(--headline)"
            >
              Policy Name
            </label>
            <input
              id="policy-name"
              name="policyName"
              type="text"
              value={policyName}
              onChange={(event) => setPolicyName(event.target.value)}
              placeholder="e.g., Bajaj Health Insurance"
              autoComplete="off"
              className="w-full rounded-xl border border-(--input-border) bg-(--input-bg) px-4 py-3 text-[15px] text-(--headline) outline-none transition duration-200 placeholder:text-(--placeholder) focus:border-(--accent) focus:ring-3 focus:ring-(--accent-soft)"
              aria-describedby={errorMessage ? "request-error" : undefined}
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="inline-flex w-full items-center justify-center rounded-xl bg-(--accent) px-5 py-3 text-sm font-semibold text-white transition duration-200 hover:bg-(--accent-hover) focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-(--accent-soft) disabled:cursor-not-allowed disabled:opacity-70"
          >
            {isLoading ? "Generating Summary..." : "Generate Summary"}
          </button>
        </form>

        {errorMessage ? (
          <p
            id="request-error"
            role="alert"
            className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {errorMessage}
          </p>
        ) : null}

        {summary ? (
          <section className="mt-8 rounded-2xl border border-(--result-border) bg-(--result-bg) p-5">
            <h2 className="mb-3 text-lg font-semibold text-(--headline)">
              Generated Summary
            </h2>
            <p className="whitespace-pre-wrap text-[15px] leading-7 text-(--body-text)">
              {summary}
            </p>
          </section>
        ) : null}
      </section>
    </main>
  );
}
