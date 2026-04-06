import type { AgentDefinition } from "@/lib/agent-registry/types";
import type {
  AgentStatus,
  LifecycleBlocker,
  LifecycleGate,
  MainLifecycleStep,
  MainStepDisplay,
  StepState,
  TransitionInfo,
} from "./types";

// ── Main promotion path ───────────────────────────────────────────────

const MAIN_PATH: MainLifecycleStep[] = [
  "draft",
  "designed",
  "tested",
  "registered",
  "active",
];

const MAIN_PATH_LABELS: Record<MainLifecycleStep, string> = {
  draft: "Draft",
  designed: "Designed",
  tested: "Tested",
  registered: "Registered",
  active: "Active",
};

// ── Gates between main steps ──────────────────────────────────────────

const GATES: LifecycleGate[] = [
  {
    from: "draft",
    to: "designed",
    title: "Definition complete",
    description: "Agent definition, prompt, and skills must be fully specified.",
  },
  {
    from: "designed",
    to: "tested",
    title: "Qualification passed",
    description: "Behavioral test pack must be executed and all checks passed.",
  },
  {
    from: "tested",
    to: "registered",
    title: "Registry validated",
    description:
      "Agent contracts and configuration validated for registry inclusion.",
  },
  {
    from: "registered",
    to: "active",
    title: "Activation approved",
    description: "Final approval for production activation.",
  },
];

// ── Helpers ───────────────────────────────────────────────────────────

export function isMainPathStatus(status: string): status is MainLifecycleStep {
  return (MAIN_PATH as string[]).includes(status);
}

export function getMainLifecycleIndex(status: AgentStatus): number {
  const idx = MAIN_PATH.indexOf(status as MainLifecycleStep);
  return idx >= 0 ? idx : -1;
}

export function getMainPathSteps(currentStatus: AgentStatus): MainStepDisplay[] {
  const currentIdx = getMainLifecycleIndex(currentStatus);
  // If status is operational (deprecated/disabled/archived), show all main steps as done
  const effectiveIdx = currentIdx < 0 ? MAIN_PATH.length : currentIdx;

  return MAIN_PATH.map((step, i) => {
    let state: StepState;
    if (i < effectiveIdx) state = "done";
    else if (i === effectiveIdx && currentIdx >= 0) state = "current";
    else state = "locked";

    return { step, state, label: MAIN_PATH_LABELS[step] };
  });
}

export function getGateBetween(
  from: MainLifecycleStep,
  to: MainLifecycleStep,
): LifecycleGate | null {
  return GATES.find((g) => g.from === from && g.to === to) ?? null;
}

export function getAllGates(): LifecycleGate[] {
  return GATES;
}

export function getNextTransition(
  agent: AgentDefinition,
): TransitionInfo | null {
  const status = agent.status as AgentStatus;
  const idx = getMainLifecycleIndex(status);

  // No next transition from operational states or active
  if (idx < 0 || idx >= MAIN_PATH.length - 1) return null;

  const from = MAIN_PATH[idx];
  const to = MAIN_PATH[idx + 1];
  const gate = getGateBetween(from, to)!;
  const blockers = getLifecycleBlockers(agent, to);

  return {
    from: status,
    to,
    gate,
    blockers,
    eligible: blockers.filter((b) => b.severity === "error").length === 0,
  };
}

export function getLifecycleBlockers(
  agent: AgentDefinition,
  targetStatus?: MainLifecycleStep,
): LifecycleBlocker[] {
  const blockers: LifecycleBlocker[] = [];
  const target = targetStatus ?? getNextMainStep(agent.status as AgentStatus);
  if (!target) return blockers;

  // Common checks for any promotion
  if (!agent.prompt_ref && !agent.prompt_content) {
    blockers.push({
      key: "prompt_missing",
      label: "Prompt reference or content is missing",
      severity: "error",
    });
  }

  if (!agent.skill_ids || agent.skill_ids.length === 0) {
    blockers.push({
      key: "skills_missing",
      label: "No skills assigned to this agent",
      severity: "warning",
    });
  }

  // Gate-specific checks
  if (target === "designed") {
    if (!agent.purpose || agent.purpose.trim().length === 0) {
      blockers.push({
        key: "purpose_missing",
        label: "Agent purpose is not defined",
        severity: "error",
      });
    }
    if (!agent.family_id) {
      blockers.push({
        key: "family_missing",
        label: "Agent family is not assigned",
        severity: "error",
      });
    }
  }

  if (target === "tested") {
    if (
      agent.last_test_status === "not_tested" ||
      !agent.last_test_status
    ) {
      blockers.push({
        key: "test_not_executed",
        label: "Test pack not executed",
        severity: "error",
      });
    }
    if (agent.last_test_status === "failed") {
      blockers.push({
        key: "test_failed",
        label: "Last test run failed",
        severity: "error",
      });
    }
  }

  if (target === "registered") {
    if (!agent.input_contract_ref) {
      blockers.push({
        key: "input_contract_missing",
        label: "Input contract reference is missing",
        severity: "warning",
      });
    }
    if (!agent.output_contract_ref) {
      blockers.push({
        key: "output_contract_missing",
        label: "Output contract reference is missing",
        severity: "warning",
      });
    }
  }

  if (target === "active") {
    if (!agent.llm_provider || !agent.llm_model) {
      blockers.push({
        key: "llm_config_missing",
        label: "LLM provider or model not configured",
        severity: "warning",
      });
    }
  }

  return blockers;
}

export function getNextMainStep(
  status: AgentStatus,
): MainLifecycleStep | null {
  const idx = getMainLifecycleIndex(status);
  if (idx < 0 || idx >= MAIN_PATH.length - 1) return null;
  return MAIN_PATH[idx + 1];
}

export function getStatusLabel(status: AgentStatus): string {
  if (isMainPathStatus(status)) return MAIN_PATH_LABELS[status];
  const labels: Record<string, string> = {
    deprecated: "Deprecated",
    disabled: "Disabled",
    archived: "Archived",
  };
  return labels[status] ?? status;
}

export function canTransitionTo(
  from: AgentStatus,
  to: AgentStatus,
): boolean {
  // Main path transitions
  const fromIdx = getMainLifecycleIndex(from);
  const toIdx = getMainLifecycleIndex(to);
  if (fromIdx >= 0 && toIdx >= 0) return toIdx === fromIdx + 1;

  // Operational transitions
  if (from === "active" && (to === "deprecated" || to === "disabled"))
    return true;
  if (
    (from === "deprecated" || from === "disabled") &&
    to === "archived"
  )
    return true;

  return false;
}
