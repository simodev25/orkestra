"""Add foreign key constraints on operational tables.

Revision ID: 011
Revises: 010
"""

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cases -> Requests
    op.create_foreign_key("fk_cases_request_id", "cases", "requests",
                          ["request_id"], ["id"], ondelete="SET NULL")
    # Runs -> Cases
    op.create_foreign_key("fk_runs_case_id", "runs", "cases",
                          ["case_id"], ["id"], ondelete="CASCADE")
    # RunNodes -> Runs
    op.create_foreign_key("fk_run_nodes_run_id", "run_nodes", "runs",
                          ["run_id"], ["id"], ondelete="CASCADE")
    # SubagentInvocations -> RunNodes
    op.create_foreign_key("fk_subagent_inv_run_node_id", "subagent_invocations", "run_nodes",
                          ["run_node_id"], ["id"], ondelete="CASCADE")
    # MCPInvocations -> SubagentInvocations
    op.create_foreign_key("fk_mcp_inv_subagent_id", "mcp_invocations", "subagent_invocations",
                          ["subagent_invocation_id"], ["id"], ondelete="CASCADE")
    # AuditEvents -> Runs (nullable)
    op.create_foreign_key("fk_audit_events_run_id", "audit_events", "runs",
                          ["run_id"], ["id"], ondelete="SET NULL")
    # TestRuns -> TestScenarios
    op.create_foreign_key("fk_test_runs_scenario_id", "test_runs", "test_scenarios",
                          ["scenario_id"], ["id"], ondelete="SET NULL")
    # TestRuns -> AgentDefinitions
    op.create_foreign_key("fk_test_runs_agent_id", "test_runs", "agent_definitions",
                          ["agent_id"], ["id"], ondelete="CASCADE")
    # TestRunEvents -> TestRuns
    op.create_foreign_key("fk_test_run_events_run_id", "test_run_events", "test_runs",
                          ["run_id"], ["id"], ondelete="CASCADE")
    # TestRunAssertions -> TestRuns
    op.create_foreign_key("fk_test_run_assertions_run_id", "test_run_assertions", "test_runs",
                          ["run_id"], ["id"], ondelete="CASCADE")
    # TestRunDiagnostics -> TestRuns
    op.create_foreign_key("fk_test_run_diagnostics_run_id", "test_run_diagnostics", "test_runs",
                          ["run_id"], ["id"], ondelete="CASCADE")
    # AgentTestRuns -> AgentDefinitions
    op.create_foreign_key("fk_agent_test_runs_agent_id", "agent_test_runs", "agent_definitions",
                          ["agent_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint("fk_agent_test_runs_agent_id", "agent_test_runs", type_="foreignkey")
    op.drop_constraint("fk_test_run_diagnostics_run_id", "test_run_diagnostics", type_="foreignkey")
    op.drop_constraint("fk_test_run_assertions_run_id", "test_run_assertions", type_="foreignkey")
    op.drop_constraint("fk_test_run_events_run_id", "test_run_events", type_="foreignkey")
    op.drop_constraint("fk_test_runs_agent_id", "test_runs", type_="foreignkey")
    op.drop_constraint("fk_test_runs_scenario_id", "test_runs", type_="foreignkey")
    op.drop_constraint("fk_audit_events_run_id", "audit_events", type_="foreignkey")
    op.drop_constraint("fk_mcp_inv_subagent_id", "mcp_invocations", type_="foreignkey")
    op.drop_constraint("fk_subagent_inv_run_node_id", "subagent_invocations", type_="foreignkey")
    op.drop_constraint("fk_run_nodes_run_id", "run_nodes", type_="foreignkey")
    op.drop_constraint("fk_runs_case_id", "runs", type_="foreignkey")
    op.drop_constraint("fk_cases_request_id", "cases", type_="foreignkey")
