"""Add calling_agent_id to mcp_invocations and config to runs.

Revision ID: 020
Revises: 019
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mcp_invocations",
        sa.Column("calling_agent_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "runs",
        sa.Column("config", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mcp_invocations", "calling_agent_id")
    op.drop_column("runs", "config")
