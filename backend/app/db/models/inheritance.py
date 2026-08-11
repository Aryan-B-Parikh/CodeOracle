"""Inheritance edge table model (subclass -> parent type)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.db.models.entity import Entity
    from app.db.models.repository import Repository


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Inheritance(Base):
    __tablename__ = "inheritances"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id"), index=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id"), index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entities.id"), nullable=True, index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entities.id"), nullable=True, index=True
    )
    parent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    line: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    repository: Mapped[Repository] = relationship(back_populates="inheritances")
    entity: Mapped[Entity | None] = relationship(
        back_populates="inherits", foreign_keys=[entity_id]
    )
