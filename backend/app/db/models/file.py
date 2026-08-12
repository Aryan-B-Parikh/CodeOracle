"""Source file table model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.db.models.chunk import Chunk
    from app.db.models.entity import Entity
    from app.db.models.import_ import Import
    from app.db.models.repository import Repository


def _utcnow() -> datetime:
    return datetime.now(UTC)


class File(Base):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id"), index=True
    )
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    loc: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    repository: Mapped[Repository] = relationship(back_populates="files")
    entities: Mapped[list[Entity]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )
    imports: Mapped[list[Import]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )
