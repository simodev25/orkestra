"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

const USE_CASES = [
  { value: "credit_review", label: "Credit Review" },
  { value: "due_diligence", label: "Due Diligence" },
  { value: "tender_review", label: "Tender Review" },
  { value: "general", label: "General" },
] as const;

const CRITICALITIES = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
] as const;

export default function NewRequestPage() {
  const [title, setTitle] = useState("");
  const [requestText, setRequestText] = useState("");
  const [useCase, setUseCase] = useState("general");
  const [criticality, setCriticality] = useState("medium");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !requestText.trim()) return;

    setSubmitting(true);
    setError(null);

    try {
      const created = await api.createRequest({
        title: title.trim(),
        request_text: requestText.trim(),
        use_case: useCase,
        criticality,
      });
      await api.submitRequest(created.id);
      await api.convertToCase(created.id);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || "Failed to create request");
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <div className="space-y-6">
        <div className="glass-panel p-8 text-center glow-cyan max-w-lg mx-auto">
          <div className="w-14 h-14 rounded-full border-2 border-ork-green/40 mx-auto flex items-center justify-center mb-4">
            <svg className="w-7 h-7 text-ork-green" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="section-title text-sm mb-2">REQUEST SUBMITTED</h2>
          <p className="text-sm text-ork-muted mb-6">
            Your request has been created and submitted for processing.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link
              href="/cases"
              className="px-4 py-2 bg-ork-cyan/10 border border-ork-cyan/30 rounded-lg text-ork-cyan text-xs font-mono uppercase tracking-wider hover:bg-ork-cyan/20 transition-colors"
            >
              View Cases
            </Link>
            <button
              onClick={() => {
                setTitle("");
                setRequestText("");
                setUseCase("general");
                setCriticality("medium");
                setSuccess(false);
              }}
              className="px-4 py-2 bg-ork-bg border border-ork-border rounded-lg text-ork-muted text-xs font-mono uppercase tracking-wider hover:border-ork-dim transition-colors"
            >
              New Request
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="section-title text-sm mb-1">NEW REQUEST</h1>
          <p className="text-ork-dim text-xs font-mono">
            Compose an orchestration request
          </p>
        </div>
        <Link
          href="/requests"
          className="text-xs font-mono text-ork-dim hover:text-ork-muted transition-colors"
        >
          &larr; BACK TO REQUESTS
        </Link>
      </div>

      {/* Error */}
      {error && (
        <div className="glass-panel p-3 border-ork-red/30">
          <p className="text-xs font-mono text-ork-red">{error}</p>
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Title */}
        <div className="space-y-2">
          <label className="data-label" htmlFor="req-title">
            TITLE
          </label>
          <input
            id="req-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Describe your request..."
            required
            className="w-full bg-ork-bg border border-ork-border rounded-lg px-4 py-3 text-sm text-ork-text placeholder:text-ork-dim/50 font-sans focus:outline-none focus:border-ork-cyan/40 focus:ring-1 focus:ring-ork-cyan/20 transition-colors"
          />
        </div>

        {/* Request Text */}
        <div className="space-y-2">
          <label className="data-label" htmlFor="req-text">
            REQUEST TEXT
          </label>
          <textarea
            id="req-text"
            value={requestText}
            onChange={(e) => setRequestText(e.target.value)}
            placeholder="Provide detailed context for the orchestration task. Include objectives, constraints, relevant data sources, expected outcomes..."
            required
            rows={10}
            className="w-full bg-ork-bg border border-ork-border rounded-lg px-4 py-3 text-sm text-ork-text placeholder:text-ork-dim/50 font-sans focus:outline-none focus:border-ork-cyan/40 focus:ring-1 focus:ring-ork-cyan/20 transition-colors resize-y"
          />
        </div>

        {/* Use Case + Criticality row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Use Case */}
          <div className="space-y-2">
            <label className="data-label" htmlFor="req-use-case">
              USE CASE
            </label>
            <select
              id="req-use-case"
              value={useCase}
              onChange={(e) => setUseCase(e.target.value)}
              className="w-full bg-ork-bg border border-ork-border rounded-lg px-4 py-3 text-sm text-ork-text font-mono focus:outline-none focus:border-ork-cyan/40 focus:ring-1 focus:ring-ork-cyan/20 transition-colors appearance-none"
            >
              {USE_CASES.map((uc) => (
                <option key={uc.value} value={uc.value}>
                  {uc.label}
                </option>
              ))}
            </select>
          </div>

          {/* Criticality */}
          <div className="space-y-2">
            <label className="data-label" htmlFor="req-crit">
              CRITICALITY
            </label>
            <select
              id="req-crit"
              value={criticality}
              onChange={(e) => setCriticality(e.target.value)}
              className="w-full bg-ork-bg border border-ork-border rounded-lg px-4 py-3 text-sm text-ork-text font-mono focus:outline-none focus:border-ork-cyan/40 focus:ring-1 focus:ring-ork-cyan/20 transition-colors appearance-none"
            >
              {CRITICALITIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Submit */}
        <div className="pt-2">
          <button
            type="submit"
            disabled={submitting || !title.trim() || !requestText.trim()}
            className="w-full sm:w-auto px-8 py-3 bg-ork-cyan/15 border border-ork-cyan/30 rounded-lg text-ork-cyan text-xs font-mono uppercase tracking-wider hover:bg-ork-cyan/25 hover:border-ork-cyan/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200"
          >
            {submitting ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-3 h-3 border border-ork-cyan/40 border-t-ork-cyan rounded-full animate-spin" />
                SUBMITTING...
              </span>
            ) : (
              "CREATE & SUBMIT REQUEST"
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
