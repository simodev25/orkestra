export type AgentStatus =
  | "draft"
  | "designed"
  | "tested"
  | "registered"
  | "active"
  | "deprecated"
  | "disabled"
  | "archived"
  | string;

export interface AgentDefinition {
  id: string;
  name: string;
  family: string;
  purpose: string;
  description: string | null;
  skills: string[] | null;
  selection_hints: Record<string, string | boolean | string[]> | null;
  allowed_mcps: string[] | null;
  forbidden_effects: string[] | null;
  input_contract_ref: string | null;
  output_contract_ref: string | null;
  criticality: string;
  cost_profile: string;
  limitations: string[] | null;
  prompt_ref: string | null;
  prompt_content: string | null;
  skills_ref: string | null;
  skills_content: string | null;
  version: string;
  status: AgentStatus;
  owner: string | null;
  last_test_status: string;
  last_validated_at: string | null;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

export interface AgentRegistryFilters {
  q?: string;
  family?: string;
  status?: string;
  criticality?: string;
  cost_profile?: string;
  mcp_id?: string;
  workflow_id?: string;
  used_in_workflow_only?: boolean;
}

export interface AgentRegistryStats {
  total_agents: number;
  active_agents: number;
  tested_agents: number;
  deprecated_agents: number;
  current_workflow_agents: number;
}

export interface McpCatalogSummary {
  id: string;
  name: string;
  purpose: string;
  effect_type: string;
  criticality: string;
  approval_required: boolean;
  obot_state: string;
  orkestra_state: string;
}

export interface AgentGenerationRequest {
  intent: string;
  use_case?: string;
  target_workflow?: string;
  criticality_target?: string;
  preferred_family?: string;
  preferred_output_style?: string;
  preferred_mcp_scope?: string;
  constraints?: string;
  owner?: string;
}

export interface GeneratedAgentDraft {
  agent_id: string;
  name: string;
  family: string;
  purpose: string;
  description: string;
  skills: string[];
  selection_hints: Record<string, string | boolean | string[]>;
  allowed_mcps: string[];
  forbidden_effects: string[];
  input_contract_ref: string | null;
  output_contract_ref: string | null;
  criticality: string;
  cost_profile: string;
  limitations: string[];
  prompt_content: string;
  skills_content: string;
  owner: string | null;
  version: string;
  status: AgentStatus;
  suggested_missing_mcps: string[];
  mcp_rationale: Record<string, string>;
}

export interface AgentGenerationResponse {
  draft: GeneratedAgentDraft;
  available_mcps: McpCatalogSummary[];
  source: string;
}

export interface AgentGenerationReviewState {
  request: AgentGenerationRequest;
  draft: GeneratedAgentDraft;
  available_mcps: McpCatalogSummary[];
}

export interface AgentCreatePayload {
  id: string;
  name: string;
  family: string;
  purpose: string;
  description?: string | null;
  skills?: string[];
  selection_hints?: Record<string, string | boolean | string[]>;
  allowed_mcps?: string[];
  forbidden_effects?: string[];
  input_contract_ref?: string | null;
  output_contract_ref?: string | null;
  criticality?: string;
  cost_profile?: string;
  limitations?: string[];
  prompt_ref?: string | null;
  prompt_content?: string | null;
  skills_ref?: string | null;
  skills_content?: string | null;
  version?: string;
  status?: AgentStatus;
  owner?: string | null;
  last_test_status?: string;
  usage_count?: number;
}

export interface AgentUpdatePayload {
  name?: string;
  family?: string;
  purpose?: string;
  description?: string | null;
  skills?: string[];
  selection_hints?: Record<string, string | boolean | string[]>;
  allowed_mcps?: string[];
  forbidden_effects?: string[];
  input_contract_ref?: string | null;
  output_contract_ref?: string | null;
  criticality?: string;
  cost_profile?: string;
  limitations?: string[];
  prompt_ref?: string | null;
  prompt_content?: string | null;
  skills_ref?: string | null;
  skills_content?: string | null;
  version?: string;
  status?: AgentStatus;
  owner?: string | null;
  last_test_status?: string;
  usage_count?: number;
}
