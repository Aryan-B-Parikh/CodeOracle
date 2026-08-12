"""API schemas for entity impact analysis (T-12)."""

from pydantic import BaseModel, ConfigDict, Field, alias_generators

from app.schemas.common import Envelope


class CallerItem(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    caller: str
    file: str
    line_start: int
    line_end: int
    call_line: int


class CalleeItem(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    callee: str
    file: str
    line_start: int = 0
    line_end: int = 0


class ImpactEntitySummary(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    name: str
    file: str
    line_start: int
    line_end: int


class ImpactData(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    entity: ImpactEntitySummary
    callers: list[CallerItem] = Field(default_factory=list)
    callees: list[CalleeItem] = Field(default_factory=list)
    impact: str
    impact_reason: str


ImpactEnvelope = Envelope[ImpactData]
