"""Make per-testcase coverage lines nullable (measured data only, never fabricated).

Revision ID: 0010_test_case_metrics
Revises: 0009_test_runs
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_test_case_metrics"
down_revision = "0009_test_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("test_cases") as batch_op:
        batch_op.alter_column(
            "coverage_line_nums",
            existing_type=sa.JSON(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("test_cases") as batch_op:
        batch_op.alter_column(
            "coverage_line_nums",
            existing_type=sa.JSON(),
            nullable=False,
        )