"""Semantic chunk table model (T-08 vector index).

Stores module/class/function-level chunks with their embedding in a real
Postgres ``vector(N)`` column (pgvector) with an HNSW cosine index; the SQLite
test dialect falls back to a JSON float list. The dimension is application
configuration (``EMBEDDING_DIMENSIONS``). Search runs in the database on
Postgres and in Python on SQLite.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db.session import Base

if TYPE_CHECKING:
    from app.db.models.entity import Entity
    from app.db.models.file import File
    from app.db.models.repository import Repository

_settings = get_settings()
_VECTOR = Vector(_settings.embedding_dimensions).with_variant(JSON(), "sqlite")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

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
    embedding: Mapped[list] = mapped_column(_VECTOR, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    repository: Mapped[Repository] = relationship(back_populates="chunks")
    file: Mapped[File] = relationship(back_populates="chunks")
    entity: Mapped[Entity | None] = relationship(back_populates="chunks")
