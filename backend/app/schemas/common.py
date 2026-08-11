"""Shared API contracts (envelope + error) used by every endpoint."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Error(BaseModel):
    code: str
    message: str


class Envelope(BaseModel, Generic[T]):
    data: T | None = None
    error: Error | None = None
