"use client";

import { useState } from "react";
import { StatusBadge } from "@/components/ui/status-badge";
import { PromotionPath } from "./PromotionPath";
import { TransitionGate } from "./TransitionGate";
import { OperationalStates } from "./OperationalStates";
import {
  getMainPathSteps,
  getAllGates,
  getNextTransition,
  getGateBetween,
  getStatusLabel,
  isMainPathStatus,
} from "@/lib/agent-lifecycle/helpers";
import type { AgentDefinition } from "@/lib/agent-registry/types";
import type { AgentStatus } from "@/lib/agent-lifecycle/types";
import { updateAgentStatus } from "@/lib/agent-registry/service";
import { ArrowRight, Info } from "lucide-react";

interface AgentLifecyclePanelProps {
  agent: AgentDefinition;
  onStatusChange?: (updated: AgentDefinition) => void;
}

export function AgentLifecyclePanel({
  agent,
  onStatusChange,
}: AgentLifecyclePanelProps) {
  const [promoting, setPromoting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const status = agent.status as AgentStatus;
  const steps = getMainPathSteps(status);
  const transition = getNextTransition(agent);
  const allGates = getAllGates();

  // Build gate array for PromotionPath: gates[i] = gate between step i and step i+1
  const gatesForPath = steps.slice(1).map((s, i) => {
    return getGateBetween(steps[i].step, s.step);
  });

  const nextLabel = transition
    ? getStatusLabel(transition.to as AgentStatus)
    : null;

  async function handlePromote(to: string) {
    setPromoting(true);
    setError(null);
    try {
      const updated = await updateAgentStatus(agent.id, to);
      onStatusChange?.(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to promote agent");
    } finally {
      setPromoting(false);
    }
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="glass-panel p-5">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="section-title mb-2">Agent lifecycle</h3>
            <div className="flex items-center gap-3">
              <span className="text-xs text-ork-dim">Current status</span>
              <StatusBadge status={agent.status} />
              {nextLabel && (
                <>
                  <ArrowRight size={12} className="text-ork-dim" />
                  <span className="text-xs font-mono text-ork-purple">
                    Next: {nextLabel}
                  </span>
                </>
              )}
            </div>
          </div>
          <div className="flex items-start gap-1.5 max-w-xs">
            <Info size={13} className="text-ork-dim mt-0.5 shrink-0" />
            <p className="text-[10px] text-ork-dim leading-relaxed">
              The lifecycle governs an agent&apos;s progression from initial draft through
              qualification and activation. Each transition requires specific gate
              conditions to be met.
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="glass-panel p-3 border-ork-red/30">
          <p className="text-xs font-mono text-ork-red">{error}</p>
        </div>
      )}

      {/* Main promotion path */}
      <PromotionPath steps={steps} gates={gatesForPath} />

      {/* Current transition gate */}
      <TransitionGate
        transition={transition}
        currentStatus={agent.status}
        agentId={agent.id}
        onPromote={handlePromote}
        promoting={promoting}
      />

      {/* Operational end states */}
      <OperationalStates
        currentStatus={status}
        onTransition={handlePromote}
        transitioning={promoting}
      />
    </div>
  );
}
