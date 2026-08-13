"""Add tested_proposal_id column to test_runs table.

Revision ID: 0012_test_run_proposal_binding
Revises: 0011_refactor_proposals
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0012_test_run_proposal_binding"
down_revision = "0011_refactor_proposals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "test_runs",
        sa.Column("tested_proposal_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        op.f("ix_test_runs_tested_proposal_id"),
        "test_runs",
        ["tested_proposal_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_test_runs_tested_proposal_id_refactor_proposals",
        "test_runs",
        "refactor_proposals",
        ["tested_proposal_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_test_runs_tested_proposal_id_refactor_proposals",
        "test_runs",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_test_runs_tested_proposal_id"),
        table_name="test_runs",
    )
    op.drop_column("test_runs", "tested_proposal_id")
