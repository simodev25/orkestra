"use client";

import { AlertTriangle, XOctagon, Archive, ArrowDown } from "lucide-react";
import type { AgentStatus } from "@/lib/agent-lifecycle/types";

interface OperationalStatesProps {
  currentStatus: AgentStatus;
  onTransition?: (to: AgentStatus) => void;
  transitioning?: boolean;
}

const STYLE_MAP = {
  deprecated: {
    active: "bg-ork-amber/10 border-ork-amber/30 text-ork-amber",
    btn: "bg-ork-amber/10 border-ork-amber/20 text-ork-amber hover:bg-ork-amber/20",
  },
  disabled: {
    active: "bg-ork-red/10 border-ork-red/30 text-ork-red",
    btn: "bg-ork-red/10 border-ork-red/20 text-ork-red hover:bg-ork-red/20",
  },
  archived: {
    active: "bg-ork-dim/15 border-ork-dim/30 text-ork-muted",
    btn: "bg-ork-dim/10 border-ork-dim/20 text-ork-muted hover:bg-ork-dim/20",
  },
} as const;

const OPS_STATES = [
  {
    status: "deprecated" as const,
    label: "Deprecated",
    description: "Agent is phased out, no new assignments",
    icon: AlertTriangle,
  },
  {
    status: "disabled" as const,
    label: "Disabled",
    description: "Agent is temporarily disabled",
    icon: XOctagon,
  },
  {
    status: "archived" as const,
    label: "Archived",
    description: "Agent permanently removed from active pool",
    icon: Archive,
  },
];

export function OperationalStates({
  currentStatus,
  onTransition,
  transitioning,
}: OperationalStatesProps) {
  const isActive = currentStatus === "active";
  const isDeprecated = currentStatus === "deprecated";
  const isDisabled = currentStatus === "disabled";
  const isArchived = currentStatus === "archived";

  function canReach(target: string): boolean {
    if (target === "deprecated") return isActive;
    if (target === "disabled") return isActive;
    if (target === "archived") return isDeprecated || isDisabled;
    return false;
  }

  function isCurrent(target: string): boolean {
    return currentStatus === target;
  }

  return (
    <div className="glass-panel p-5">
      <h3 className="section-title mb-1">Operational / terminal states</h3>
      <p className="text-[11px] text-ork-dim mb-4">
        Transitions from <span className="text-ork-green">Active</span> to end-of-life states.
      </p>

      <div className="flex items-start gap-3">
        {/* Left column: deprecated + disabled */}
        <div className="flex-1 space-y-2">
          {OPS_STATES.filter((s) => s.status !== "archived").map((s) => {
            const Icon = s.icon;
            const active = isCurrent(s.status);
            const reachable = canReach(s.status);
            const styles = STYLE_MAP[s.status];

            return (
              <div
                key={s.status}
                className={`p-3 rounded border text-xs font-mono transition-colors ${
                  active ? styles.active : "bg-ork-bg border-ork-border text-ork-muted"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Icon size={14} />
                    <span className="uppercase tracking-wider">{s.label}</span>
                  </div>
                  {reachable && onTransition && (
                    <button
                      disabled={transitioning}
                      onClick={() => onTransition(s.status)}
                      className={`px-2 py-0.5 rounded text-[10px] border transition-colors ${styles.btn}`}
                    >
                      Move here
                    </button>
                  )}
                </div>
                <p className="text-[10px] text-ork-dim mt-1">{s.description}</p>
              </div>
            );
          })}
        </div>

        {/* Arrow to archived */}
        <div className="flex flex-col items-center justify-center pt-6">
          <ArrowDown size={16} className="text-ork-dim" />
        </div>

        {/* Archived */}
        <div className="flex-1">
          {(() => {
            const s = OPS_STATES.find((x) => x.status === "archived")!;
            const Icon = s.icon;
            const active = isArchived;
            const reachable = canReach("archived");
            const styles = STYLE_MAP.archived;

            return (
              <div
                className={`p-3 rounded border text-xs font-mono transition-colors ${
                  active ? styles.active : "bg-ork-bg border-ork-border text-ork-muted"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Icon size={14} />
                    <span className="uppercase tracking-wider">{s.label}</span>
                  </div>
                  {reachable && onTransition && (
                    <button
                      disabled={transitioning}
                      onClick={() => onTransition("archived")}
                      className={`px-2 py-0.5 rounded text-[10px] border transition-colors ${styles.btn}`}
                    >
                      Move here
                    </button>
                  )}
                </div>
                <p className="text-[10px] text-ork-dim mt-1">{s.description}</p>
                <p className="text-[10px] text-ork-dim mt-2 italic">
                  Reachable from Deprecated or Disabled
                </p>
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );
}
