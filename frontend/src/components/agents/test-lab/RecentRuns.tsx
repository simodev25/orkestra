"use client";

import { CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import type { AgentTestRunResult } from "@/lib/agent-test-lab/types";

interface RecentRunsProps {
  runs: AgentTestRunResult[];
}

export function RecentRuns({ runs }: RecentRunsProps) {
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
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => {
              const passed = run.behavioralChecks.filter(
                (c) => c.actual === "pass",
              ).length;
              const total = run.behavioralChecks.length;
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
                      {run.verdict === "pass" && (
                        <CheckCircle2 size={12} className="text-ork-green" />
                      )}
                      {run.verdict === "fail" && (
                        <XCircle size={12} className="text-ork-red" />
                      )}
                      {run.verdict === "error" && (
                        <AlertTriangle size={12} className="text-ork-amber" />
                      )}
                      <span
                        className={
                          run.verdict === "pass"
                            ? "text-ork-green"
                            : run.verdict === "fail"
                              ? "text-ork-red"
                              : "text-ork-amber"
                        }
                      >
                        {run.verdict}
                      </span>
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right text-ork-muted">
                    {run.latencyMs}ms
                  </td>
                  <td className="px-3 py-2 text-right">
                    <span
                      className={
                        passed === total ? "text-ork-green" : "text-ork-amber"
                      }
                    >
                      {passed}/{total}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
