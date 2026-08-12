"""API schemas for repository summary and architecture classification (T-11)."""

from pydantic import BaseModel, ConfigDict, Field, alias_generators

from app.schemas.common import Envelope
from app.schemas.explanation import EvidenceItem


class ArchLayer(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    layer: str
    modules: list[str] = Field(default_factory=list)


class ArchIssue(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    kind: str
    detail: str
    severity: str = "medium"


class HighRiskEntity(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    name: str
    file: str
    complexity: int = 0
    callers: int = 0


class RepositorySummaryData(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    architecture: list[ArchLayer] = Field(default_factory=list)
    issues: list[ArchIssue] = Field(default_factory=list)
    overview: str | None = None


class AnalysisSummaryPayload(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    summary: RepositorySummaryData
    high_risk_entities: list[HighRiskEntity] = Field(default_factory=list)


SummaryEnvelope = Envelope[AnalysisSummaryPayload]


class ModuleSummaryItem(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    file: str
    language: str
    loc: int = 0
    entity_count: int = 0
    entities: list[str] = Field(default_factory=list)
    purpose: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    summary: str


ModuleSummaryEnvelope = Envelope[list[ModuleSummaryItem]]
