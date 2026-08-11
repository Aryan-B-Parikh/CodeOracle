"""Entities, calls, imports.

Revision ID: 0002_entities
Revises: 0001_initial
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_entities"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

JSONB_VARIANT = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("signature", sa.String(length=500), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("complexity", sa.Integer(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("docstring", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB_VARIANT, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_entities_file_id"), "entities", ["file_id"])
    op.create_index(op.f("ix_entities_repository_id"), "entities", ["repository_id"])

    op.create_table(
        "calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("caller_id", sa.Uuid(), nullable=True),
        sa.Column("callee_id", sa.Uuid(), nullable=True),
        sa.Column("callee_name", sa.String(length=255), nullable=False),
        sa.Column("call_line", sa.Integer(), nullable=False),
        sa.Column("external", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["callee_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["caller_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_calls_callee_id"), "calls", ["callee_id"])
    op.create_index(op.f("ix_calls_caller_id"), "calls", ["caller_id"])
    op.create_index(op.f("ix_calls_repository_id"), "calls", ["repository_id"])

    op.create_table(
        "imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("module", sa.String(length=255), nullable=False),
        sa.Column("local_name", sa.String(length=255), nullable=True),
        sa.Column("is_external", sa.Boolean(), nullable=False),
        sa.Column("line", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_imports_file_id"), "imports", ["file_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_imports_file_id"), table_name="imports")
    op.drop_table("imports")
    op.drop_index(op.f("ix_calls_callee_id"), table_name="calls")
    op.drop_index(op.f("ix_calls_caller_id"), table_name="calls")
    op.drop_index(op.f("ix_calls_repository_id"), table_name="calls")
    op.drop_table("calls")
    op.drop_index(op.f("ix_entities_repository_id"), table_name="entities")
    op.drop_index(op.f("ix_entities_file_id"), table_name="entities")
    op.drop_table("entities")
