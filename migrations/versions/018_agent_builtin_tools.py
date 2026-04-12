"""Add allowed_builtin_tools JSONB column to agent_definitions.

Revision ID: 018
Revises: 017
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_definitions",
        sa.Column("allowed_builtin_tools", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_definitions", "allowed_builtin_tools")
