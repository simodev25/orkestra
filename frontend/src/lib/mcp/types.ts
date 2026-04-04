/**
 * MCP Catalog & Toolkit — Type definitions
 *
 * Strong typing for all MCP-related data structures.
 * No `any` types. Every field is documented.
 */

// ────────────────────────────────────────────────────────────
// Enums
// ────────────────────────────────────────────────────────────

export type McpEffectType = "read" | "search" | "compute" | "generate" | "validate" | "write" | "act";
export type McpStatus = "draft" | "tested" | "registered" | "active" | "degraded" | "disabled" | "archived";
export type McpCriticality = "low" | "medium" | "high";
export type McpCostProfile = "low" | "medium" | "high" | "variable";
export type McpRetryPolicy = "none" | "retry_once" | "retry_twice" | "standard" | "aggressive";

// ────────────────────────────────────────────────────────────
// Core MCP Definition
// ────────────────────────────────────────────────────────────

export interface McpDefinition {
  id: string;
  name: string;
  purpose: string;
  description: string | null;
  effect_type: McpEffectType;
  input_contract_ref: string | null;
  output_contract_ref: string | null;
  allowed_agents: string[] | null;
  criticality: McpCriticality;
  timeout_seconds: number;
  retry_policy: string;
  cost_profile: McpCostProfile;
  approval_required: boolean;
  audit_required: boolean;
  status: McpStatus;
  version: string;
  owner: string | null;
  created_at: string;
  updated_at: string;
}

// ────────────────────────────────────────────────────────────
// MCP Health
// ────────────────────────────────────────────────────────────

export interface McpHealth {
  mcp_id: string;
  status: string;
  healthy: boolean;
  last_check_at: string | null;
  last_success_at: string | null;
  last_failure_at: string | null;
  avg_latency_ms: number | null;
  failure_rate: number | null;
  total_invocations: number;
  recent_errors: string[];
}

// ────────────────────────────────────────────────────────────
// MCP Runtime Metadata
// ────────────────────────────────────────────────────────────

export interface McpRuntimeMetadata {
  timeout_seconds: number;
  retry_policy: string;
  cost_profile: McpCostProfile;
  approval_required: boolean;
  audit_required: boolean;
}

// ────────────────────────────────────────────────────────────
// MCP Usage Summary
// ────────────────────────────────────────────────────────────

export interface McpUsageSummary {
  mcp_id: string;
  total_invocations: number;
  total_cost: number;
  avg_latency_ms: number;
  avg_cost: number;
  agents_using: string[];
  invocations_by_status: Record<string, number>;
}

// ────────────────────────────────────────────────────────────
// MCP Test
// ────────────────────────────────────────────────────────────

export interface McpTestRequest {
  tool_action: string | null;
  tool_kwargs: Record<string, unknown>;
}

export interface McpTestResult {
  mcp_id: string;
  success: boolean;
  latency_ms: number;
  output: string | null;
  error: string | null;
}

// ────────────────────────────────────────────────────────────
// MCP Catalog Stats
// ────────────────────────────────────────────────────────────

export interface McpCatalogStats {
  total: number;
  active: number;
  degraded: number;
  disabled: number;
  critical: number;
  approval_required: number;
  healthy: number;
}

// ────────────────────────────────────────────────────────────
// MCP Catalog Filter State
// ────────────────────────────────────────────────────────────

export interface McpCatalogFilterState {
  search: string;
  status: McpStatus | "all";
  criticality: McpCriticality | "all";
  effect_type: McpEffectType | "all";
  approval_required: boolean | "all";
  audit_required: boolean | "all";
  cost_profile: McpCostProfile | "all";
}

// ────────────────────────────────────────────────────────────
// MCP Create / Update payloads
// ────────────────────────────────────────────────────────────

export interface McpCreatePayload {
  id: string;
  name: string;
  purpose: string;
  description?: string;
  effect_type: McpEffectType;
  input_contract_ref?: string;
  output_contract_ref?: string;
  allowed_agents?: string[];
  criticality?: McpCriticality;
  timeout_seconds?: number;
  retry_policy?: string;
  cost_profile?: McpCostProfile;
  approval_required?: boolean;
  audit_required?: boolean;
  version?: string;
  owner?: string;
}

export interface McpUpdatePayload {
  name?: string;
  purpose?: string;
  description?: string;
  effect_type?: McpEffectType;
  input_contract_ref?: string;
  output_contract_ref?: string;
  allowed_agents?: string[];
  criticality?: McpCriticality;
  timeout_seconds?: number;
  retry_policy?: string;
  cost_profile?: McpCostProfile;
  approval_required?: boolean;
  audit_required?: boolean;
  version?: string;
  owner?: string;
}

// ────────────────────────────────────────────────────────────
// Compatibility Helper (for future AI agent generation)
// ────────────────────────────────────────────────────────────

export interface McpCompatibilityHint {
  mcp_id: string;
  compatible_agent_families: string[];
  compatible_use_cases: string[];
  similar_mcps: string[];
  suggested_effect_chain: string[];
}

// ────────────────────────────────────────────────────────────
// Effect type metadata (for UI)
// ────────────────────────────────────────────────────────────

export const EFFECT_TYPE_META: Record<McpEffectType, { label: string; color: string; icon: string; risk: string }> = {
  read: { label: "Read", color: "cyan", icon: "BookOpen", risk: "low" },
  search: { label: "Search", color: "cyan", icon: "Search", risk: "low" },
  compute: { label: "Compute", color: "purple", icon: "Cpu", risk: "low" },
  generate: { label: "Generate", color: "purple", icon: "Sparkles", risk: "medium" },
  validate: { label: "Validate", color: "green", icon: "CheckCircle", risk: "low" },
  write: { label: "Write", color: "amber", icon: "PenLine", risk: "high" },
  act: { label: "Act", color: "red", icon: "Zap", risk: "critical" },
};

export const CRITICALITY_META: Record<McpCriticality, { label: string; color: string }> = {
  low: { label: "Low", color: "green" },
  medium: { label: "Medium", color: "amber" },
  high: { label: "High", color: "red" },
};

export const STATUS_META: Record<McpStatus, { label: string; color: string }> = {
  draft: { label: "Draft", color: "dim" },
  tested: { label: "Tested", color: "cyan" },
  registered: { label: "Registered", color: "purple" },
  active: { label: "Active", color: "green" },
  degraded: { label: "Degraded", color: "amber" },
  disabled: { label: "Disabled", color: "red" },
  archived: { label: "Archived", color: "dim" },
};
