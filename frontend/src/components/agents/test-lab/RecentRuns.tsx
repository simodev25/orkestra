"use client";

import { useState } from "react";
import { CheckCircle2, XCircle, AlertTriangle, Eye } from "lucide-react";
import type { AgentTestRunResult } from "@/lib/agent-test-lab/types";
import { TestRunDetail } from "./TestRunDetail";

interface RecentRunsProps {
  runs: AgentTestRunResult[];
}

export function RecentRuns({ runs }: RecentRunsProps) {
  const [selectedRun, setSelectedRun] = useState<AgentTestRunResult | null>(null);

  if (runs.length === 0) {
    return (
      <div className="space-y-3">
        <h3 className="section-title">Recent runs</h3>
        <div className="glass-panel p-4 text-center">
          <p className="text-xs font-mono text-ork-dim">No test runs recorded yet.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="section-title">Recent runs</h3>

      <div className="glass-panel overflow-hidden">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-ork-border text-ork-dim">
              <th className="text-left px-3 py-2 font-normal">Date</th>
              <th className="text-left px-3 py-2 font-normal">Version</th>
              <th className="text-left px-3 py-2 font-normal">Verdict</th>
              <th className="text-right px-3 py-2 font-normal">Latency</th>
              <th className="text-right px-3 py-2 font-normal">Checks</th>
              <th className="text-center px-3 py-2 font-normal">Detail</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => {
              const checks = run.behavioralChecks || [];
              const passed = checks.filter((c) => c.actual === "pass").length;
              const total = checks.length;
              return (
                <tr
                  key={run.id}
                  className="border-b border-ork-border/50 hover:bg-ork-hover/50 transition-colors"
                >
                  <td className="px-3 py-2 text-ork-muted">
                    {new Date(run.timestamp).toLocaleString("en-US", {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td className="px-3 py-2 text-ork-text">{run.agentVersion}</td>
                  <td className="px-3 py-2">
                    <span className="flex items-center gap-1">
                      {run.verdict === "pass" && <CheckCircle2 size={12} className="text-ork-green" />}
                      {run.verdict === "fail" && <XCircle size={12} className="text-ork-red" />}
                      {run.verdict === "error" && <AlertTriangle size={12} className="text-ork-amber" />}
                      <span className={
                        run.verdict === "pass" ? "text-ork-green"
                          : run.verdict === "fail" ? "text-ork-red"
                            : "text-ork-amber"
                      }>
                        {run.verdict}
                      </span>
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right text-ork-muted">
                    {run.latencyMs}ms
                  </td>
                  <td className="px-3 py-2 text-right">
                    <span className={passed === total && total > 0 ? "text-ork-green" : "text-ork-amber"}>
                      {passed}/{total}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-center">
                    <button
                      onClick={() => setSelectedRun(run)}
                      className="p-1 rounded border border-ork-border text-ork-muted hover:text-ork-cyan hover:border-ork-cyan/30 transition-colors"
                      title="View full detail"
                    >
                      <Eye size={13} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {selectedRun && (
        <TestRunDetail run={selectedRun} onClose={() => setSelectedRun(null)} />
      )}
    </div>
  );
}
