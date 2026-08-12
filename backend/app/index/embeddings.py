"""Provider-agnostic embedding gateway (T-08).

- ``EMBEDDING_MODEL`` unset (default): deterministic local feature-hashing
  embedder — no network, no API key, stable across runs (test suite / dev).
- ``EMBEDDING_MODEL`` set: OpenAI-compatible ``/embeddings`` API using
  ``LLM_API_KEY``, ``EMBEDDING_BASE_URL``, with batching
  (``EMBEDDING_BATCH_SIZE``) and retries (``EMBEDDING_RETRIES``).
  Calls are content-addressed by ``service.embed_cached`` so unchanged content
  is never re-sent to the provider.

Both produce L2-normalized vectors so cosine similarity is comparable.
The dimension is ``EMBEDDING_DIMENSIONS`` (must match the embedder's model).
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from typing import Protocol

from app.config import get_settings

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

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

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
    """OpenAI-compatible ``/embeddings`` client with batching and retries."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        batch_size: int = 64,
        retries: int = 3,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.batch_size = batch_size
        self.retries = retries

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            embeddings.extend(self._embed_batch(texts[start : start + self.batch_size]))
        return embeddings

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        import httpx

        url = f"{self.base_url}/embeddings"
        payload = {"model": self.model, "input": texts}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=60)
                response.raise_for_status()
                data = response.json()["data"]
                ordered = sorted(data, key=lambda item: item["index"])
                return [_normalize(list(item["embedding"])) for item in ordered]
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.5 * (2**attempt))  # exponential backoff
        message = f"embedding request failed after {self.retries + 1} attempts: {last_error}"
        raise RuntimeError(message) from last_error


def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.embedding_model:
        if not settings.llm_api_key:
            raise RuntimeError("EMBEDDING_MODEL set but LLM_API_KEY is empty")
        return OpenAICompatEmbedder(
            api_key=settings.llm_api_key,
            model=settings.embedding_model,
            base_url=settings.embedding_base_url,
            batch_size=settings.embedding_batch_size,
            retries=settings.embedding_retries,
        )
    return HashEmbedder(dimensions=settings.embedding_dimensions)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot