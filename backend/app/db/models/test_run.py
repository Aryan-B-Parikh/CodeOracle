"""TestRun DB table model (T-13 & T-14)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.db.models.repository import Repository
    from app.db.models.test_case import TestCase

JSONVariant = JSONB().with_variant(JSON(), "sqlite")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("repositories.id"), nullable=False, index=True
    )
    tested_proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("refactor_proposals.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="queued")
    iteration: Mapped[int] = mapped_column(Integer, default=1)
    tests_generated: Mapped[int] = mapped_column(Integer, default=0)
    tests_passed: Mapped[int] = mapped_column(Integer, default=0)
    tests_failed: Mapped[int] = mapped_column(Integer, default=0)
    line_coverage: Mapped[float] = mapped_column(Float, default=0.0)
    branch_coverage: Mapped[float] = mapped_column(Float, default=0.0)
    target: Mapped[float] = mapped_column(Float, default=60.0)
    target_reached: Mapped[bool] = mapped_column(Boolean, default=False)
    uncovered_lines: Mapped[list] = mapped_column(JSONVariant, default=list)
    failed_tests: Mapped[list] = mapped_column(JSONVariant, default=list)
    test_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    log: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    repository: Mapped[Repository] = relationship(back_populates="test_runs")
    test_cases: Mapped[list[TestCase]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )
