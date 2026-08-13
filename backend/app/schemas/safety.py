"""API schemas for breaking-change detection and Refactor Safety Score (T-18 & T-19)."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, alias_generators

from app.schemas.common import Envelope


class BreakingChangeItem(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    entity: str
    impact: Literal["HIGH", "MEDIUM", "LOW"]
    reason: str
    affected_callers: list[str] = Field(default_factory=list)


class SafetyScoreData(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    proposal_id: uuid.UUID
    test_run_id: uuid.UUID | None = None
    original_checksum: str = ""
    proposed_checksum: str = ""
    total: int = Field(ge=0, le=100)
    confidence_score: int = Field(default=50, ge=0, le=100)
    confidence_level: Literal["high", "medium", "low"] = "medium"
    api_compatibility: int = Field(ge=0, le=100)
    test_compatibility: int = Field(ge=0, le=100)
    dependency_impact: int = Field(ge=0, le=100)
    behavioral_risk: int = Field(ge=0, le=100)
    risk_level: Literal["low", "medium", "high"]
    behavior_status: Literal["BEHAVIOR_PRESERVED", "BEHAVIOR_MUTATED", "UNVERIFIED"] = "UNVERIFIED"
    breaking_changes: list[BreakingChangeItem] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


SafetyScoreEnvelope = Envelope[SafetyScoreData]
