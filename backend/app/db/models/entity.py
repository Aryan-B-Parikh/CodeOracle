"""Code entity table model (functions / methods / classes)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.repository import JSONVariant
from app.db.session import Base

if TYPE_CHECKING:
    from app.db.models.call import Call
    from app.db.models.chunk import Chunk
    from app.db.models.file import File
    from app.db.models.inheritance import Inheritance
    from app.db.models.repository import Repository


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id"), index=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entities.id"), nullable=True
    )
    signature: Mapped[str | None] = mapped_column(String(500))
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    line_start: Mapped[int] = mapped_column(Integer, default=0)
    line_end: Mapped[int] = mapped_column(Integer, default=0)
    complexity: Mapped[int] = mapped_column(Integer, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    docstring: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONVariant)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    repository: Mapped[Repository] = relationship(back_populates="entities")
    file: Mapped[File] = relationship(back_populates="entities")
    parent: Mapped[Entity | None] = relationship(
        back_populates="children", remote_side=[id]
    )
    children: Mapped[list[Entity]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    calls_made: Mapped[list[Call]] = relationship(
        back_populates="caller", foreign_keys="Call.caller_id"
    )
    inherits: Mapped[list[Inheritance]] = relationship(
        back_populates="entity", foreign_keys="Inheritance.entity_id"
    )
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
