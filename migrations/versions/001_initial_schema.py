"""Initial schema — all 17 Orkestra domain entities.

Revision ID: 001
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- requests ----
    op.create_table(
        "requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, server_default="default"),
        sa.Column("created_by", sa.String(100), nullable=False, server_default="system"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("request_text", sa.Text, nullable=False),
        sa.Column("use_case", sa.String(100), nullable=True),
        sa.Column("workflow_template_id", sa.String(36), nullable=True),
        sa.Column("criticality", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("input_mode", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("attachments_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_requests_status", "requests", ["status"])
    op.create_index("ix_requests_criticality", "requests", ["criticality"])
    op.create_index("ix_requests_created_at", "requests", ["created_at"])

    # ---- cases ----
    op.create_table(
        "cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False, server_default="default"),
        sa.Column("case_type", sa.String(100), nullable=True),
        sa.Column("business_context", sa.Text, nullable=True),
        sa.Column("criticality", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(30), nullable=False, server_default="created"),
        sa.Column("current_run_id", sa.String(36), nullable=True),
        sa.Column("document_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_cases_status", "cases", ["status"])
    op.create_index("ix_cases_request_id", "cases", ["request_id"])

    # ---- workflow_definitions ----
    op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0.0"),
        sa.Column("use_case", sa.String(100), nullable=True),
        sa.Column("execution_mode", sa.String(30), nullable=False, server_default="sequential"),
        sa.Column("graph_definition", JSONB, nullable=True),
        sa.Column("policy_profile_id", sa.String(36), nullable=True),
        sa.Column("budget_profile_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ---- orchestration_plans ----
    op.create_table(
        "orchestration_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=True),
        sa.Column("workflow_id", sa.String(36), nullable=True),
        sa.Column("workflow_version", sa.String(20), nullable=True),
        sa.Column("objective_summary", sa.Text, nullable=True),
        sa.Column("selected_agents", JSONB, nullable=True),
        sa.Column("selected_mcps", JSONB, nullable=True),
        sa.Column("execution_topology", JSONB, nullable=True),
        sa.Column("estimated_cost", sa.Float, nullable=True),
        sa.Column("estimated_parallelism", sa.Integer, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(100), nullable=False, server_default="orchestrator"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_plans_case_id", "orchestration_plans", ["case_id"])
    op.create_index("ix_plans_status", "orchestration_plans", ["status"])

    # ---- runs ----
    op.create_table(
        "runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), nullable=False),
        sa.Column("plan_id", sa.String(36), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="created"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_cost", sa.Float, nullable=True),
        sa.Column("actual_cost", sa.Float, nullable=False, server_default="0"),
        sa.Column("approval_state", sa.String(30), nullable=True),
        sa.Column("replay_status", sa.String(30), nullable=True),
        sa.Column("final_output", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_runs_case_id", "runs", ["case_id"])
    op.create_index("ix_runs_status", "runs", ["status"])
    op.create_index("ix_runs_created_at", "runs", ["created_at"])

    # ---- run_nodes ----
    op.create_table(
        "run_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("node_type", sa.String(30), nullable=False, server_default="subagent"),
        sa.Column("node_ref", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("depends_on", JSONB, nullable=True),
        sa.Column("parallel_group", sa.String(100), nullable=True),
        sa.Column("trigger_condition", JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_run_nodes_run_id", "run_nodes", ["run_id"])
    op.create_index("ix_run_nodes_status", "run_nodes", ["status"])

    # ---- subagent_invocations ----
    op.create_table(
        "subagent_invocations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("run_node_id", sa.String(36), nullable=False),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("agent_version", sa.String(20), nullable=True),
        sa.Column("prompt_version", sa.String(20), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("input_summary", sa.Text, nullable=True),
        sa.Column("output_summary", sa.Text, nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("cost", sa.Float, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("result_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_subagent_inv_run_id", "subagent_invocations", ["run_id"])

    # ---- mcp_invocations ----
    op.create_table(
        "mcp_invocations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("subagent_invocation_id", sa.String(36), nullable=True),
        sa.Column("mcp_id", sa.String(100), nullable=False),
        sa.Column("mcp_version", sa.String(20), nullable=True),
        sa.Column("effect_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="requested"),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("cost", sa.Float, nullable=False, server_default="0"),
        sa.Column("input_fingerprint", sa.String(255), nullable=True),
        sa.Column("output_summary", sa.Text, nullable=True),
        sa.Column("approval_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_mcp_inv_run_id", "mcp_invocations", ["run_id"])

    # ---- control_decisions ----
    op.create_table(
        "control_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("decision_scope", sa.String(30), nullable=False),
        sa.Column("decision_type", sa.String(30), nullable=False),
        sa.Column("policy_rule_id", sa.String(100), nullable=True),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("target_ref", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_control_dec_run_id", "control_decisions", ["run_id"])
    op.create_index("ix_control_dec_type", "control_decisions", ["decision_type"])

    # ---- approval_requests ----
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("case_id", sa.String(36), nullable=False),
        sa.Column("approval_type", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("reviewer_role", sa.String(50), nullable=True),
        sa.Column("assigned_to", sa.String(100), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="requested"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_approvals_status", "approval_requests", ["status"])
    op.create_index("ix_approvals_run_id", "approval_requests", ["run_id"])

    # ---- audit_events ----
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor_type", sa.String(50), nullable=False),
        sa.Column("actor_ref", sa.String(100), nullable=False),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_run_id", "audit_events", ["run_id"])
    op.create_index("ix_audit_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_timestamp", "audit_events", ["timestamp"])

    # ---- evidence_records ----
    op.create_table(
        "evidence_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_ref", sa.String(100), nullable=False),
        sa.Column("linked_entity_type", sa.String(50), nullable=True),
        sa.Column("linked_entity_ref", sa.String(100), nullable=True),
        sa.Column("evidence_strength", sa.String(20), nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evidence_run_id", "evidence_records", ["run_id"])

    # ---- replay_bundles ----
    op.create_table(
        "replay_bundles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("bundle_status", sa.String(30), nullable=False, server_default="not_generated"),
        sa.Column("storage_ref", sa.String(500), nullable=True),
        sa.Column("generated_by", sa.String(100), nullable=True),
        sa.Column("replayable", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("replay_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_replay_run_id", "replay_bundles", ["run_id"])

    # ---- agent_definitions ----
    op.create_table(
        "agent_definitions",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("family", sa.String(50), nullable=False),
        sa.Column("purpose", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("skills", JSONB, nullable=True),
        sa.Column("selection_hints", JSONB, nullable=True),
        sa.Column("allowed_mcps", JSONB, nullable=True),
        sa.Column("forbidden_effects", JSONB, nullable=True),
        sa.Column("input_contract_ref", sa.String(255), nullable=True),
        sa.Column("output_contract_ref", sa.String(255), nullable=True),
        sa.Column("criticality", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("cost_profile", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("limitations", JSONB, nullable=True),
        sa.Column("prompt_ref", sa.String(255), nullable=True),
        sa.Column("skills_ref", sa.String(255), nullable=True),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0.0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("owner", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agents_status", "agent_definitions", ["status"])
    op.create_index("ix_agents_family", "agent_definitions", ["family"])

    # ---- mcp_definitions ----
    op.create_table(
        "mcp_definitions",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("purpose", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("effect_type", sa.String(30), nullable=False),
        sa.Column("input_contract_ref", sa.String(255), nullable=True),
        sa.Column("output_contract_ref", sa.String(255), nullable=True),
        sa.Column("allowed_agents", JSONB, nullable=True),
        sa.Column("criticality", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="30"),
        sa.Column("retry_policy", sa.String(30), nullable=False, server_default="standard"),
        sa.Column("cost_profile", sa.String(20), nullable=False, server_default="low"),
        sa.Column("approval_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("audit_required", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0.0"),
        sa.Column("owner", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_mcps_status", "mcp_definitions", ["status"])
    op.create_index("ix_mcps_effect_type", "mcp_definitions", ["effect_type"])

    # ---- policy_profiles ----
    op.create_table(
        "policy_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("rules", JSONB, nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ---- budget_profiles ----
    op.create_table(
        "budget_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("max_run_cost", sa.Float, nullable=True),
        sa.Column("max_agent_cost", sa.Float, nullable=True),
        sa.Column("max_mcp_cost", sa.Float, nullable=True),
        sa.Column("soft_limit", sa.Float, nullable=True),
        sa.Column("hard_limit", sa.Float, nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("budget_profiles")
    op.drop_table("policy_profiles")
    op.drop_table("mcp_definitions")
    op.drop_table("agent_definitions")
    op.drop_table("replay_bundles")
    op.drop_table("evidence_records")
    op.drop_table("audit_events")
    op.drop_table("approval_requests")
    op.drop_table("control_decisions")
    op.drop_table("mcp_invocations")
    op.drop_table("subagent_invocations")
    op.drop_table("run_nodes")
    op.drop_table("runs")
    op.drop_table("orchestration_plans")
    op.drop_table("workflow_definitions")
    op.drop_table("cases")
    op.drop_table("requests")
