"""Provider-agnostic embedding gateway (T-08).

- ``EMBEDDING_MODEL`` unset (default): deterministic local feature-hashing
  embedder. No network, no API key, stable across runs — ideal for fixtures,
  dev, and the test suite.
- ``EMBEDDING_MODEL`` set: OpenAI-compatible ``/embeddings`` API via
  ``LLM_API_KEY`` (same env surface as the LLM gateway). Both produce
  L2-normalized vectors so cosine similarity is comparable.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from app.config import get_settings

EMBEDDING_DIMENSIONS = 256

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")
_CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|[0-9]|$)|[A-Z]?[a-z]+|[0-9]+")


class Embedder(Protocol):
    def embed_many(self, texts: list[str]) -> list[list[float]]: ...


def _tokens(text: str) -> list[str]:
    result: list[str] = []
    for identifier in _TOKEN_RE.findall(text):
        result.append(identifier.lower())
        for part in identifier.split("_"):
            result.extend(sub.lower() for sub in _CAMEL_RE.findall(part))
    return result


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class HashEmbedder:
    """Feature-hashing embedder: token -> (bucket, sign) over a fixed dimension."""

    dimensions = EMBEDDING_DIMENSIONS

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in set(_tokens(text)):
            digest = hashlib.md5(token.encode("utf-8", errors="replace")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        return _normalize(vector)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class OpenAICompatEmbedder:
    """Minimal OpenAI-compatible ``/embeddings`` client (used when configured)."""

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        import httpx

        response = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()["data"]
        embeddings = [item["embedding"] for item in sorted(data, key=lambda item: item["index"])]
        return [_normalize(list(item)) for item in embeddings]


def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.embedding_model:
        if not settings.llm_api_key:
            raise RuntimeError("EMBEDDING_MODEL set but LLM_API_KEY is empty")
        return OpenAICompatEmbedder(settings.llm_api_key, settings.embedding_model)
    return HashEmbedder()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot