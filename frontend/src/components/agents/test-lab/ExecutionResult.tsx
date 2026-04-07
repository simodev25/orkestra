"use client";

import { useState } from "react";
import { CheckCircle2, XCircle, Clock, Cpu, FileText } from "lucide-react";
import type { AgentTestRunResult } from "@/lib/agent-test-lab/types";

interface ExecutionResultProps {
  result: AgentTestRunResult | null;
  running: boolean;
}

type ResultTab = "rendered" | "raw" | "parsed" | "checks" | "diff";

const TABS: { key: ResultTab; label: string }[] = [
  { key: "rendered", label: "Rendered" },
  { key: "raw", label: "Raw" },
  { key: "parsed", label: "Parsed" },
  { key: "checks", label: "Checks" },
  { key: "diff", label: "Diff" },
];

export function ExecutionResult({ result, running }: ExecutionResultProps) {
  const [activeTab, setActiveTab] = useState<ResultTab>("rendered");

  if (running) {
    return (
      <div className="glass-panel p-8 flex flex-col items-center justify-center gap-3">
        <div className="w-6 h-6 border-2 border-ork-cyan border-t-transparent rounded-full animate-spin" />
        <p className="text-xs font-mono text-ork-cyan">Executing test run...</p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="glass-panel p-8 text-center">
        <FileText size={24} className="mx-auto text-ork-dim mb-2" />
        <p className="text-xs font-mono text-ork-dim">
          No results yet. Configure a test case and run it.
        </p>
      </div>
    );
  }

  const passedChecks = result.behavioralChecks.filter((c) => c.actual === "pass").length;
  const totalChecks = result.behavioralChecks.length;

  return (
    <div className="space-y-4">
      <h3 className="section-title">Execution result</h3>

      {/* Summary bar */}
      <div className="glass-panel p-4">
        <div className="flex items-center gap-4 flex-wrap">
          {/* Verdict */}
          <div className="flex items-center gap-1.5">
            {result.verdict === "pass" ? (
              <CheckCircle2 size={16} className="text-ork-green" />
            ) : (
              <XCircle size={16} className="text-ork-red" />
            )}
            <span
              className={`text-xs font-mono font-semibold uppercase ${
                result.verdict === "pass" ? "text-ork-green" : "text-ork-red"
              }`}
            >
              {result.verdict}
            </span>
          </div>

          <span className="w-px h-4 bg-ork-border" />

          {/* Latency */}
          <div className="flex items-center gap-1.5 text-xs text-ork-muted">
            <Clock size={12} />
            <span className="font-mono">{result.latencyMs}ms</span>
          </div>

          {/* Tokens */}
          {result.tokenUsage && (
            <>
              <span className="w-px h-4 bg-ork-border" />
              <div className="flex items-center gap-1.5 text-xs text-ork-muted">
                <Cpu size={12} />
                <span className="font-mono">
                  {result.tokenUsage.input}↑ {result.tokenUsage.output}↓
                </span>
              </div>
            </>
          )}

          <span className="w-px h-4 bg-ork-border" />

          {/* Checks score */}
          <span className="text-xs font-mono text-ork-muted">
            Checks:{" "}
            <span
              className={
                passedChecks === totalChecks ? "text-ork-green" : "text-ork-amber"
              }
            >
              {passedChecks}/{totalChecks}
            </span>
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-ork-border flex">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-[11px] font-mono uppercase tracking-wider transition-colors border-b-2 -mb-px ${
              activeTab === tab.key
                ? "text-ork-cyan border-ork-cyan"
                : "text-ork-muted border-transparent hover:text-ork-text"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="glass-panel p-4">
        {activeTab === "rendered" && (
          <div className="text-xs text-ork-text whitespace-pre-wrap font-mono leading-relaxed">
            {result.parsedOutput
              ? formatRendered(result.parsedOutput)
              : result.rawOutput}
          </div>
        )}

        {activeTab === "raw" && (
          <pre className="text-xs font-mono text-ork-muted whitespace-pre-wrap bg-ork-bg border border-ork-border rounded p-3 overflow-x-auto">
            {result.rawOutput}
          </pre>
        )}

        {activeTab === "parsed" && (
          <pre className="text-xs font-mono text-ork-text whitespace-pre-wrap bg-ork-bg border border-ork-border rounded p-3 overflow-x-auto">
            {result.parsedOutput
              ? JSON.stringify(result.parsedOutput, null, 2)
              : "No parsed output available"}
          </pre>
        )}

        {activeTab === "checks" && (
          <div className="space-y-2">
            {result.behavioralChecks.length === 0 && (
              <p className="text-xs text-ork-dim font-mono">No checks evaluated.</p>
            )}
            {result.behavioralChecks.map((check) => (
              <div
                key={check.key}
                className={`flex items-start gap-2.5 p-2.5 rounded border ${
                  check.actual === "pass"
                    ? "border-ork-green/20 bg-ork-green/5"
                    : "border-ork-red/20 bg-ork-red/5"
                }`}
              >
                {check.actual === "pass" ? (
                  <CheckCircle2 size={14} className="text-ork-green mt-0.5 shrink-0" />
                ) : (
                  <XCircle size={14} className="text-ork-red mt-0.5 shrink-0" />
                )}
                <div>
                  <span className="text-xs font-mono text-ork-text">{check.label}</span>
                  {check.details && (
                    <p className="text-[10px] text-ork-dim mt-0.5">{check.details}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === "diff" && (
          <p className="text-xs text-ork-dim font-mono">
            Baseline comparison will be available when regression data is collected.
          </p>
        )}
      </div>
    </div>
  );
}

function formatRendered(parsed: Record<string, unknown>): string {
  const lines: string[] = [];
  for (const [key, val] of Object.entries(parsed)) {
    if (Array.isArray(val)) {
      lines.push(`${key}:`);
      val.forEach((item, i) => lines.push(`  ${i + 1}. ${String(item)}`));
    } else {
      lines.push(`${key}: ${String(val)}`);
    }
  }
  return lines.join("\n");
}
