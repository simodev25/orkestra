"""Add namespaces table and agent namespace scoping.

Revision ID: 022
Revises: 021
"""

import sqlalchemy as sa
from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


DEFAULT_NAMESPACE_ID = "b536d855-6f6a-573c-8a75-99d5631a91f9"
DEFAULT_NAMESPACE_NAME = "Default"
DEFAULT_NAMESPACE_SLUG = "default"
DEFAULT_NAMESPACE_DESCRIPTION = "System default namespace"


def upgrade() -> None:
    op.create_table(
        "namespaces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=63), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )

    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            INSERT INTO namespaces (id, name, slug, description)
            VALUES (:id, :name, :slug, :description)
            ON CONFLICT (slug) DO NOTHING
            """
        ),
        {
            "id": DEFAULT_NAMESPACE_ID,
            "name": DEFAULT_NAMESPACE_NAME,
            "slug": DEFAULT_NAMESPACE_SLUG,
            "description": DEFAULT_NAMESPACE_DESCRIPTION,
        },
    )

    op.add_column(
        "agent_definitions",
        sa.Column("namespace_id", sa.String(length=36), nullable=True),
    )

    op.create_foreign_key(
        "fk_agent_definitions_namespace_id",
        "agent_definitions",
        "namespaces",
        ["namespace_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    bind.execute(
        sa.text(
            """
            UPDATE agent_definitions
            SET namespace_id = :default_id
            WHERE namespace_id IS NULL
            """
        ),
        {"default_id": DEFAULT_NAMESPACE_ID},
    )

    op.alter_column(
        "agent_definitions",
        "namespace_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )

    op.create_index(
        "ix_agent_definitions_namespace_id",
        "agent_definitions",
        ["namespace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_definitions_namespace_id", table_name="agent_definitions")
    op.drop_constraint("fk_agent_definitions_namespace_id", "agent_definitions", type_="foreignkey")
    op.drop_column("agent_definitions", "namespace_id")
    op.drop_table("namespaces")
