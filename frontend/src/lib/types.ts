export interface Request {
  id: string;
  title: string;
  request_text: string;
  use_case: string | null;
  criticality: string;
  input_mode: string;
  status: string;
  attachments_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface Case {
  id: string;
  request_id: string;
  case_type: string | null;
  criticality: string;
  status: string;
  current_run_id: string | null;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface Plan {
  id: string;
  case_id: string;
  run_id: string | null;
  objective_summary: string | null;
  selected_agents: any[];
  selected_mcps: any[];
  execution_topology: any;
  estimated_cost: number | null;
  status: string;
  created_at: string;
}

export interface Run {
  id: string;
  case_id: string;
  plan_id: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  estimated_cost: number | null;
  actual_cost: number;
  created_at: string;
}

export interface RunNode {
  id: string;
  run_id: string;
  node_type: string;
  node_ref: string;
  status: string;
  depends_on: string[] | null;
  parallel_group: string | null;
  order_index: number;
  started_at: string | null;
  ended_at: string | null;
}

export interface Agent {
  id: string;
  name: string;
  family: string;
  purpose: string;
  description: string | null;
  skills: string[] | null;
  allowed_mcps: string[] | null;
  criticality: string;
  cost_profile: string;
  version: string;
  status: string;
  owner: string | null;
  created_at: string;
}

export interface MCP {
  id: string;
  name: string;
  purpose: string;
  effect_type: string;
  allowed_agents: string[] | null;
  criticality: string;
  timeout_seconds: number;
  cost_profile: string;
  approval_required: boolean;
  audit_required: boolean;
  status: string;
  version: string;
  owner: string | null;
  created_at: string;
}

export interface ControlDecision {
  id: string;
  run_id: string;
  decision_scope: string;
  decision_type: string;
  policy_rule_id: string | null;
  reason: string;
  severity: string;
  target_ref: string | null;
  created_at: string;
}

export interface Approval {
  id: string;
  run_id: string;
  case_id: string;
  approval_type: string;
  reason: string;
  reviewer_role: string | null;
  assigned_to: string | null;
  status: string;
  requested_at: string | null;
  resolved_at: string | null;
  decision_comment: string | null;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  run_id: string | null;
  event_type: string;
  actor_type: string;
  actor_ref: string;
  payload: any;
  timestamp: string;
}

export interface Workflow {
  id: string;
  name: string;
  version: string;
  use_case: string | null;
  execution_mode: string;
  graph_definition: any;
  status: string;
  published_at: string | null;
  created_at: string;
}

export interface PolicyProfile {
  id: string;
  name: string;
  description: string | null;
  rules: any;
  is_default: boolean;
  created_at: string;
}

export interface BudgetProfile {
  id: string;
  name: string;
  max_run_cost: number | null;
  soft_limit: number | null;
  hard_limit: number | null;
  is_default: boolean;
  created_at: string;
}

export interface RunLiveState {
  run_id: string;
  run_status: string;
  started_at: string | null;
  estimated_cost: number | null;
  actual_cost: number;
  nodes_total: number;
  nodes_by_status: Record<string, number>;
  nodes: { id: string; node_ref: string; node_type: string; status: string; order_index: number }[];
  agent_invocations: number;
  agent_invocations_cost: number;
  mcp_invocations: number;
  mcp_invocations_cost: number;
  control_decisions: number;
  control_denials: number;
}

export interface PlatformMetrics {
  runs_by_status: Record<string, number>;
  total_runs: number;
  total_agent_cost: number;
  total_mcp_cost: number;
  total_cost: number;
  control_decisions_by_type: Record<string, number>;
  audit_events_total: number;
}
