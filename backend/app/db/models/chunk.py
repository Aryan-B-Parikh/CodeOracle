"""Semantic chunk table model (T-08 vector index).

Stores module/class/function level chunks with their embedding as a JSON list
of floats (JSONVariant -> real ``vector`` column on Postgres is the documented
pgvector upgrade path; see DECISIONS.md). The embedding dimension is an
application concern; search computes cosine similarity in Python for now.
"""

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
    from app.db.models.file import File
    from app.db.models.repository import Repository

JSONVariant = JSONB().with_variant(JSON(), "sqlite")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("repositories.id"), index=True, nullable=False
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("files.id"), index=True, nullable=False
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("entities.id"), index=True, nullable=True
    )
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    qualified_name: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(JSONVariant, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    repository: Mapped[Repository] = relationship(back_populates="chunks")
    file: Mapped[File] = relationship(back_populates="chunks")
    entity: Mapped[Entity | None] = relationship(back_populates="chunks")