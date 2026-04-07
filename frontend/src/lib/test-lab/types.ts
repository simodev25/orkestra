// Types for Agentic Test Lab

export interface AssertionDef {
  type: string;
  target?: string;
  expected?: string;
  critical: boolean;
}

export interface TestScenario {
  id: string;
  name: string;
  description: string | null;
  agent_id: string;
  input_prompt: string;
  input_payload: Record<string, unknown> | null;
  allowed_tools: string[] | null;
  expected_tools: string[] | null;
  timeout_seconds: number;
  max_iterations: number;
  retry_count: number;
  assertions: AssertionDef[];
  tags: string[] | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface TestRun {
  id: string;
  scenario_id: string;
  agent_id: string;
  agent_version: string;
  status: string;
  verdict: string | null;
  score: number | null;
  duration_ms: number | null;
  final_output: string | null;
  summary: string | null;
  error_message: string | null;
  execution_metadata: Record<string, unknown> | null;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
}

export interface TestRunEvent {
  id: string;
  run_id: string;
  event_type: string;
  phase: string | null;
  message: string | null;
  details: Record<string, unknown> | null;
  timestamp: string;
  duration_ms: number | null;
}

export interface TestRunAssertion {
  id: string;
  run_id: string;
  assertion_type: string;
  target: string | null;
  expected: string | null;
  actual: string | null;
  passed: boolean;
  critical: boolean;
  message: string;
  details: Record<string, unknown> | null;
}

export interface TestRunDiagnostic {
  id: string;
  run_id: string;
  code: string;
  severity: string;
  message: string;
  probable_causes: string[] | null;
  recommendation: string | null;
  evidence: Record<string, unknown> | null;
}

export interface AgentTestSummary {
  agent_id: string;
  total_runs: number;
  passed_runs: number;
  failed_runs: number;
  warning_runs: number;
  pass_rate: number;
  average_score: number;
  last_run_at: string | null;
  last_verdict: string | null;
  tool_failure_rate: number;
  timeout_rate: number;
  average_duration_ms: number;
  eligible_for_tested: boolean;
}

export interface RunReport {
  run: TestRun;
  events: TestRunEvent[];
  assertions: TestRunAssertion[];
  diagnostics: TestRunDiagnostic[];
  scenario: TestScenario;
}
