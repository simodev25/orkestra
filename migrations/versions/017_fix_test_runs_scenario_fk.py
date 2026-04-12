"""Fix test_runs.scenario_id FK: SET NULL → CASCADE.

The column is NOT NULL so SET NULL fails on scenario delete.
CASCADE is correct: deleting a scenario deletes its runs.

Revision ID: 017
Revises: 016
"""

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("fk_test_runs_scenario_id", "test_runs", type_="foreignkey")
    op.create_foreign_key(
        "fk_test_runs_scenario_id",
        "test_runs",
        "test_scenarios",
        ["scenario_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_test_runs_scenario_id", "test_runs", type_="foreignkey")
    op.create_foreign_key(
        "fk_test_runs_scenario_id",
        "test_runs",
        "test_scenarios",
        ["scenario_id"],
        ["id"],
        ondelete="SET NULL",
    )
