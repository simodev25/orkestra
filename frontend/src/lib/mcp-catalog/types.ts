export type ObotState = "active" | "degraded" | "disabled" | string;
export type ObotHealthState = "healthy" | "warning" | "failing" | string;
export type OrkestraState = "enabled" | "disabled" | "restricted" | "hidden" | string;
export type McpCriticality = "low" | "medium" | "high" | string;
export type McpEffectType = "read" | "search" | "compute" | "generate" | "validate" | "write" | "act" | string;

export interface ObotServerSummary {
  id: string;
  name: string;
  purpose: string;
  description: string | null;
  effect_type: McpEffectType;
  criticality: McpCriticality;
  approval_required: boolean;
  state: ObotState;
  health_status: ObotHealthState | null;
  version: string | null;
  obot_url: string | null;
}

export interface ObotServerDetails extends ObotServerSummary {
  metadata: Record<string, unknown>;
  usage_last_24h: number | null;
  incidents_last_7d: number | null;
  health_note: string | null;
}

export interface OrkestraMcpBinding {
  obot_server_id: string;
  obot_server_name: string;
  enabled_in_orkestra: boolean;
  hidden_from_catalog: boolean;
  hidden_from_ai_generator: boolean;
  allowed_agent_families: string[];
  allowed_workflows: string[];
  business_domain: string | null;
  risk_level_override: string | null;
  preferred_use_cases: string[];
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CatalogMcpViewModel {
  obot_server: ObotServerSummary;
  orkestra_binding: OrkestraMcpBinding;
  obot_state: ObotState;
  orkestra_state: OrkestraState;
  is_imported_in_orkestra: boolean;
}

export interface CatalogMcpDetailsViewModel {
  obot_server: ObotServerDetails;
  orkestra_binding: OrkestraMcpBinding;
  obot_state: ObotState;
  orkestra_state: OrkestraState;
  is_imported_in_orkestra: boolean;
}

export interface McpCatalogStats {
  obot_total: number;
  obot_active: number;
  obot_degraded: number;
  obot_disabled: number;
  orkestra_enabled: number;
  orkestra_disabled: number;
  orkestra_restricted: number;
  orkestra_hidden: number;
  critical: number;
  approval_required: number;
  hidden_from_ai_generator: number;
}

export interface SyncCatalogResult {
  total_obot_servers: number;
  existing_bindings_updated: number;
  missing_bindings: number;
  source: string;
}

export interface ImportFromObotResult {
  imported_count: number;
  updated_count: number;
  total_selected: number;
}

export interface OrkestraBindingUpdatePayload {
  enabled_in_orkestra?: boolean;
  hidden_from_catalog?: boolean;
  hidden_from_ai_generator?: boolean;
  allowed_agent_families?: string[];
  allowed_workflows?: string[];
  business_domain?: string | null;
  risk_level_override?: string | null;
  preferred_use_cases?: string[];
  notes?: string | null;
}

export interface McpCatalogFilters {
  search?: string;
  obot_status?: string;
  orkestra_status?: string;
  criticality?: string;
  effect_type?: string;
  approval_required?: "all" | "true" | "false";
  allowed_workflow?: string;
  allowed_agent_family?: string;
  hidden_from_ai_generator?: "all" | "true" | "false";
}
