"""Dependency graph API schemas (React Flow payload, T-06)."""

from pydantic import BaseModel, ConfigDict, Field, alias_generators

from app.schemas.common import Envelope


class GraphNode(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=alias_generators.to_camel,
    )

    id: str
    label: str
    type: str
    complexity: int = 0
    file: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    qualified_name: str | None = None
    risk_score: int | None = None


class GraphEdge(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    source: str
    target: str
    kind: str = "call"


class CycleRef(BaseModel):
    model_config = ConfigDict(alias_generator=alias_generators.to_camel)

    cycle: list[str]


class GraphMeta(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    circular_dependencies: list[CycleRef] = Field(default_factory=list)
    high_risk_node_ids: list[str] = Field(default_factory=list)


class GraphPayload(BaseModel):
    model_config = ConfigDict(alias_generator=alias_generators.to_camel)

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    meta: GraphMeta = Field(default_factory=GraphMeta)


GraphEnvelope = Envelope[GraphPayload]
