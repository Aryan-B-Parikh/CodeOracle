from fastapi import FastAPI

from app import __version__
from app.api.routes.health import router as health_router

app = FastAPI(title="CodeOracle API", version=__version__)

app.include_router(health_router, prefix="/api/v1")
