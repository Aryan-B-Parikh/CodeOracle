"""Semantic search API schemas (T-08)."""

import uuid

from pydantic import BaseModel, ConfigDict, Field, alias_generators

from app.schemas.common import Envelope


class SearchResult(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    entity_id: uuid.UUID | None = None
    qualified_name: str | None = None
    file: str | None = None
    type: str | None = None
    level: str
    line_start: int | None = None
    line_end: int | None = None
    score: float = 0.0


class SearchPayload(BaseModel):
    model_config = ConfigDict(alias_generator=alias_generators.to_camel)

    query: str
    results: list[SearchResult] = Field(default_factory=list)


SearchEnvelope = Envelope[SearchPayload]