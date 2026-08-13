"""Semantic chunks (module/class/function) with embeddings.

Revision ID: 0007_chunks
Revises: 0006_analyses
Create Date: 2026-08-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_chunks"
down_revision = "0006_analyses"
branch_labels = None
depends_on = None

JSONB_VARIANT = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("qualified_name", sa.String(length=500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", JSONB_VARIANT, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chunks_entity_id"), "chunks", ["entity_id"])
    op.create_index(op.f("ix_chunks_file_id"), "chunks", ["file_id"])
    op.create_index(op.f("ix_chunks_repository_id"), "chunks", ["repository_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_chunks_repository_id"), table_name="chunks")
    op.drop_index(op.f("ix_chunks_file_id"), table_name="chunks")
    op.drop_index(op.f("ix_chunks_entity_id"), table_name="chunks")
    op.drop_table("chunks")