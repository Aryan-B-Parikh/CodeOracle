"""API schemas for evidence-cited AI function explanations (T-10)."""

import uuid

from pydantic import BaseModel, ConfigDict, Field, alias_generators

from app.schemas.common import Envelope


class EvidenceItem(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    claim: str
    file: str
    line_start: int
    line_end: int
    code: str


class ExplanationFields(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    purpose: str
    inputs: str
    outputs: str
    side_effects: str
    dependencies: str
    control_flow: str
    error_handling: str
    business_rules: str
    complexity: int = 0
    risks: str


class EntitySummary(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=alias_generators.to_camel,
    )

    id: uuid.UUID | None = None
    name: str
    type: str
    file: str
    line_start: int
    line_end: int


class ExplanationData(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    entity: EntitySummary
    explanation: ExplanationFields
    evidence: list[EvidenceItem] = Field(default_factory=list)


ExplanationEnvelope = Envelope[ExplanationData]
