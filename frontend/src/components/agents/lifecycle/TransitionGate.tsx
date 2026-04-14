"use client";

import Link from "next/link";
import { AlertTriangle, XCircle, ArrowRight, CheckCircle2, ShieldAlert, FlaskConical, Plus } from "lucide-react";
import type { TransitionInfo } from "@/lib/agent-lifecycle/types";
import { getStatusLabel } from "@/lib/agent-lifecycle/helpers";

interface TransitionGateProps {
  transition: TransitionInfo | null;
  currentStatus: string;
  agentId?: string;
  onPromote?: (to: string) => void;
  promoting?: boolean;
}

export function TransitionGate({
  transition,
  currentStatus,
  agentId,
  onPromote,
  promoting,
}: TransitionGateProps) {
  if (!transition) {
    const isActive = currentStatus === "active";
    return (
      <div className="glass-panel p-5">
        <h3 className="section-title mb-3">Current transition gate</h3>
        <div className="flex items-center gap-2 text-sm text-ork-muted">
          <CheckCircle2 size={16} className="text-ork-green" />
          <span>
            {isActive
              ? "Agent is active. No further promotion available."
              : "No promotion transition available from this state."}
          </span>
        </div>
      </div>
    );
  }

  const errors = transition.blockers.filter((b) => b.severity === "error");
  const warnings = transition.blockers.filter((b) => b.severity === "warning");

  return (
    <div className="glass-panel p-5">
      <h3 className="section-title mb-4">Current transition gate</h3>

      {/* From → To */}
      <div className="flex items-center gap-3 mb-4">
        <span className="px-2.5 py-1 text-xs font-mono uppercase tracking-wider rounded bg-ork-cyan/10 text-ork-cyan border border-ork-cyan/20">
          {getStatusLabel(transition.from as any)}
        </span>
        <ArrowRight size={16} className="text-ork-dim" />
        <span className="px-2.5 py-1 text-xs font-mono uppercase tracking-wider rounded bg-ork-purple/10 text-ork-purple border border-ork-purple/20">
          {getStatusLabel(transition.to as any)}
        </span>
      </div>

      {/* Gate info */}
      <div className="mb-4 p-3 rounded bg-ork-bg border border-ork-border">
        <div className="flex items-center gap-2 mb-1">
          <ShieldAlert size={14} className="text-ork-amber" />
          <span className="text-xs font-mono font-semibold text-ork-text">
            {transition.gate.title}
          </span>
        </div>
        <p className="text-xs text-ork-muted ml-5">{transition.gate.description}</p>
      </div>

      {/* Blockers */}
      {transition.blockers.length > 0 && (
        <div className="space-y-1.5 mb-4">
          {errors.map((b) => (
            <div key={b.key} className="flex items-start gap-2 text-xs">
              <XCircle size={14} className="text-ork-red mt-0.5 shrink-0" />
              <span className="text-ork-red">{b.label}</span>
            </div>
          ))}
          {warnings.map((b) => (
            <div key={b.key} className="flex items-start gap-2 text-xs">
              <AlertTriangle size={14} className="text-ork-amber mt-0.5 shrink-0" />
              <span className="text-ork-amber">{b.label}</span>
            </div>
          ))}
        </div>
      )}

      {transition.blockers.length === 0 && (
        <div className="flex items-center gap-2 text-xs text-ork-green mb-4">
          <CheckCircle2 size={14} />
          <span>All gate conditions met</span>
        </div>
      )}

      {/* Test Lab actions (when gate is designed → tested) */}
      {transition.from === "designed" && transition.to === "tested" && agentId && (
        <div className="flex items-center gap-2 mb-4">
          <Link
            href={`/test-lab/scenarios/new?agent_id=${agentId}`}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider bg-ork-purple/15 text-ork-purple border border-ork-purple/30 rounded hover:bg-ork-purple/25 transition-colors"
          >
            <Plus size={11} />
            Create Test Scenario
          </Link>
          <Link
            href="/test-lab"
            className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider bg-ork-cyan/10 text-ork-cyan border border-ork-cyan/30 rounded hover:bg-ork-cyan/20 transition-colors"
          >
            <FlaskConical size={11} />
            Open Test Lab
          </Link>
        </div>
      )}

      {/* Promote button */}
      {onPromote && (
        <button
          type="button"
          disabled={!transition.eligible || promoting}
          onClick={() => onPromote(transition.to)}
          className={`w-full py-2 text-xs font-mono uppercase tracking-wider rounded border transition-colors ${
            transition.eligible
              ? "bg-ork-cyan/10 text-ork-cyan border-ork-cyan/30 hover:bg-ork-cyan/20"
              : "bg-ork-border/30 text-ork-dim border-ork-border cursor-not-allowed"
          }`}
        >
          {promoting
            ? "Promoting..."
            : transition.eligible
              ? `Promote to ${getStatusLabel(transition.to as any)}`
              : "Blocked — resolve errors first"}
        </button>
      )}
    </div>
  );
}
