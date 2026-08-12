"""API schemas for test runs and test generation (T-13 & T-14)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, alias_generators

from app.schemas.common import Envelope


class UncoveredLineItem(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    file: str
    line: int
    branch: bool = False


class FailedTestItem(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    name: str
    target_entity: str | None = None
    message: str


class TestRunData(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    test_run_id: uuid.UUID
    status: str
    iteration: int = 1
    tests_generated: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    line_coverage: float = 0.0
    branch_coverage: float = 0.0
    target: float = 60.0
    target_reached: bool = False
    status_label: str = "PENDING"
    uncovered_lines: list[UncoveredLineItem] = Field(default_factory=list)
    failed_tests: list[FailedTestItem] = Field(default_factory=list)
    test_code: str | None = None
    created_at: datetime


TestRunEnvelope = Envelope[TestRunData]


class GenerateTestCodeResponse(BaseModel):
    model_config = ConfigDict(
        alias_generator=alias_generators.to_camel, populate_by_name=True
    )

    repository_id: uuid.UUID
    language: str
    code: str
    target_functions: list[str] = Field(default_factory=list)
    test_run_id: uuid.UUID | None = None


GenerateTestCodeEnvelope = Envelope[GenerateTestCodeResponse]
