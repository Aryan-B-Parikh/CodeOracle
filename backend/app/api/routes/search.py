"""Semantic search API: vector-similarity retrieval over the index (T-08)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models.repository import Repository
from app.db.session import get_db
from app.index.service import DEFAULT_SEARCH_LIMIT, MAX_SEARCH_LIMIT, search
from app.schemas.search import SearchEnvelope, SearchPayload, SearchResult

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "/repositories/{repository_id}/search",
    response_model=SearchEnvelope,
)
def search_repository(
    repository_id: uuid.UUID,
    db: DbSession,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=MAX_SEARCH_LIMIT)] = DEFAULT_SEARCH_LIMIT,
) -> SearchEnvelope:
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")
    results = search(db, repository, q, limit=limit)
    return SearchEnvelope(
        data=SearchPayload(
            query=q,
            results=[SearchResult.model_validate(item) for item in results],
        )
    )