"""Executive Report API routes (T-21)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.models.repository import Repository
from app.db.session import get_db
from app.services.report import generate_executive_report

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "/repositories/{repository_id}/report",
    response_class=Response,
    status_code=200,
)
def get_executive_report_markdown(
    repository_id: uuid.UUID,
    db: DbSession,
) -> Response:
    """Generate and return a full Markdown Executive Report for a repository."""
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    report_md = generate_executive_report(db, repository)
    filename = f"{repository.name.replace(' ', '_')}_Architecture_Report.md"

    return Response(
        content=report_md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
