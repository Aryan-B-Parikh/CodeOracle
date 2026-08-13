"""Analysis pipeline rows (per-stage progress for the live pipeline UI).

Revision ID: 0006_analyses
Revises: 0005_inheritances
Create Date: 2026-08-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_analyses"
down_revision = "0005_inheritances"
branch_labels = None
depends_on = None

JSONB_VARIANT = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("pipeline_state", JSONB_VARIANT, nullable=True),
        sa.Column("summary", JSONB_VARIANT, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analyses_repository_id"), "analyses", ["repository_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_analyses_repository_id"), table_name="analyses")
    op.drop_table("analyses")