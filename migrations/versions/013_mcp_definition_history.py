"""Add mcp_definition_history table for audit trail.

Revision ID: 013
Revises: 012
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_definition_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("mcp_id", sa.String(100), sa.ForeignKey("mcp_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.String(20), nullable=True),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_mcp_definition_history_mcp_id", "mcp_definition_history", ["mcp_id"])


def downgrade() -> None:
    op.drop_index("ix_mcp_definition_history_mcp_id", "mcp_definition_history")
    op.drop_table("mcp_definition_history")
