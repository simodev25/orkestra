"""Add pipeline_agent_ids and routing_mode columns to agent_definitions.

Revision ID: 019
Revises: 018
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_definitions",
        sa.Column("pipeline_agent_ids", JSONB, nullable=True, server_default="[]"),
    )
    op.add_column(
        "agent_definitions",
        sa.Column("routing_mode", sa.String(20), nullable=False, server_default="sequential"),
    )


def downgrade() -> None:
    op.drop_column("agent_definitions", "routing_mode")
    op.drop_column("agent_definitions", "pipeline_agent_ids")
