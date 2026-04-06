import type { AgentStatus, LifecycleBlocker } from "@/lib/agent-lifecycle/types";

// ── Test modes ────────────────────────────────────────────────────────

export type TestMode = "manual" | "template" | "regression";

// ── Behavioral checks ────────────────────────────────────────────────

export const BEHAVIORAL_CHECK_KEYS = [
  "stayInScope",
  "structuredOutput",
  "groundedEvidence",
  "avoidsHallucination",
  "flagsMissingData",
  "handlesAmbiguity",
  "refusesOutOfScopeAction",
] as const;

export type BehavioralCheckKey = (typeof BEHAVIORAL_CHECK_KEYS)[number];

export interface BehavioralCheckDef {
  key: BehavioralCheckKey;
  label: string;
  description: string;
}

export const BEHAVIORAL_CHECKS: BehavioralCheckDef[] = [
  {
    key: "stayInScope",
    label: "Stays in scope",
    description: "Agent responds only within its defined domain",
  },
  {
    key: "structuredOutput",
    label: "Structured output",
    description: "Agent produces output matching the expected schema",
  },
  {
    key: "groundedEvidence",
    label: "Grounded evidence",
    description: "Claims are backed by provided documents/data",
  },
  {
    key: "avoidsHallucination",
    label: "Avoids hallucination",
    description: "Agent does not fabricate facts or references",
  },
  {
    key: "flagsMissingData",
    label: "Flags missing data",
    description: "Agent explicitly signals when required data is absent",
  },
  {
    key: "handlesAmbiguity",
    label: "Handles ambiguity",
    description: "Agent asks for clarification or acknowledges uncertainty",
  },
  {
    key: "refusesOutOfScopeAction",
    label: "Refuses out-of-scope action",
    description: "Agent declines tasks beyond its mandate",
  },
];

// ── Test case input ──────────────────────────────────────────────────

export interface AgentTestCaseInput {
  mode: TestMode;
  title: string;
  task: string;
  structuredInput: string; // JSON string edited by user
  evidence: string;
  contextVariables: string; // JSON string
  expectedBehaviors: Record<BehavioralCheckKey, boolean>;
}

// ── Test run result ──────────────────────────────────────────────────

export type RunVerdict = "pass" | "fail" | "error" | "running";

export interface BehavioralCheckResult {
  key: BehavioralCheckKey;
  label: string;
  expected: boolean;
  actual: "pass" | "fail";
  details?: string;
}

export interface AgentTestRunResult {
  id: string;
  agentId: string;
  agentVersion: string;
  timestamp: string;
  status: "running" | "completed" | "failed" | "error";
  verdict: RunVerdict;
  latencyMs: number;
  tokenUsage: { input: number; output: number; total: number } | null;
  rawOutput: string;
  parsedOutput: Record<string, unknown> | null;
  behavioralChecks: BehavioralCheckResult[];
  notes: string;
}

// ── Qualification gate ───────────────────────────────────────────────

export interface QualificationGateResult {
  eligible: boolean;
  currentStatus: AgentStatus;
  targetStatus: "tested";
  blockers: LifecycleBlocker[];
  qualifiedRunsCount: number;
  requiredRunsCount: number;
}

// ── Default empty test case ──────────────────────────────────────────

export function createEmptyTestCase(): AgentTestCaseInput {
  const behaviors = {} as Record<BehavioralCheckKey, boolean>;
  for (const check of BEHAVIORAL_CHECKS) {
    behaviors[check.key] = true;
  }
  return {
    mode: "manual",
    title: "",
    task: "",
    structuredInput: "{}",
    evidence: "",
    contextVariables: "{}",
    expectedBehaviors: behaviors,
  };
}
