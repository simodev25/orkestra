import type {
  AgentCreatePayload,
  AgentDefinition,
  AgentGenerationRequest,
  AgentGenerationResponse,
  AgentRegistryFilters,
  AgentRegistryStats,
  AgentUpdatePayload,
  GeneratedAgentDraft,
  McpCatalogSummary,
} from "./types";

const BASE = "/api/agents";

async function request<R>(url: string, opts?: RequestInit): Promise<R> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || res.statusText);
  }
  return res.json();
}

function asBoolParam(value: boolean | undefined): string | undefined {
  if (value === undefined) return undefined;
  return value ? "true" : "false";
}

export async function listAgents(filters?: AgentRegistryFilters): Promise<AgentDefinition[]> {
  const q = new URLSearchParams();
  if (filters?.q) q.set("q", filters.q);
  if (filters?.family && filters.family !== "all") q.set("family", filters.family);
  if (filters?.status && filters.status !== "all") q.set("status", filters.status);
  if (filters?.criticality && filters.criticality !== "all") q.set("criticality", filters.criticality);
  if (filters?.cost_profile && filters.cost_profile !== "all") q.set("cost_profile", filters.cost_profile);
  if (filters?.mcp_id) q.set("mcp_id", filters.mcp_id);
  if (filters?.workflow_id) q.set("workflow_id", filters.workflow_id);
  const workflowOnly = asBoolParam(filters?.used_in_workflow_only);
  if (workflowOnly) q.set("used_in_workflow_only", workflowOnly);
  const qs = q.toString();
  return request<AgentDefinition[]>(`${BASE}${qs ? `?${qs}` : ""}`);
}

export async function getAgent(agentId: string): Promise<AgentDefinition> {
  return request<AgentDefinition>(`${BASE}/${agentId}`);
}

export async function createAgent(payload: AgentCreatePayload): Promise<AgentDefinition> {
  return request<AgentDefinition>(BASE, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateAgent(agentId: string, payload: AgentUpdatePayload): Promise<AgentDefinition> {
  return request<AgentDefinition>(`${BASE}/${agentId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function updateAgentStatus(agentId: string, status: string): Promise<AgentDefinition> {
  return request<AgentDefinition>(`${BASE}/${agentId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function deleteAgent(agentId: string): Promise<void> {
  const res = await fetch(`${BASE}/${agentId}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || res.statusText);
  }
}

export async function getAgentRegistryStats(workflowId?: string): Promise<AgentRegistryStats> {
  const query = workflowId ? `?workflow_id=${encodeURIComponent(workflowId)}` : "";
  return request<AgentRegistryStats>(`${BASE}/stats${query}`);
}

export async function generateAgentDraft(
  payload: AgentGenerationRequest,
): Promise<AgentGenerationResponse> {
  return request<AgentGenerationResponse>(`${BASE}/generate-draft`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function saveGeneratedDraft(draft: GeneratedAgentDraft): Promise<AgentDefinition> {
  return request<AgentDefinition>(`${BASE}/save-generated-draft`, {
    method: "POST",
    body: JSON.stringify({ draft }),
  });
}

export async function listAvailableSkills(): Promise<string[]> {
  const res = await fetch("/api/skills", {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || res.statusText);
  }
  const skills = await res.json();
  return skills.map((s: { skill_id: string }) => s.skill_id);
}

export async function listMcpCatalogForAgentDesign(): Promise<McpCatalogSummary[]> {
  const items = await request<
    Array<{
      obot_server: {
        id: string;
        name: string;
        purpose: string;
        effect_type: string;
        criticality: string;
        approval_required: boolean;
      };
      obot_state: string;
      orkestra_state: string;
    }>
  >("/api/mcp-catalog");

  return items.map((item) => ({
    id: item.obot_server.id,
    name: item.obot_server.name,
    purpose: item.obot_server.purpose,
    effect_type: item.obot_server.effect_type,
    criticality: item.obot_server.criticality,
    approval_required: item.obot_server.approval_required,
    obot_state: item.obot_state,
    orkestra_state: item.orkestra_state,
  }));
}
