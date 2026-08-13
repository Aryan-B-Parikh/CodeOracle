"""Pydantic schemas for refactor proposal API (T-17)."""

import uuid

from pydantic import BaseModel, ConfigDict, Field, alias_generators

from app.schemas.common import Envelope


class BreakingChange(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    entity: str
    impact: str  # HIGH, MEDIUM, LOW
    reason: str
    affected_callers: list[str] = Field(default_factory=list)


class BreakingChangesResult(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    detected: bool
    changes: list[BreakingChange] = Field(default_factory=list)


class RefactorProposal(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    proposal_id: uuid.UUID
    entity_id: uuid.UUID
    entity_name: str
    file_path: str
    original: str
    proposed: str
    rationale: list[str] = Field(default_factory=list)
    behavioral_differences: list[str] = Field(default_factory=list)
    breaking_changes: BreakingChangesResult = Field(
        default_factory=lambda: BreakingChangesResult(detected=False, changes=[])
    )
    # SHA-256 checksum of the original source — proves original repo unchanged
    original_checksum: str


RefactorProposalEnvelope = Envelope[RefactorProposal]

