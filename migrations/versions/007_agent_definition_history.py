"""Add agent_definition_history table.

Revision ID: 007
Revises: 006
Create Date: 2026-04-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_definition_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_id", sa.String(100), sa.ForeignKey("agent_definitions.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("family_id", sa.String(50), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("skill_ids_snapshot", JSONB(), nullable=False, server_default="[]"),
        sa.Column("prompt_content", sa.Text(), nullable=True),
        sa.Column("skills_content", sa.Text(), nullable=True),
        sa.Column("soul_content", sa.Text(), nullable=True),
        sa.Column("selection_hints", JSONB(), nullable=True),
        sa.Column("allowed_mcps", JSONB(), nullable=True),
        sa.Column("forbidden_effects", JSONB(), nullable=True),
        sa.Column("limitations", JSONB(), nullable=True),
        sa.Column("criticality", sa.String(20), nullable=False),
        sa.Column("cost_profile", sa.String(20), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("owner", sa.String(100), nullable=True),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("original_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("agent_definition_history")
