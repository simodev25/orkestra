import type {
  CatalogMcpDetailsViewModel,
  CatalogMcpViewModel,
  ImportFromObotResult,
  McpCatalogFilters,
  McpCatalogStats,
  ObotServerDetails,
  ObotServerSummary,
  OrkestraMcpBinding,
  OrkestraBindingUpdatePayload,
  SyncCatalogResult,
} from "./types";

const BASE = "/api/mcp-catalog";

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

function boolParam(value: "all" | "true" | "false" | undefined): boolean | undefined {
  if (value === "true") return true;
  if (value === "false") return false;
  return undefined;
}

export function mapObotServerToCatalogItem(
  obotServer: ObotServerSummary,
  binding: OrkestraMcpBinding,
  isImportedInOrkestra: boolean,
): CatalogMcpViewModel {
  const orkestraState = binding.hidden_from_catalog
    ? "hidden"
    : !binding.enabled_in_orkestra
      ? "disabled"
      : binding.allowed_agent_families.length > 0 || binding.allowed_workflows.length > 0
        ? "restricted"
        : "enabled";

  return {
    obot_server: obotServer,
    orkestra_binding: binding,
    obot_state: obotServer.state,
    orkestra_state: orkestraState,
    is_imported_in_orkestra: isImportedInOrkestra,
  };
}

export async function listCatalogItems(filters?: McpCatalogFilters): Promise<CatalogMcpViewModel[]> {
  const query = new URLSearchParams();
  if (filters?.search) query.set("search", filters.search);
  if (filters?.obot_status && filters.obot_status !== "all") query.set("obot_status", filters.obot_status);
  if (filters?.orkestra_status && filters.orkestra_status !== "all") query.set("orkestra_status", filters.orkestra_status);
  if (filters?.criticality && filters.criticality !== "all") query.set("criticality", filters.criticality);
  if (filters?.effect_type && filters.effect_type !== "all") query.set("effect_type", filters.effect_type);
  const approvalRequired = boolParam(filters?.approval_required);
  if (approvalRequired !== undefined) query.set("approval_required", String(approvalRequired));
  const hiddenFromAi = boolParam(filters?.hidden_from_ai_generator);
  if (hiddenFromAi !== undefined) query.set("hidden_from_ai_generator", String(hiddenFromAi));
  if (filters?.allowed_workflow) query.set("allowed_workflow", filters.allowed_workflow);
  if (filters?.allowed_agent_family) query.set("allowed_agent_family", filters.allowed_agent_family);

  const qs = query.toString();
  return request<CatalogMcpViewModel[]>(`${BASE}${qs ? `?${qs}` : ""}`);
}

export async function fetchObotServers(): Promise<ObotServerSummary[]> {
  const items = await listCatalogItems();
  return items.map((item) => item.obot_server);
}

export async function getCatalogItem(obotServerId: string): Promise<CatalogMcpDetailsViewModel> {
  return request<CatalogMcpDetailsViewModel>(`${BASE}/${obotServerId}`);
}

export async function fetchObotServerById(obotServerId: string): Promise<ObotServerDetails> {
  const detail = await getCatalogItem(obotServerId);
  return detail.obot_server;
}

export async function getCatalogStats(): Promise<McpCatalogStats> {
  return request<McpCatalogStats>(`${BASE}/stats`);
}

export async function syncObotCatalog(): Promise<SyncCatalogResult> {
  return request<SyncCatalogResult>(`${BASE}/sync`, { method: "POST" });
}

export async function importFromObot(obotServerIds?: string[]): Promise<ImportFromObotResult> {
  return request<ImportFromObotResult>(`${BASE}/import`, {
    method: "POST",
    body: JSON.stringify({ obot_server_ids: obotServerIds }),
  });
}

export async function updateOrkestraBindings(
  obotServerId: string,
  payload: OrkestraBindingUpdatePayload,
): Promise<OrkestraMcpBinding> {
  return request<OrkestraMcpBinding>(`${BASE}/${obotServerId}/bindings`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function enableInOrkestra(obotServerId: string): Promise<OrkestraMcpBinding> {
  return request<OrkestraMcpBinding>(`${BASE}/${obotServerId}/enable`, { method: "POST" });
}

export async function disableInOrkestra(obotServerId: string): Promise<OrkestraMcpBinding> {
  return request<OrkestraMcpBinding>(`${BASE}/${obotServerId}/disable`, { method: "POST" });
}

export async function bindToWorkflow(
  obotServerId: string,
  workflowId: string,
): Promise<OrkestraMcpBinding> {
  return request<OrkestraMcpBinding>(`${BASE}/${obotServerId}/bind-workflow`, {
    method: "POST",
    body: JSON.stringify({ workflow_id: workflowId }),
  });
}

export async function bindToAgentFamily(
  obotServerId: string,
  agentFamily: string,
): Promise<OrkestraMcpBinding> {
  return request<OrkestraMcpBinding>(`${BASE}/${obotServerId}/bind-agent-family`, {
    method: "POST",
    body: JSON.stringify({ agent_family: agentFamily }),
  });
}
