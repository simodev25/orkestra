"""Add llm_provider and llm_model to agent_definitions.

Revision ID: 008
Revises: 007
Create Date: 2026-04-05
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_definitions", sa.Column("llm_provider", sa.String(30), nullable=True))
    op.add_column("agent_definitions", sa.Column("llm_model", sa.String(100), nullable=True))
    op.add_column("agent_definition_history", sa.Column("llm_provider", sa.String(30), nullable=True))
    op.add_column("agent_definition_history", sa.Column("llm_model", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_definitions", "llm_model")
    op.drop_column("agent_definitions", "llm_provider")
    op.drop_column("agent_definition_history", "llm_model")
    op.drop_column("agent_definition_history", "llm_provider")
