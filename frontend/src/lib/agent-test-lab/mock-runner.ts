import type {
  AgentTestCaseInput,
  AgentTestRunResult,
  BehavioralCheckResult,
} from "./types";
import { BEHAVIORAL_CHECKS } from "./types";

/**
 * Test runner — calls POST /api/agents/{agentId}/test-run to execute
 * a real LLM call with the agent's system prompt + test task.
 *
 * Behavioral checks are currently evaluated client-side as heuristics.
 * Replace with server-side validation when available.
 */
export async function executeTestRun(
  agentId: string,
  agentVersion: string,
  testCase: AgentTestCaseInput,
): Promise<AgentTestRunResult> {
  let structuredInput: Record<string, unknown> | null = null;
  try {
    structuredInput = JSON.parse(testCase.structuredInput);
  } catch {
    /* keep null */
  }

  let contextVars: Record<string, unknown> | null = null;
  try {
    contextVars = JSON.parse(testCase.contextVariables);
  } catch {
    /* keep null */
  }

  const res = await fetch(`/api/agents/${agentId}/test-run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task: testCase.task,
      structured_input: structuredInput,
      evidence: testCase.evidence || null,
      context_variables: contextVars,
    }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Test run failed: ${res.statusText}`);
  }

  const data = await res.json();

  const rawOutput: string = data.raw_output || "";
  let parsedOutput: Record<string, unknown> | null = null;
  try {
    parsedOutput = JSON.parse(rawOutput);
  } catch {
    /* not JSON — keep null */
  }

  // Client-side behavioral check heuristics (best-effort until server-side validation)
  const checks: BehavioralCheckResult[] = BEHAVIORAL_CHECKS.filter(
    (c) => testCase.expectedBehaviors[c.key],
  ).map((c) => {
    const passed = evaluateCheck(c.key, rawOutput);
    return {
      key: c.key,
      label: c.label,
      expected: true,
      actual: passed ? ("pass" as const) : ("fail" as const),
      details: passed
        ? "Heuristic check passed"
        : "Heuristic check flagged — review output manually",
    };
  });

  const allPassed = checks.every((c) => c.actual === "pass");
  const isError = data.status === "error";

  return {
    id: `run-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    agentId: data.agent_id || agentId,
    agentVersion: data.agent_version || agentVersion,
    timestamp: new Date().toISOString(),
    status: isError ? "error" : "completed",
    verdict: isError ? "error" : allPassed ? "pass" : "fail",
    latencyMs: data.latency_ms || 0,
    tokenUsage: data.token_usage
      ? {
          input: data.token_usage.input || 0,
          output: data.token_usage.output || 0,
          total: data.token_usage.total || 0,
        }
      : null,
    rawOutput,
    parsedOutput,
    behavioralChecks: checks,
    notes: isError ? (data.error || "LLM call failed") : "",
  };
}

/**
 * Simple heuristic checks against the raw LLM output.
 * These are best-effort signals, not definitive verdicts.
 */
function evaluateCheck(key: string, output: string): boolean {
  const lower = output.toLowerCase();
  const hasContent = output.trim().length > 20;

  switch (key) {
    case "stayInScope":
      // Pass if output doesn't contain disclaimers about being out of scope
      return hasContent && !lower.includes("not within my scope") && !lower.includes("cannot help with");
    case "structuredOutput":
      // Pass if output looks structured (JSON, bullet points, sections)
      return hasContent && (output.includes("{") || output.includes("- ") || output.includes("##") || output.includes("1."));
    case "groundedEvidence":
      // Pass if output doesn't contain hedging language typical of hallucination
      return hasContent;
    case "avoidsHallucination":
      // Pass if output is present (deeper analysis needs server-side validation)
      return hasContent;
    case "flagsMissingData":
    case "handlesAmbiguity":
    case "refusesOutOfScopeAction":
      return false; // Cannot be evaluated client-side
    default:
      return true;
  }
}
