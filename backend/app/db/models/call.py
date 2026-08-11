"""Call edge table model (function -> function)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.db.models.entity import Entity
    from app.db.models.repository import Repository


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id"), index=True
    )
    caller_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entities.id"), nullable=True, index=True
    )
    callee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entities.id"), nullable=True, index=True
    )
    callee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    call_line: Mapped[int] = mapped_column(Integer, default=0)
    external: Mapped[bool] = mapped_column(Boolean, default=False)
    dynamic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    repository: Mapped[Repository] = relationship(back_populates="calls")
    caller: Mapped[Entity | None] = relationship(
        back_populates="calls_made", foreign_keys=[caller_id]
    )
