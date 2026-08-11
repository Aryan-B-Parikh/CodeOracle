"""Add language_counts to repositories.

Revision ID: 0003_language_counts
Revises: 0002_entities
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_language_counts"
down_revision = "0002_entities"
branch_labels = None
depends_on = None

JSONB_VARIANT = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column(
            "language_counts",
            JSONB_VARIANT,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("repositories", "language_counts")
