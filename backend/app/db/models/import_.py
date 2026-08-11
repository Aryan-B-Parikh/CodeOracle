"""Import record table model (per source file)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.db.models.file import File


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Import(Base):
    __tablename__ = "imports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id"), index=True)
    module: Mapped[str] = mapped_column(String(255), nullable=False)
    local_name: Mapped[str | None] = mapped_column(String(255))
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)
    kind: Mapped[str] = mapped_column(String(16), default="normal")
    line: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    file: Mapped[File] = relationship(back_populates="imports")
