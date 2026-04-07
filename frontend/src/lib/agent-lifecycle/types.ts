export type AgentStatus =
  | "draft"
  | "designed"
  | "tested"
  | "registered"
  | "active"
  | "deprecated"
  | "disabled"
  | "archived";

export type MainLifecycleStep =
  | "draft"
  | "designed"
  | "tested"
  | "registered"
  | "active";

export type OperationalStatus = "deprecated" | "disabled" | "archived";

export type StepState = "done" | "current" | "locked";

export interface LifecycleGate {
  from: MainLifecycleStep;
  to: MainLifecycleStep;
  title: string;
  description: string;
}

export interface LifecycleBlocker {
  key: string;
  label: string;
  severity: "error" | "warning";
}

export interface TransitionInfo {
  from: AgentStatus;
  to: AgentStatus;
  gate: LifecycleGate;
  blockers: LifecycleBlocker[];
  eligible: boolean;
}

export interface MainStepDisplay {
  step: MainLifecycleStep;
  state: StepState;
  label: string;
}
