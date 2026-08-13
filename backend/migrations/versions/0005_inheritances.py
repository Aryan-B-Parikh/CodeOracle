"""Inheritance edges + import kind.

Revision ID: 0005_inheritances
Revises: 0004_call_dynamic
Create Date: 2026-08-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_inheritances"
down_revision = "0004_call_dynamic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "imports",
        sa.Column(
            "kind",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'normal'"),
        ),
    )

    op.create_table(
        "inheritances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("parent_name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("line", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inheritances_entity_id"), "inheritances", ["entity_id"])
    op.create_index(op.f("ix_inheritances_file_id"), "inheritances", ["file_id"])
    op.create_index(op.f("ix_inheritances_parent_id"), "inheritances", ["parent_id"])
    op.create_index(
        op.f("ix_inheritances_repository_id"), "inheritances", ["repository_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_inheritances_repository_id"), table_name="inheritances")
    op.drop_index(op.f("ix_inheritances_parent_id"), table_name="inheritances")
    op.drop_index(op.f("ix_inheritances_file_id"), table_name="inheritances")
    op.drop_index(op.f("ix_inheritances_entity_id"), table_name="inheritances")
    op.drop_table("inheritances")
    op.drop_column("imports", "kind")
