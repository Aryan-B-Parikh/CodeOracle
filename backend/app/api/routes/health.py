from fastapi import APIRouter

from app.schemas.common import Envelope
from app.schemas.health import HealthStatus

router = APIRouter()


@router.get("/health", response_model=Envelope[HealthStatus])
def health() -> Envelope[HealthStatus]:
    return Envelope(data=HealthStatus(status="ok"))
