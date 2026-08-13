"""Immutable refactor proposal record model (T-17 W3: versioned, reproducible proposals)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.db.models.entity import Entity
    from app.db.models.repository import Repository

JSONVariant = JSONB().with_variant(JSON(), "sqlite")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class RefactorProposalRecord(Base):
    """Immutable proposal record — never updated, only inserted.

    The (original_checksum, entity_id) pair uniquely identifies what source
    text was read when this proposal was generated, so users can always
    reproduce which exact original produced this diff.
    """

    __tablename__ = "refactor_proposals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("repositories.id"), nullable=False, index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("entities.id"), nullable=False, index=True
    )
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    original: Mapped[str] = mapped_column(Text, nullable=False, default="")
    proposed: Mapped[str] = mapped_column(Text, nullable=False, default="")
    original_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    rationale: Mapped[list] = mapped_column(JSONVariant, default=list)
    behavioral_differences: Mapped[list] = mapped_column(JSONVariant, default=list)
    # Validation fields — set at proposal creation time
    syntax_valid: Mapped[str | None] = mapped_column(
        "syntax_valid", String(8), nullable=True
    )
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    repository: Mapped[Repository] = relationship(back_populates="refactor_proposals")
    entity: Mapped[Entity] = relationship()
