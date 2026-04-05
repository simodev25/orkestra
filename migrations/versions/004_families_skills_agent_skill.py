"""Create family_definitions, skill_definitions, skill_families, agent_skills tables.

Revision ID: 004
Revises: 003
Create Date: 2026-04-05
"""

import json
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# Paths to seed files (relative to repo root, resolved at migration time)
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(__file__)
_CONFIG_DIR = os.path.join(_HERE, "..", "..", "app", "config")
_FAMILIES_SEED = os.path.join(_CONFIG_DIR, "families.seed.json")
_SKILLS_SEED = os.path.join(_CONFIG_DIR, "skills.seed.json")


def _load_json(path: str) -> dict:
    with open(os.path.normpath(path), encoding="utf-8") as fh:
        return json.load(fh)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Create family_definitions
    # ------------------------------------------------------------------
    op.create_table(
        "family_definitions",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ------------------------------------------------------------------
    # 2. Create skill_definitions
    # ------------------------------------------------------------------
    op.create_table(
        "skill_definitions",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("behavior_templates", JSONB, nullable=False, server_default="[]"),
        sa.Column("output_guidelines", JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ------------------------------------------------------------------
    # 3. Create skill_families (join table)
    # ------------------------------------------------------------------
    op.create_table(
        "skill_families",
        sa.Column(
            "skill_id",
            sa.String(100),
            sa.ForeignKey("skill_definitions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "family_id",
            sa.String(50),
            sa.ForeignKey("family_definitions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # ------------------------------------------------------------------
    # 4. Create agent_skills (join table)
    # ------------------------------------------------------------------
    op.create_table(
        "agent_skills",
        sa.Column(
            "agent_id",
            sa.String(100),
            sa.ForeignKey("agent_definitions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "skill_id",
            sa.String(100),
            sa.ForeignKey("skill_definitions.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )

    # ------------------------------------------------------------------
    # 5. Seed family_definitions from families.seed.json
    # ------------------------------------------------------------------
    bind = op.get_bind()
    families_data = _load_json(_FAMILIES_SEED)
    for fam in families_data.get("families", []):
        bind.execute(
            sa.text(
                "INSERT INTO family_definitions (id, label, description) "
                "VALUES (:id, :label, :description) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {
                "id": fam["family_id"],
                "label": fam["label"],
                "description": fam.get("description"),
            },
        )

    # ------------------------------------------------------------------
    # 6. Seed skill_definitions + skill_families from skills.seed.json
    # ------------------------------------------------------------------
    skills_data = _load_json(_SKILLS_SEED)
    for skill in skills_data.get("skills", []):
        bind.execute(
            sa.text(
                "INSERT INTO skill_definitions "
                "(id, label, category, description, behavior_templates, output_guidelines) "
                "VALUES (:id, :label, :category, :description, :bt::jsonb, :og::jsonb) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {
                "id": skill["skill_id"],
                "label": skill["label"],
                "category": skill["category"],
                "description": skill.get("description"),
                "bt": json.dumps(skill.get("behavior_templates", [])),
                "og": json.dumps(skill.get("output_guidelines", [])),
            },
        )
        for fam_id in skill.get("allowed_families", []):
            bind.execute(
                sa.text(
                    "INSERT INTO skill_families (skill_id, family_id) "
                    "VALUES (:skill_id, :family_id) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"skill_id": skill["skill_id"], "family_id": fam_id},
            )

    # ------------------------------------------------------------------
    # 7. Migrate existing agent data: skills JSONB → agent_skills rows
    #    Only inserts rows where the skill_id exists in skill_definitions.
    # ------------------------------------------------------------------
    bind.execute(
        sa.text(
            """
            INSERT INTO agent_skills (agent_id, skill_id)
            SELECT a.id, s.skill_id
            FROM agent_definitions a
            CROSS JOIN LATERAL jsonb_array_elements_text(
                COALESCE(a.skills, '[]'::jsonb)
            ) AS s(skill_id)
            JOIN skill_definitions sd ON sd.id = s.skill_id
            ON CONFLICT DO NOTHING
            """
        )
    )

    # ------------------------------------------------------------------
    # 8. Rename family → family_id on agent_definitions
    #    Then add the FK constraint.
    # ------------------------------------------------------------------
    op.alter_column("agent_definitions", "family", new_column_name="family_id")

    # Ensure every existing agent's family_id value exists in family_definitions
    # (insert a placeholder row if not, so FK addition doesn't fail)
    bind.execute(
        sa.text(
            """
            INSERT INTO family_definitions (id, label)
            SELECT DISTINCT a.family_id, a.family_id
            FROM agent_definitions a
            WHERE NOT EXISTS (
                SELECT 1 FROM family_definitions f WHERE f.id = a.family_id
            )
            ON CONFLICT DO NOTHING
            """
        )
    )

    op.create_foreign_key(
        "fk_agent_definitions_family_id",
        "agent_definitions",
        "family_definitions",
        ["family_id"],
        ["id"],
    )

    # ------------------------------------------------------------------
    # 9. Drop old skills JSONB column from agent_definitions
    # ------------------------------------------------------------------
    op.drop_column("agent_definitions", "skills")


def downgrade() -> None:
    # Restore skills JSONB column
    op.add_column(
        "agent_definitions",
        sa.Column("skills", JSONB, nullable=True),
    )

    # Re-populate skills JSONB from agent_skills rows
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE agent_definitions a
            SET skills = sub.skill_list
            FROM (
                SELECT agent_id, jsonb_agg(skill_id) AS skill_list
                FROM agent_skills
                GROUP BY agent_id
            ) sub
            WHERE a.id = sub.agent_id
            """
        )
    )

    # Drop FK, drop agent_skills join table rows, rename family_id → family
    op.drop_constraint("fk_agent_definitions_family_id", "agent_definitions", type_="foreignkey")
    op.alter_column("agent_definitions", "family_id", new_column_name="family")

    # Drop tables in reverse dependency order
    op.drop_table("agent_skills")
    op.drop_table("skill_families")
    op.drop_table("skill_definitions")
    op.drop_table("family_definitions")
