"""Analysis pipeline request/response schemas (T-07)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, alias_generators

from app.schemas.common import Envelope


class AnalysisOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=alias_generators.to_camel,
    )

    id: uuid.UUID
    repository_id: uuid.UUID
    status: str
    pipeline_state: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class RepositoryStatusOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=alias_generators.to_camel,
    )

    repository_status: str
    analysis_status: str | None = None
    current_stage: str | None = None
    pipeline_state: dict[str, Any] = Field(default_factory=dict)


AnalysisEnvelope = Envelope[AnalysisOut]
StatusEnvelope = Envelope[RepositoryStatusOut]