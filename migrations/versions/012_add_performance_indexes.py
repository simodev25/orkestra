"""Add performance indexes for common query patterns.

Revision ID: 012
Revises: 011
"""

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_subagent_inv_agent_id", "subagent_invocations", ["agent_id"])
    op.create_index("ix_subagent_inv_status", "subagent_invocations", ["status"])
    op.create_index("ix_mcp_inv_mcp_id", "mcp_invocations", ["mcp_id"])
    op.create_index("ix_mcp_inv_status", "mcp_invocations", ["status"])
    op.create_index("ix_cases_tenant_id", "cases", ["tenant_id"])
    op.create_index("ix_requests_tenant_id", "requests", ["tenant_id"])
    op.create_index("ix_approval_requests_case_id", "approval_requests", ["case_id"])
    op.create_index("ix_run_nodes_run_status", "run_nodes", ["run_id", "status"])
    op.create_index("ix_audit_events_run_type", "audit_events", ["run_id", "event_type"])
    op.create_index("ix_agent_test_runs_agent_created", "agent_test_runs", ["agent_id", "created_at"])
    op.create_index("ix_test_runs_scenario_status", "test_runs", ["scenario_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_test_runs_scenario_status", "test_runs")
    op.drop_index("ix_agent_test_runs_agent_created", "agent_test_runs")
    op.drop_index("ix_audit_events_run_type", "audit_events")
    op.drop_index("ix_run_nodes_run_status", "run_nodes")
    op.drop_index("ix_approval_requests_case_id", "approval_requests")
    op.drop_index("ix_requests_tenant_id", "requests")
    op.drop_index("ix_cases_tenant_id", "cases")
    op.drop_index("ix_mcp_inv_status", "mcp_invocations")
    op.drop_index("ix_mcp_inv_mcp_id", "mcp_invocations")
    op.drop_index("ix_subagent_inv_status", "subagent_invocations")
    op.drop_index("ix_subagent_inv_agent_id", "subagent_invocations")
