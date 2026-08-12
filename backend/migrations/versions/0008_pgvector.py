"""Production pgvector: real vector column + HNSW cosine index + embedding cache.

Revision ID: 0008_pgvector
Revises: 0007_chunks
Create Date: 2026-08-12

Requires the ``vector`` extension (created idempotently here) and the ``pgvector``
Python package. The dim must match ``EMBEDDING_DIMENSIONS`` (default 256).
"""

import os

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0008_pgvector"
down_revision = "0007_chunks"
branch_labels = None
depends_on = None

_EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "256"))

JSONB_VARIANT = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.alter_column(
        "chunks",
        "embedding",
        type_=Vector(_EMBEDDING_DIMENSIONS),
        postgresql_using="embedding::text::vector",
    )
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "embedding_cache",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", JSONB_VARIANT, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "model", "dimensions", "content_hash", name="uq_embcache_key"
        ),
    )
    op.create_index(
        op.f("ix_embedding_cache_content_hash"), "embedding_cache", ["content_hash"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_embedding_cache_content_hash"), table_name="embedding_cache")
    op.drop_table("embedding_cache")
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    op.alter_column(
        "chunks",
        "embedding",
        type_=JSONB_VARIANT,
        postgresql_using="embedding::text::jsonb",
    )