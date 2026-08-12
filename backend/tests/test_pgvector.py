"""Real PostgreSQL + pgvector integration tests for T-08.

These tests are skipped on non-PostgreSQL environments, but CI provisions a
real pgvector service so the production vector path is exercised on every
quality-gate run.
"""

import uuid

import pytest
from sqlalchemy import text

from app.db.models.chunk import Chunk
from app.db.models.file import File
from app.db.models.repository import Repository
from app.db.session import Base, SessionLocal, engine
from app.index.embeddings import get_embedder
from app.index.service import search


@pytest.fixture(scope="module", autouse=True)
def _requires_postgresql() -> None:
    if engine.dialect.name != "postgresql":
        pytest.skip("pgvector integration tests require PostgreSQL")


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)


def _repository(db, name: str) -> tuple[Repository, File]:
    repository = Repository(
        id=uuid.uuid4(),
        name=name,
        source_type="upload",
        languages={"python": 1},
        loc=10,
        entity_count=0,
        file_count=1,
        warnings=[],
        status="analyzed",
    )
    file_row = File(
        id=uuid.uuid4(),
        repository_id=repository.id,
        path="main.py",
        language="python",
        loc=10,
        sha256="0" * 64,
    )
    db.add(repository)
    db.add(file_row)
    db.commit()
    return repository, file_row


def test_vector_extension_and_column_type() -> None:
    with engine.connect() as conn:
        extension = conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one_or_none()
        assert extension == 1

        vector_type = conn.execute(
            text(
                """SELECT pg_type.typname
                   FROM pg_type
                   JOIN pg_attribute ON pg_type.oid = pg_attribute.atttypid
                   JOIN pg_class ON pg_attribute.attrelid = pg_class.oid
                   WHERE pg_class.relname = 'chunks'
                     AND pg_attribute.attname = 'embedding'"""
            )
        ).scalar_one()
        assert vector_type == "vector"

        index = conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'chunks' AND indexname = 'ix_chunks_embedding_hnsw'"
            )
        ).scalar_one_or_none()
        assert index == "ix_chunks_embedding_hnsw"


def test_vector_round_trip() -> None:
    embedder = get_embedder()
    vector = embedder.embed_many(["test function for pgvector"])[0]
    assert vector
    assert all(isinstance(value, float) for value in vector)

    with SessionLocal() as db:
        repository, file_row = _repository(db, "vector_round_trip")
        chunk = Chunk(
            id=uuid.uuid4(),
            repository_id=repository.id,
            file_id=file_row.id,
            entity_id=None,
            level="function",
            qualified_name="test_func",
            content="test function for pgvector",
            embedding=vector,
        )
        db.add(chunk)
        db.commit()

        retrieved = db.get(Chunk, chunk.id)
        assert retrieved is not None
        assert retrieved.embedding is not None
        assert len(retrieved.embedding) == len(vector)


def test_database_cosine_search_returns_ranked_results() -> None:
    embedder = get_embedder()
    texts = [
        "calculate tax rate",
        "compute invoice total",
        "apply discount to price",
    ]

    with SessionLocal() as db:
        repository, file_row = _repository(db, "cosine_search")
        vectors = embedder.embed_many(texts)
        for value, vector in zip(texts, vectors, strict=True):
            db.add(
                Chunk(
                    id=uuid.uuid4(),
                    repository_id=repository.id,
                    file_id=file_row.id,
                    entity_id=None,
                    level="function",
                    qualified_name=value.replace(" ", "_"),
                    content=value,
                    embedding=vector,
                )
            )
        db.commit()

        results = search(db, repository, "tax calculation", limit=3)

        assert len(results) == 3
        scores = [float(result["score"]) for result in results]
        assert all(0.0 <= score <= 1.0 for score in scores)
        assert scores == sorted(scores, reverse=True)
        assert all(result["file"] == "main.py" for result in results)
