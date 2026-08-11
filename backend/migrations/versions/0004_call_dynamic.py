"""Add dynamic flag to calls.

Revision ID: 0004_call_dynamic
Revises: 0003_language_counts
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_call_dynamic"
down_revision = "0003_language_counts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calls",
        sa.Column(
            "dynamic",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("calls", "dynamic")
