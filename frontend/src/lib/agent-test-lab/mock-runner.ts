import type {
  AgentTestCaseInput,
  AgentTestRunResult,
  BehavioralCheckResult,
  BehavioralCheckKey,
} from "./types";
import { BEHAVIORAL_CHECKS } from "./types";

/**
 * Mock test runner.
 * Replace this module with a real backend call when the test execution API is available.
 * Expected backend endpoint: POST /api/agents/{agentId}/test-run
 * Expected request body: AgentTestCaseInput
 * Expected response: AgentTestRunResult
 */
export async function executeTestRun(
  agentId: string,
  agentVersion: string,
  testCase: AgentTestCaseInput,
): Promise<AgentTestRunResult> {
  // Simulate network latency
  await new Promise((r) => setTimeout(r, 1500 + Math.random() * 1000));

  const checks: BehavioralCheckResult[] = BEHAVIORAL_CHECKS.filter(
    (c) => testCase.expectedBehaviors[c.key],
  ).map((c) => {
    // Simulate ~85% pass rate
    const passed = Math.random() > 0.15;
    return {
      key: c.key,
      label: c.label,
      expected: true,
      actual: passed ? ("pass" as const) : ("fail" as const),
      details: passed
        ? "Check passed in simulated run"
        : "Simulated failure — replace with real validation",
    };
  });

  const allPassed = checks.every((c) => c.actual === "pass");
  const latency = 800 + Math.floor(Math.random() * 2200);

  const mockOutput = JSON.stringify(
    {
      analysis: "This is a simulated agent response for the test scenario.",
      confidence: allPassed ? 0.92 : 0.61,
      recommendations: [
        "Simulated recommendation 1",
        "Simulated recommendation 2",
      ],
    },
    null,
    2,
  );

  return {
    id: `run-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    agentId,
    agentVersion,
    timestamp: new Date().toISOString(),
    status: "completed",
    verdict: allPassed ? "pass" : "fail",
    latencyMs: latency,
    tokenUsage: {
      input: 340 + Math.floor(Math.random() * 200),
      output: 120 + Math.floor(Math.random() * 150),
      total: 0, // computed below
    },
    rawOutput: mockOutput,
    parsedOutput: JSON.parse(mockOutput),
    behavioralChecks: checks,
    notes: "",
  };
}
