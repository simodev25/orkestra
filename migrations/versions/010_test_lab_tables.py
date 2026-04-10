"""Add test lab tables.

Revision ID: 010
Revises: 009
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- test_scenarios ----
    op.create_table(
        "test_scenarios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("input_prompt", sa.Text, nullable=False),
        sa.Column("input_payload", JSONB, nullable=True),
        sa.Column("allowed_tools", JSONB, nullable=True),
        sa.Column("expected_tools", JSONB, nullable=True),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="120"),
        sa.Column("max_iterations", sa.Integer, nullable=False, server_default="5"),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("assertions", JSONB, nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_test_scenarios_agent_id", "test_scenarios", ["agent_id"])

    # ---- test_runs ----
    op.create_table(
        "test_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scenario_id", sa.String(36), nullable=False),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("agent_version", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("verdict", sa.String(30), nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("final_output", sa.Text, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("execution_metadata", JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_test_runs_scenario_id", "test_runs", ["scenario_id"])
    op.create_index("ix_test_runs_agent_id", "test_runs", ["agent_id"])
    op.create_index("ix_test_runs_status", "test_runs", ["status"])

    # ---- test_run_events ----
    op.create_table(
        "test_run_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("phase", sa.String(50), nullable=True),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_test_run_events_run_id", "test_run_events", ["run_id"])
    op.create_index("ix_test_run_events_event_type", "test_run_events", ["event_type"])

    # ---- test_run_assertions ----
    op.create_table(
        "test_run_assertions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("assertion_type", sa.String(50), nullable=False),
        sa.Column("target", sa.String(255), nullable=True),
        sa.Column("expected", sa.Text, nullable=True),
        sa.Column("actual", sa.Text, nullable=True),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("critical", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_test_run_assertions_run_id", "test_run_assertions", ["run_id"])

    # ---- test_run_diagnostics ----
    op.create_table(
        "test_run_diagnostics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("probable_causes", JSONB, nullable=True),
        sa.Column("recommendation", sa.Text, nullable=True),
        sa.Column("evidence", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_test_run_diagnostics_run_id", "test_run_diagnostics", ["run_id"])

    # ---- agent_test_runs ----
    op.create_table(
        "agent_test_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("agent_version", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("verdict", sa.String(10), nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("raw_output", sa.Text, nullable=False, server_default=""),
        sa.Column("task", sa.Text, nullable=False, server_default=""),
        sa.Column("token_usage", sa.JSON, nullable=True),
        sa.Column("behavioral_checks", sa.JSON, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("trace_data", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agent_test_runs_agent_id", "agent_test_runs", ["agent_id"])
    op.create_index("ix_agent_test_runs_status", "agent_test_runs", ["status"])
    op.create_index("ix_agent_test_runs_created_at", "agent_test_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_test_runs_created_at", table_name="agent_test_runs")
    op.drop_index("ix_agent_test_runs_status", table_name="agent_test_runs")
    op.drop_index("ix_agent_test_runs_agent_id", table_name="agent_test_runs")
    op.drop_table("agent_test_runs")

    op.drop_index("ix_test_run_diagnostics_run_id", table_name="test_run_diagnostics")
    op.drop_table("test_run_diagnostics")

    op.drop_index("ix_test_run_assertions_run_id", table_name="test_run_assertions")
    op.drop_table("test_run_assertions")

    op.drop_index("ix_test_run_events_event_type", table_name="test_run_events")
    op.drop_index("ix_test_run_events_run_id", table_name="test_run_events")
    op.drop_table("test_run_events")

    op.drop_index("ix_test_runs_status", table_name="test_runs")
    op.drop_index("ix_test_runs_agent_id", table_name="test_runs")
    op.drop_index("ix_test_runs_scenario_id", table_name="test_runs")
    op.drop_table("test_runs")

    op.drop_index("ix_test_scenarios_agent_id", table_name="test_scenarios")
    op.drop_table("test_scenarios")
