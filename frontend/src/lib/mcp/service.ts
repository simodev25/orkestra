/**
 * MCP Service — Data access layer for MCP Catalog & Toolkit
 *
 * Centralizes all MCP-related API calls.
 */

import type {
  McpDefinition,
  McpHealth,
  McpUsageSummary,
  McpCatalogStats,
  McpTestRequest,
  McpTestResult,
  McpCreatePayload,
  McpUpdatePayload,
  McpCompatibilityHint,
} from "./types";

const BASE = "/api/mcps";

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

// ────────────────────────────────────────────────────────────
// Catalog
// ────────────────────────────────────────────────────────────

export async function listMcps(params?: {
  effect_type?: string;
  status?: string;
  criticality?: string;
}): Promise<McpDefinition[]> {
  const query = new URLSearchParams();
  if (params?.effect_type && params.effect_type !== "all") query.set("effect_type", params.effect_type);
  if (params?.status && params.status !== "all") query.set("status", params.status);
  if (params?.criticality && params.criticality !== "all") query.set("criticality", params.criticality);
  const qs = query.toString();
  try {
    return await request<McpDefinition[]>(`${BASE}${qs ? `?${qs}` : ""}`);
  } catch (err) {
    console.error("Failed to list MCPs:", err);
    throw err;
  }
}

export async function getMcp(id: string): Promise<McpDefinition> {
  try {
    return await request<McpDefinition>(`${BASE}/${id}`);
  } catch (err) {
    console.error("Failed to get MCP:", err);
    throw err;
  }
}

export async function getCatalogStats(): Promise<McpCatalogStats> {
  try {
    return await request<McpCatalogStats>(`${BASE}/catalog/stats`);
  } catch (err) {
    console.error("Failed to get catalog stats:", err);
    throw err;
  }
}

// ────────────────────────────────────────────────────────────
// CRUD
// ────────────────────────────────────────────────────────────

export async function createMcp(data: McpCreatePayload): Promise<McpDefinition> {
  return request<McpDefinition>(BASE, { method: "POST", body: JSON.stringify(data) });
}

export async function updateMcp(id: string, data: McpUpdatePayload): Promise<McpDefinition> {
  return request<McpDefinition>(`${BASE}/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function updateMcpStatus(id: string, status: string): Promise<McpDefinition> {
  return request<McpDefinition>(`${BASE}/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

// ────────────────────────────────────────────────────────────
// Health & Usage
// ────────────────────────────────────────────────────────────

export async function getMcpHealth(id: string): Promise<McpHealth> {
  try {
    return await request<McpHealth>(`${BASE}/${id}/health`);
  } catch (err) {
    console.error("Failed to get MCP health:", err);
    throw err;
  }
}

export async function getMcpUsage(id: string): Promise<McpUsageSummary> {
  try {
    return await request<McpUsageSummary>(`${BASE}/${id}/usage`);
  } catch (err) {
    console.error("Failed to get MCP usage:", err);
    throw err;
  }
}

// ────────────────────────────────────────────────────────────
// Toolkit — Test / Invoke
// ────────────────────────────────────────────────────────────

export async function testMcp(id: string, req?: McpTestRequest): Promise<McpTestResult> {
  try {
    return await request<McpTestResult>(`${BASE}/${id}/test`, {
      method: "POST",
      body: JSON.stringify(req || { tool_action: null, tool_kwargs: {} }),
    });
  } catch (err) {
    console.error("Failed to test MCP:", err);
    throw err;
  }
}

// ────────────────────────────────────────────────────────────
// Compatibility Helper (computed client-side for now)
// ────────────────────────────────────────────────────────────

export function getCompatibilityHints(mcp: McpDefinition, allMcps: McpDefinition[]): McpCompatibilityHint {
  const effectFamilyMap: Record<string, string[]> = {
    read: ["preparation", "extraction", "evidence"],
    search: ["preparation", "research", "evidence"],
    compute: ["analysis", "control", "scoring"],
    generate: ["synthesis", "output"],
    validate: ["control", "governance"],
    write: ["output", "reporting"],
    act: ["output", "integration"],
  };

  const useCaseMap: Record<string, string[]> = {
    read: ["credit_review", "due_diligence", "document_analysis"],
    search: ["research", "due_diligence", "procurement"],
    compute: ["risk_scoring", "credit_review", "compliance"],
    generate: ["report_generation", "synthesis"],
    validate: ["compliance", "quality_check"],
    write: ["reporting", "export"],
    act: ["notification", "integration"],
  };

  const similar = allMcps
    .filter((m) => m.id !== mcp.id && m.effect_type === mcp.effect_type)
    .map((m) => m.id);

  return {
    mcp_id: mcp.id,
    compatible_agent_families: effectFamilyMap[mcp.effect_type] || [],
    compatible_use_cases: useCaseMap[mcp.effect_type] || [],
    similar_mcps: similar,
    suggested_effect_chain: mcp.effect_type === "read" ? ["read", "compute", "validate"]
      : mcp.effect_type === "search" ? ["search", "read", "compute"]
      : mcp.effect_type === "compute" ? ["compute", "validate", "generate"]
      : [mcp.effect_type],
  };
}

// ────────────────────────────────────────────────────────────
// Agent list (for allowed_agents multi-select)
// ────────────────────────────────────────────────────────────

export async function listAgentIds(): Promise<string[]> {
  try {
    const agents = await request<{ id: string }[]>("/api/agents");
    return agents.map((a) => a.id);
  } catch (err) {
    console.error("Failed to list agent IDs:", err);
    throw err;
  }
}
