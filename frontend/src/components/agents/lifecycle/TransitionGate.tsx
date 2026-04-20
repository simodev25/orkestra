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
      <div className="gate">
        <div className="gate__head">
          <h3 className="gate__title">Current transition gate</h3>
        </div>
        <div className="gate__blockers">
          <div className="blocker blocker--ok">
            <CheckCircle2 size={14} />
            <span>
              {isActive
                ? "Agent is active. No further promotion available."
                : "No promotion transition available from this state."}
            </span>
          </div>
        </div>
      </div>
    );
  }

  const errors = transition.blockers.filter((b) => b.severity === "error");
  const warnings = transition.blockers.filter((b) => b.severity === "warning");

  return (
    <div className="gate">
      <div className="gate__head">
        <h3 className="gate__title">Current transition gate</h3>
        <div className="gate__flow">
          <span>{getStatusLabel(transition.from as any)}</span>
          <ArrowRight size={12} />
          <span className="to">{getStatusLabel(transition.to as any)}</span>
        </div>
      </div>

      {/* Gate info */}
      <p className="gate__desc">
        <ShieldAlert size={13} style={{ display: "inline", marginRight: 4, verticalAlign: "middle" }} />
        <strong>{transition.gate.title}</strong>
        {" — "}
        {transition.gate.description}
      </p>

      {/* Blockers */}
      {transition.blockers.length > 0 && (
        <div className="gate__blockers">
          {errors.map((b) => (
            <div key={b.key} className="blocker blocker--error">
              <XCircle size={14} />
              <span>{b.label}</span>
            </div>
          ))}
          {warnings.map((b) => (
            <div key={b.key} className="blocker blocker--warning">
              <AlertTriangle size={14} />
              <span>{b.label}</span>
            </div>
          ))}
        </div>
      )}

      {transition.blockers.length === 0 && (
        <div className="gate__blockers">
          <div className="blocker blocker--ok">
            <CheckCircle2 size={14} />
            <span>All gate conditions met</span>
          </div>
        </div>
      )}

      {/* Test Lab actions (when gate is designed → tested) */}
      {transition.from === "designed" && transition.to === "tested" && agentId && (
        <div className="gate__foot" style={{ justifyContent: "flex-start" }}>
          <Link
            href={`/test-lab/scenarios/new?agent_id=${agentId}`}
            className="btn"
          >
            <Plus size={11} />
            Create Test Scenario
          </Link>
          <Link
            href="/test-lab"
            className="btn btn--cyan"
          >
            <FlaskConical size={11} />
            Open Test Lab
          </Link>
        </div>
      )}

      {/* Promote button */}
      {onPromote && (
        <div className="gate__foot">
          <button
            type="button"
            disabled={!transition.eligible || promoting}
            onClick={() => onPromote(transition.to)}
            className={transition.eligible ? "btn btn--cyan" : "btn"}
            style={{ width: "100%" }}
          >
            {promoting
              ? "Promoting..."
              : transition.eligible
                ? `Promote to ${getStatusLabel(transition.to as any)}`
                : "Blocked — resolve errors first"}
          </button>
        </div>
      )}
    </div>
  );
}
