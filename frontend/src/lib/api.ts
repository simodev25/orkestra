import type * as T from "./types";

const BASE = "/api";

async function request<R>(url: string, opts?: RequestInit): Promise<R> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  // Requests
  listRequests: (status?: string) =>
    request<T.Request[]>(`/requests${status ? `?status=${status}` : ""}`),
  createRequest: (data: { title: string; request_text: string; criticality?: string; use_case?: string }) =>
    request<T.Request>("/requests", { method: "POST", body: JSON.stringify(data) }),
  submitRequest: (id: string) =>
    request<T.Request>(`/requests/${id}/submit`, { method: "POST" }),

  // Cases
  listCases: (status?: string) =>
    request<T.Case[]>(`/cases${status ? `?status=${status}` : ""}`),
  convertToCase: (requestId: string) =>
    request<T.Case>(`/cases/${requestId}/convert`, { method: "POST" }),

  // Plans
  generatePlan: (caseId: string) =>
    request<T.Plan>(`/cases/${caseId}/plan`, { method: "POST" }),
  getPlan: (planId: string) =>
    request<T.Plan>(`/plans/${planId}`),

  // Runs
  listRuns: () => request<T.Run[]>("/runs"),
  getRun: (id: string) => request<T.Run>(`/runs/${id}`),
  createRun: (caseId: string, planId: string) =>
    request<T.Run>(`/cases/${caseId}/runs`, { method: "POST", body: JSON.stringify({ plan_id: planId }) }),
  startRun: (id: string) => request<T.Run>(`/runs/${id}/start`, { method: "POST" }),
  cancelRun: (id: string) => request<T.Run>(`/runs/${id}/cancel`, { method: "POST" }),
  getRunNodes: (id: string) => request<T.RunNode[]>(`/runs/${id}/nodes`),
  getRunLiveState: (id: string) => request<T.RunLiveState>(`/runs/${id}/live-state`),

  // Agents
  listAgents: (family?: string) =>
    request<T.Agent[]>(`/agents${family ? `?family=${family}` : ""}`),
  createAgent: (data: any) => request<T.Agent>("/agents", { method: "POST", body: JSON.stringify(data) }),
  updateAgentStatus: (id: string, status: string) =>
    request<T.Agent>(`/agents/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),

  // MCPs
  listMCPs: () => request<T.MCP[]>("/mcps"),
  createMCP: (data: any) => request<T.MCP>("/mcps", { method: "POST", body: JSON.stringify(data) }),
  updateMCPStatus: (id: string, status: string) =>
    request<T.MCP>(`/mcps/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),

  // Control
  listControlDecisions: () => request<T.ControlDecision[]>("/control-decisions"),
  getRunControlDecisions: (runId: string) => request<T.ControlDecision[]>(`/runs/${runId}/control-decisions`),

  // Approvals
  listApprovals: (status?: string) =>
    request<T.Approval[]>(`/approvals${status ? `?status=${status}` : ""}`),
  approveApproval: (id: string, comment?: string) =>
    request<T.Approval>(`/approvals/${id}/approve`, { method: "POST", body: JSON.stringify({ comment: comment || "" }) }),
  rejectApproval: (id: string, comment?: string) =>
    request<T.Approval>(`/approvals/${id}/reject`, { method: "POST", body: JSON.stringify({ comment: comment || "" }) }),

  // Audit
  getAuditTrail: (runId: string) => request<T.AuditEvent[]>(`/runs/${runId}/audit`),
  getEvidence: (runId: string) => request<any[]>(`/runs/${runId}/evidence`),

  // Workflows
  listWorkflows: () => request<T.Workflow[]>("/workflow-definitions"),
  createWorkflow: (data: any) =>
    request<T.Workflow>("/workflow-definitions", { method: "POST", body: JSON.stringify(data) }),
  publishWorkflow: (id: string) =>
    request<T.Workflow>(`/workflow-definitions/${id}/publish`, { method: "POST" }),

  // Settings
  listPolicies: () => request<T.PolicyProfile[]>("/settings/policy-profiles"),
  createPolicy: (data: any) =>
    request<T.PolicyProfile>("/settings/policy-profiles", { method: "POST", body: JSON.stringify(data) }),
  listBudgets: () => request<T.BudgetProfile[]>("/settings/budget-profiles"),
  createBudget: (data: any) =>
    request<T.BudgetProfile>("/settings/budget-profiles", { method: "POST", body: JSON.stringify(data) }),

  // Secrets (API keys)
  listSecrets: () => request<T.PlatformSecret[]>("/settings/secrets"),
  upsertSecret: (id: string, value: string, description?: string) =>
    request<{ id: string; status: string }>(`/settings/secrets/${id}`, {
      method: "PUT",
      body: JSON.stringify({ value, description: description ?? "" }),
    }),
  deleteSecret: (id: string) =>
    request<{ id: string; status: string }>(`/settings/secrets/${id}`, { method: "DELETE" }),

  // Metrics
  getPlatformMetrics: () => request<T.PlatformMetrics>("/metrics/platform"),
};
