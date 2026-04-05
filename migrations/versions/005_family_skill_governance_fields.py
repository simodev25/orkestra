"""Add governance fields to families and skills, soul_content to agents.

Revision ID: 005
Revises: 004
Create Date: 2026-04-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Family: add governance + prompt fields
    op.add_column("family_definitions", sa.Column("default_system_rules", JSONB(), nullable=False, server_default="[]"))
    op.add_column("family_definitions", sa.Column("default_forbidden_effects", JSONB(), nullable=False, server_default="[]"))
    op.add_column("family_definitions", sa.Column("default_output_expectations", JSONB(), nullable=False, server_default="[]"))
    op.add_column("family_definitions", sa.Column("version", sa.String(20), nullable=False, server_default="1.0.0"))
    op.add_column("family_definitions", sa.Column("status", sa.String(20), nullable=False, server_default="active"))
    op.add_column("family_definitions", sa.Column("owner", sa.String(100), nullable=True))

    # Skill: add governance fields
    op.add_column("skill_definitions", sa.Column("version", sa.String(20), nullable=False, server_default="1.0.0"))
    op.add_column("skill_definitions", sa.Column("status", sa.String(20), nullable=False, server_default="active"))
    op.add_column("skill_definitions", sa.Column("owner", sa.String(100), nullable=True))

    # Agent: add soul_content
    op.add_column("agent_definitions", sa.Column("soul_content", sa.Text(), nullable=True))

    # Now update existing families from seed data if available
    import json
    import os
    config_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "app", "config"))
    families_path = os.path.join(config_dir, "families.seed.json")

    if os.path.exists(families_path):
        with open(families_path, encoding="utf-8") as f:
            data = json.load(f)

        conn = op.get_bind()
        for fam in data.get("families", []):
            conn.execute(
                sa.text(
                    "UPDATE family_definitions SET "
                    "default_system_rules = CAST(:rules AS jsonb), "
                    "default_forbidden_effects = CAST(:effects AS jsonb), "
                    "default_output_expectations = CAST(:expectations AS jsonb), "
                    "version = :version, status = :status, owner = :owner "
                    "WHERE id = :id"
                ),
                {
                    "id": fam["family_id"],
                    "rules": json.dumps(fam.get("default_system_rules", [])),
                    "effects": json.dumps(fam.get("default_forbidden_effects", [])),
                    "expectations": json.dumps(fam.get("default_output_expectations", [])),
                    "version": fam.get("version", "1.0.0"),
                    "status": fam.get("status", "active"),
                    "owner": fam.get("owner"),
                },
            )

    # Update existing skills from seed
    skills_path = os.path.join(config_dir, "skills.seed.json")
    if os.path.exists(skills_path):
        with open(skills_path, encoding="utf-8") as f:
            data = json.load(f)

        conn = op.get_bind()
        for skill in data.get("skills", []):
            conn.execute(
                sa.text(
                    "UPDATE skill_definitions SET "
                    "version = :version, status = :status, owner = :owner "
                    "WHERE id = :id"
                ),
                {
                    "id": skill["skill_id"],
                    "version": skill.get("version", "1.0.0"),
                    "status": skill.get("status", "active"),
                    "owner": skill.get("owner"),
                },
            )


def downgrade() -> None:
    op.drop_column("agent_definitions", "soul_content")
    op.drop_column("skill_definitions", "owner")
    op.drop_column("skill_definitions", "status")
    op.drop_column("skill_definitions", "version")
    op.drop_column("family_definitions", "owner")
    op.drop_column("family_definitions", "status")
    op.drop_column("family_definitions", "version")
    op.drop_column("family_definitions", "default_output_expectations")
    op.drop_column("family_definitions", "default_forbidden_effects")
    op.drop_column("family_definitions", "default_system_rules")
