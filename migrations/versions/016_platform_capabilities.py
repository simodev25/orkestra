"""Add platform_capabilities table for global feature toggles.

Revision ID: 016
Revises: 015
"""

import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_capabilities",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    # Default: code execution disabled platform-wide
    op.execute(
        "INSERT INTO platform_capabilities (key, value) VALUES ('code_execution_enabled', 'false')"
    )


def downgrade() -> None:
    op.drop_table("platform_capabilities")
