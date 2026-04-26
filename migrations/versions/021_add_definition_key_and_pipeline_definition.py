"""Add definition_key and pipeline_definition for GH-14.

Revision ID: 021
Revises: 020
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "test_scenarios",
        sa.Column("definition_key", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ux_test_scenarios_definition_key",
        "test_scenarios",
        ["definition_key"],
        unique=True,
    )

    op.add_column(
        "agent_definitions",
        sa.Column("pipeline_definition", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_definitions", "pipeline_definition")
    op.drop_index("ux_test_scenarios_definition_key", table_name="test_scenarios")
    op.drop_column("test_scenarios", "definition_key")
