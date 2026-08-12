"""Semantic index: build module/class/function chunks, embed, and search (T-08).

The index is rebuilt deterministically after each analysis run. Embeddings go
through a content-addressed cache so API-backed embedders are only called for
new text. On PostgreSQL the similarity search runs in the database (pgvector
cosine distance, HNSW-backed); on the SQLite test dialect it falls back to
Python cosine over the stored JSON vectors with identical result semantics.
"""

from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.call import Call
from app.db.models.chunk import Chunk
from app.db.models.embedding_cache import EmbeddingCache
from app.db.models.entity import Entity
from app.db.models.file import File
from app.db.models.import_ import Import
from app.db.models.inheritance import Inheritance
from app.db.models.repository import Repository
from app.index.chunking import entity_chunk_text, level_for, module_chunk_text
from app.index.embeddings import cosine_similarity, get_embedder

settings = get_settings()

DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 50

_TEST_PATH_PARTS = {"test", "tests", "spec", "specs"}
_TEST_FILE_NAMES = {"conftest.py"}


def _is_test_file(file_row: File) -> bool:
    """Exclude test sources from the semantic index (noise for entity search)."""
    name = Path(file_row.path).name
    if name in _TEST_FILE_NAMES:
        return True
    if name.startswith("test_") or name.endswith(".test.py"):
        return True
    if name.endswith("Test.java") or name.endswith("Tests.java"):
        return True
    return any(part in _TEST_PATH_PARTS for part in Path(file_row.path).parts)


def _coerce_list(value: object) -> list[float]:
    """Convert pgvector/numpy values or JSON sequences into a float list."""
    if hasattr(value, "tolist"):
        converted = value.tolist()
        if not isinstance(converted, list):
            raise TypeError("Expected a one-dimensional embedding")
        return [float(item) for item in converted]
    if isinstance(value, (list, tuple)):
        return [float(item) for item in value]
    raise TypeError(f"Unsupported embedding value: {type(value).__name__}")


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def delete_index(db: Session, repository_id: uuid.UUID) -> None:
    db.query(Chunk).filter(Chunk.repository_id == repository_id).delete(
        synchronize_session=False
    )


def embed_cached(db: Session, texts: list[str]) -> list[list[float]]:
    """Content-addressed embedding with fallback to direct embedding when caching
    is disabled. Persistently cached by (model, dimensions, content hash)."""
    embedder = get_embedder()
    if not settings.embedding_cache:
        return embedder.embed_many(texts)

    hashes = [_content_hash(text) for text in texts]
    model = settings.embedding_model or "local"
    dimensions = settings.embedding_dimensions

    by_hash: dict[str, list[float]] = {}
    rows = (
        db.query(EmbeddingCache)
        .filter(
            EmbeddingCache.model == model,
            EmbeddingCache.dimensions == dimensions,
            EmbeddingCache.content_hash.in_(hashes),
        )
        .all()
    )
    for row in rows:
        by_hash[row.content_hash] = _coerce_list(row.embedding)

    needed_indices = [i for i, h in enumerate(hashes) if h not in by_hash]
    missing_vectors: list[list[float]] = (
        embedder.embed_many([texts[i] for i in needed_indices])
        if needed_indices
        else []
    )

    vectors_by_index: dict[int, list[float]] = {}
    for i, h in enumerate(hashes):
        cached = by_hash.get(h)
        if cached is not None:
            vectors_by_index[i] = cached

    for vector, index in zip(missing_vectors, needed_indices, strict=True):
        vectors_by_index[index] = vector

    if len(vectors_by_index) != len(hashes):
        raise RuntimeError("embed_cached produced incomplete embeddings")

    resolved_vectors = [vectors_by_index[i] for i in range(len(hashes))]

    new_rows = [
        EmbeddingCache(
            model=model,
            dimensions=dimensions,
            content_hash=hashes[index],
            embedding=vector,
        )
        for index, vector in zip(needed_indices, missing_vectors, strict=True)
    ]
    if new_rows:
        db.add_all(new_rows)
        db.commit()
    return resolved_vectors


def create_index(db: Session, repository: Repository) -> int:
    """Rebuild embeddings for a repository; returns the number of chunks stored."""
    delete_index(db, repository.id)
    db.commit()

    calls_by_caller: dict[str, list[Call]] = defaultdict(list)
    for call in db.query(Call).filter(Call.repository_id == repository.id):
        if call.caller_id is not None:
            calls_by_caller[str(call.caller_id)].append(call)

    inheritances_by_entity: dict[str, list[Inheritance]] = defaultdict(list)
    for edge in db.query(Inheritance).filter(Inheritance.repository_id == repository.id):
        if edge.entity_id is not None:
            inheritances_by_entity[str(edge.entity_id)].append(edge)

    imports_by_file: dict[str, list[Import]] = defaultdict(list)
    for imported in db.query(Import).filter(
        Import.file_id.in_([f.id for f in repository.files])
    ):
        imports_by_file[str(imported.file_id)].append(imported)

    chunks: list[Chunk] = []
    texts: list[str] = []
    for file_row in repository.files:
        if _is_test_file(file_row):
            continue
        module_text = module_chunk_text(
            file_row,
            imports_by_file[str(file_row.id)],
            [e for e in file_row.entities if not e.parent_id],
        )
        chunks.append(
            Chunk(
                repository_id=repository.id,
                file_id=file_row.id,
                entity_id=None,
                level="module",
                qualified_name=None,
                content=module_text,
            )
        )
        texts.append(module_text)
        for entity in file_row.entities:
            qualified_name = (
                entity.metadata_json.get("qualified_name") or entity.name
            ) if entity.metadata_json else entity.name
            text = entity_chunk_text(entity, calls_by_caller, inheritances_by_entity)
            chunks.append(
                Chunk(
                    repository_id=repository.id,
                    file_id=file_row.id,
                    entity_id=entity.id,
                    level=level_for(entity),
                    qualified_name=qualified_name,
                    content=text,
                )
            )
            texts.append(text)

    vectors = embed_cached(db, texts)
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk.embedding = vector

    db.add_all(chunks)
    db.commit()
    return len(chunks)


def search(
    db: Session,
    repository: Repository,
    query: str,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> list[dict[str, object]]:
    query_vector = embed_cached(db, [query])[0]
    if db.get_bind().dialect.name == "postgresql":
        scored = _database_search(db, repository, query_vector, limit)
    else:
        scored = _python_search(db, repository, query_vector)
    return _build_results(db, repository, scored, limit)


def _python_search(
    db: Session,
    repository: Repository,
    query_vector: list[float],
) -> list[tuple[float, Chunk]]:
    scored: list[tuple[float, Chunk]] = []
    for chunk in db.query(Chunk).filter(Chunk.repository_id == repository.id):
        if not chunk.embedding:
            continue
        scored.append(
            (cosine_similarity(query_vector, _coerce_list(chunk.embedding)), chunk)
        )
    return scored


def _database_search(
    db: Session,
    repository: Repository,
    query_vector: list[float],
    limit: int,
) -> list[tuple[float, Chunk]]:
    """pgvector cosine distance (``<=>``) evaluated inside PostgreSQL, HNSW-backed."""
    distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
    rows = (
        db.execute(
            select(Chunk, distance)
            .where(Chunk.repository_id == repository.id)
            .order_by(distance.asc())
            .limit(limit)
        )
        .all()
    )
    return [(1.0 - float(row.distance), row.Chunk) for row in rows]


def _build_results(
    db: Session,
    repository: Repository,
    scored: list[tuple[float, Chunk]],
    limit: int,
) -> list[dict[str, object]]:
    scored.sort(key=lambda item: (-item[0], item[1].qualified_name or ""))

    entity_by_id = {
        entity.id: entity
        for entity in db.query(Entity).filter(Entity.repository_id == repository.id)
    }
    file_by_id = {
        file_row.id: file_row
        for file_row in db.query(File).filter(File.repository_id == repository.id)
    }

    results: list[dict[str, object]] = []
    for score, chunk in scored[:limit]:
        entity = entity_by_id.get(chunk.entity_id) if chunk.entity_id else None
        file_row = file_by_id.get(chunk.file_id)
        results.append(
            {
                "entity_id": chunk.entity_id,
                "qualified_name": chunk.qualified_name,
                "file": file_row.path if file_row else None,
                "type": entity.type if entity else None,
                "level": chunk.level,
                "line_start": entity.line_start if entity else None,
                "line_end": entity.line_end if entity else None,
                "score": round(score, 4),
            }
        )
    return results
