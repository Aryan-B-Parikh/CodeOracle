"""TestCase DB table model (T-13 & T-14)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.db.models.test_run import TestRun

JSONVariant = JSONB().with_variant(JSON(), "sqlite")


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    test_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("test_runs.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("entities.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="passed")
    coverage_line_nums: Mapped[list | None] = mapped_column(
        JSONVariant, nullable=True
    )
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    test_run: Mapped[TestRun] = relationship(back_populates="test_cases")
