"""Test run and generated test case tables.

Revision ID: 0009_test_runs
Revises: 0008_pgvector
Create Date: 2026-08-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_test_runs"
down_revision = "0008_pgvector"
branch_labels = None
depends_on = None

JSONB_VARIANT = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "test_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("tests_generated", sa.Integer(), nullable=False),
        sa.Column("tests_passed", sa.Integer(), nullable=False),
        sa.Column("tests_failed", sa.Integer(), nullable=False),
        sa.Column("line_coverage", sa.Float(), nullable=False),
        sa.Column("branch_coverage", sa.Float(), nullable=False),
        sa.Column("target", sa.Float(), nullable=False),
        sa.Column("target_reached", sa.Boolean(), nullable=False),
        sa.Column("uncovered_lines", JSONB_VARIANT, nullable=False),
        sa.Column("failed_tests", JSONB_VARIANT, nullable=False),
        sa.Column("test_code", sa.Text(), nullable=True),
        sa.Column("log", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_test_runs_repository_id"),
        "test_runs",
        ["repository_id"],
    )

    op.create_table(
        "test_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("test_run_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("coverage_line_nums", JSONB_VARIANT, nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["target_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["test_run_id"], ["test_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_test_cases_test_run_id"),
        "test_cases",
        ["test_run_id"],
    )
    op.create_index(
        op.f("ix_test_cases_target_entity_id"),
        "test_cases",
        ["target_entity_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_test_cases_target_entity_id"),
        table_name="test_cases",
    )
    op.drop_index(
        op.f("ix_test_cases_test_run_id"),
        table_name="test_cases",
    )
    op.drop_table("test_cases")
    op.drop_index(
        op.f("ix_test_runs_repository_id"),
        table_name="test_runs",
    )
    op.drop_table("test_runs")
