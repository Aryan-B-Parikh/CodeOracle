"""Add refactor_proposals table (T-17 W3 & T-18/T-19).

Revision ID: 0011_refactor_proposals
Revises: 0010_test_case_metrics
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0011_refactor_proposals"
down_revision = "0010_test_case_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refactor_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("entity_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("original", sa.Text(), nullable=False, server_default=""),
        sa.Column("proposed", sa.Text(), nullable=False, server_default=""),
        sa.Column("original_checksum", sa.String(length=64), nullable=False),
        sa.Column(
            "rationale",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(
                sa.JSON(), "sqlite"
            ),
            nullable=True,
        ),
        sa.Column(
            "behavioral_differences",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(
                sa.JSON(), "sqlite"
            ),
            nullable=True,
        ),
        sa.Column("syntax_valid", sa.String(length=8), nullable=True),
        sa.Column("validation_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entities.id"],
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_refactor_proposals_entity_id"),
        "refactor_proposals",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_refactor_proposals_repository_id"),
        "refactor_proposals",
        ["repository_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_refactor_proposals_repository_id"),
        table_name="refactor_proposals",
    )
    op.drop_index(
        op.f("ix_refactor_proposals_entity_id"),
        table_name="refactor_proposals",
    )
    op.drop_table("refactor_proposals")
