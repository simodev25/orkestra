"use client";

import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldCheck,
} from "lucide-react";
import { StatusBadge } from "@/components/ui/status-badge";
import type { AgentTestRunResult } from "@/lib/agent-test-lab/types";
import type { LifecycleBlocker } from "@/lib/agent-lifecycle/types";

interface QualificationGateProps {
  currentStatus: string;
  runs: AgentTestRunResult[];
  onPromote: () => void;
  promoting: boolean;
}

export function QualificationGate({
  currentStatus,
  runs,
  onPromote,
  promoting,
}: QualificationGateProps) {
  const qualifiedRuns = runs.filter(
    (r) => r.status === "completed" && r.verdict === "pass",
  );
  const isDesigned = currentStatus === "designed";

  // Compute blockers
  const blockers: LifecycleBlocker[] = [];

  if (runs.length === 0) {
    blockers.push({
      key: "no_runs",
      label: "No test runs available",
      severity: "error",
    });
  } else if (qualifiedRuns.length === 0) {
    blockers.push({
      key: "no_qualified_runs",
      label: "No qualified (passing) runs",
      severity: "error",
    });
  }

  // Check the latest run for specific failures
  const latestRun = runs[0];
  if (latestRun && latestRun.status === "completed") {
    const failedChecks = latestRun.behavioralChecks.filter(
      (c) => c.actual === "fail",
    );
    for (const fc of failedChecks) {
      blockers.push({
        key: `check_${fc.key}`,
        label: `${fc.label} — check failed`,
        severity: "error",
      });
    }
  }

  if (!isDesigned) {
    blockers.push({
      key: "wrong_status",
      label: `Agent must be in "designed" status to promote (current: ${currentStatus})`,
      severity: "error",
    });
  }

  const eligible = blockers.length === 0;

  return (
    <div className="space-y-3">
      <h3 className="section-title flex items-center gap-2">
        <ShieldCheck size={14} />
        Qualification gate
      </h3>

      <div className="glass-panel p-4 space-y-3">
        {/* Current lifecycle */}
        <div className="flex items-center justify-between">
          <span className="data-label">Current status</span>
          <StatusBadge status={currentStatus} />
        </div>

        <div className="flex items-center justify-between">
          <span className="data-label">Qualified runs</span>
          <span className="text-xs font-mono text-ork-text">
            {qualifiedRuns.length} / {runs.length}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="data-label">Eligibility</span>
          {eligible ? (
            <span className="flex items-center gap-1 text-xs font-mono text-ork-green">
              <CheckCircle2 size={12} /> Eligible
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs font-mono text-ork-red">
              <XCircle size={12} /> Blocked
            </span>
          )}
        </div>

        {/* Blockers list */}
        {blockers.length > 0 && (
          <div className="border-t border-ork-border pt-3 space-y-1.5">
            {blockers.map((b) => (
              <div key={b.key} className="flex items-start gap-2 text-xs">
                {b.severity === "error" ? (
                  <XCircle size={13} className="text-ork-red mt-0.5 shrink-0" />
                ) : (
                  <AlertTriangle
                    size={13}
                    className="text-ork-amber mt-0.5 shrink-0"
                  />
                )}
                <span
                  className={
                    b.severity === "error" ? "text-ork-red" : "text-ork-amber"
                  }
                >
                  {b.label}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Promote button */}
        <button
          disabled={!eligible || promoting}
          onClick={onPromote}
          className={`w-full py-2.5 text-xs font-mono uppercase tracking-wider rounded border transition-colors mt-2 ${
            eligible
              ? "bg-ork-green/10 text-ork-green border-ork-green/30 hover:bg-ork-green/20"
              : "bg-ork-border/30 text-ork-dim border-ork-border cursor-not-allowed"
          }`}
        >
          {promoting
            ? "Promoting..."
            : eligible
              ? "Promote to tested"
              : "Blocked — resolve issues first"}
        </button>
      </div>
    </div>
  );
}
