"""Add governance fields for Agent Registry and AI draft flow.

Revision ID: 003
Revises: 002
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_definitions", sa.Column("prompt_content", sa.Text(), nullable=True))
    op.add_column("agent_definitions", sa.Column("skills_content", sa.Text(), nullable=True))
    op.add_column(
        "agent_definitions",
        sa.Column("last_test_status", sa.String(length=30), nullable=False, server_default="not_tested"),
    )
    op.add_column("agent_definitions", sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "agent_definitions",
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("agent_definitions", "usage_count")
    op.drop_column("agent_definitions", "last_validated_at")
    op.drop_column("agent_definitions", "last_test_status")
    op.drop_column("agent_definitions", "skills_content")
    op.drop_column("agent_definitions", "prompt_content")
