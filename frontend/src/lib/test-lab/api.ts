import type * as T from "./types";
import { request } from "../api-client";

const BASE = "/api/test-lab";

export const testLabApi = {
  // Scenarios
  listScenarios: (agentId?: string) =>
    request<T.TestScenario[]>(`${BASE}/scenarios${agentId ? `?agent_id=${agentId}` : ""}`),
  getScenario: (id: string) =>
    request<T.TestScenario>(`${BASE}/scenarios/${id}`),
  createScenario: (data: Omit<T.TestScenario, "id" | "created_at" | "updated_at">) =>
    request<T.TestScenario>(`${BASE}/scenarios`, { method: "POST", body: JSON.stringify(data) }),
  updateScenario: (id: string, data: Partial<T.TestScenario>) =>
    request<T.TestScenario>(`${BASE}/scenarios/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteScenario: (id: string) =>
    request<void>(`${BASE}/scenarios/${id}`, { method: "DELETE" }),

  // Runs
  startRun: (scenarioId: string) =>
    request<T.TestRun>(`${BASE}/scenarios/${scenarioId}/run`, { method: "POST" }),
  listRuns: (params?: { scenario_id?: string; agent_id?: string }) => {
    const q = new URLSearchParams();
    if (params?.scenario_id) q.set("scenario_id", params.scenario_id);
    if (params?.agent_id) q.set("agent_id", params.agent_id);
    const qs = q.toString();
    return request<T.TestRun[]>(`${BASE}/runs${qs ? `?${qs}` : ""}`);
  },
  getRun: (id: string) =>
    request<T.TestRun>(`${BASE}/runs/${id}`),
  getRunEvents: (runId: string) =>
    request<T.TestRunEvent[]>(`${BASE}/runs/${runId}/events`),
  getRunAssertions: (runId: string) =>
    request<T.TestRunAssertion[]>(`${BASE}/runs/${runId}/assertions`),
  getRunDiagnostics: (runId: string) =>
    request<T.TestRunDiagnostic[]>(`${BASE}/runs/${runId}/diagnostics`),
  getRunReport: (runId: string) =>
    request<T.RunReport>(`${BASE}/runs/${runId}/report`),

  // Agent summary
  getAgentSummary: (agentId: string) =>
    request<T.AgentTestSummary>(`${BASE}/agents/${agentId}/summary`),
};
