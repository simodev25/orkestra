"use client";

import { AlertTriangle, XOctagon, Archive, ArrowDown } from "lucide-react";
import type { AgentStatus } from "@/lib/agent-lifecycle/types";
import { StatusBadge } from "@/components/ui/status-badge";

interface OperationalStatesProps {
  currentStatus: AgentStatus;
  onTransition?: (to: AgentStatus) => void;
  transitioning?: boolean;
}

const BLOCKER_VARIANT: Record<string, "blocker--error" | "blocker--warning" | "blocker--ok"> = {
  deprecated: "blocker--warning",
  disabled:   "blocker--error",
  archived:   "blocker--ok",
};

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
    <div className="glass-panel" style={{ padding: "14px 16px" }}>
      <h3 className="section-title" style={{ marginBottom: 4 }}>Operational / terminal states</h3>
      <p className="text-[11px] text-ork-dim" style={{ marginBottom: 12 }}>
        Transitions from <span className="text-ork-green">Active</span> to end-of-life states.
      </p>

      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        {/* Left column: deprecated + disabled */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
          {OPS_STATES.filter((s) => s.status !== "archived").map((s) => {
            const Icon = s.icon;
            const active = isCurrent(s.status);
            const reachable = canReach(s.status);
            const variant = BLOCKER_VARIANT[s.status];

            return (
              <div
                key={s.status}
                className={`blocker ${active ? variant : ""}`}
                style={{ flexDirection: "column", alignItems: "stretch", gap: 4, padding: "8px 10px" }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <Icon size={13} />
                    <StatusBadge status={s.status} />
                  </div>
                  {reachable && onTransition && (
                    <button
                      type="button"
                      disabled={transitioning}
                      onClick={() => onTransition(s.status)}
                      className="btn"
                    >
                      Move here
                    </button>
                  )}
                </div>
                <p className="text-[10px] text-ork-dim">{s.description}</p>
              </div>
            );
          })}
        </div>

        {/* Arrow to archived */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", paddingTop: 20 }}>
          <ArrowDown size={16} className="text-ork-dim" />
        </div>

        {/* Archived */}
        <div style={{ flex: 1 }}>
          {(() => {
            const s = OPS_STATES.find((x) => x.status === "archived")!;
            const Icon = s.icon;
            const active = isArchived;
            const reachable = canReach("archived");
            const variant = BLOCKER_VARIANT.archived;

            return (
              <div
                className={`blocker ${active ? variant : ""}`}
                style={{ flexDirection: "column", alignItems: "stretch", gap: 4, padding: "8px 10px" }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <Icon size={13} />
                    <StatusBadge status={s.status} />
                  </div>
                  {reachable && onTransition && (
                    <button
                      type="button"
                      disabled={transitioning}
                      onClick={() => onTransition("archived")}
                      className="btn"
                    >
                      Move here
                    </button>
                  )}
                </div>
                <p className="text-[10px] text-ork-dim">{s.description}</p>
                <p className="text-[10px] text-ork-dim" style={{ fontStyle: "italic" }}>
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
