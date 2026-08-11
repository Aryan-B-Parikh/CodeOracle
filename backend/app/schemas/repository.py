"""Repository request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, alias_generators

from app.schemas.common import Envelope


class RepositoryOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=alias_generators.to_camel,
    )

    id: uuid.UUID
    name: str
    source_type: str
    github_url: str | None = None
    languages: dict[str, bool] = Field(default_factory=dict)
    language_counts: dict[str, int] = Field(default_factory=dict)
    loc: int = 0
    entity_count: int = 0
    file_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime


class ImportRequest(BaseModel):
    github_url: str


RepositoryEnvelope = Envelope[RepositoryOut]
