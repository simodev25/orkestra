"""Add Orkestra MCP bindings table.

Revision ID: 002
Revises: 001
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orkestra_mcp_bindings",
        sa.Column("obot_server_id", sa.String(120), primary_key=True),
        sa.Column("obot_server_name", sa.String(255), nullable=False),
        sa.Column("enabled_in_orkestra", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("hidden_from_catalog", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("allowed_agent_families", JSONB, nullable=True),
        sa.Column("allowed_workflows", JSONB, nullable=True),
        sa.Column("business_domain", sa.String(120), nullable=True),
        sa.Column("risk_level_override", sa.String(20), nullable=True),
        sa.Column("preferred_use_cases", JSONB, nullable=True),
        sa.Column("hidden_from_ai_generator", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("orkestra_mcp_bindings")
