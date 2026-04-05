"""Add version history tables for families and skills.

Revision ID: 006
Revises: 005
Create Date: 2026-04-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "family_definition_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("family_id", sa.String(50), sa.ForeignKey("family_definitions.id"), nullable=False, index=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_system_rules", JSONB(), nullable=False, server_default="[]"),
        sa.Column("default_forbidden_effects", JSONB(), nullable=False, server_default="[]"),
        sa.Column("default_output_expectations", JSONB(), nullable=False, server_default="[]"),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("owner", sa.String(100), nullable=True),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("original_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "skill_definition_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("skill_id", sa.String(100), sa.ForeignKey("skill_definitions.id"), nullable=False, index=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("behavior_templates", JSONB(), nullable=False, server_default="[]"),
        sa.Column("output_guidelines", JSONB(), nullable=False, server_default="[]"),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("owner", sa.String(100), nullable=True),
        sa.Column("allowed_families_snapshot", JSONB(), nullable=False, server_default="[]"),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("original_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("skill_definition_history")
    op.drop_table("family_definition_history")
