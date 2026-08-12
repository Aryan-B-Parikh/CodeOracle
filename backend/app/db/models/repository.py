"""Repository table model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.db.models.analysis import Analysis
    from app.db.models.call import Call
    from app.db.models.entity import Entity
    from app.db.models.file import File
    from app.db.models.inheritance import Inheritance

JSONVariant = JSONB().with_variant(JSON(), "sqlite")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    github_url: Mapped[str | None] = mapped_column(String(500))
    languages: Mapped[dict] = mapped_column(JSONVariant, default=dict)
    language_counts: Mapped[dict] = mapped_column(JSONVariant, default=dict)
    loc: Mapped[int] = mapped_column(Integer, default=0)
    entity_count: Mapped[int] = mapped_column(Integer, default=0)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    warnings: Mapped[list] = mapped_column(JSONVariant, default=list)
    status: Mapped[str] = mapped_column(String(16), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    files: Mapped[list[File]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    entities: Mapped[list[Entity]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    calls: Mapped[list[Call]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    inheritances: Mapped[list[Inheritance]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    analyses: Mapped[list[Analysis]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
