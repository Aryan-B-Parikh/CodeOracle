from fastapi import FastAPI

from app import __version__
from app.api.routes.graph import router as graph_router
from app.api.routes.health import router as health_router
from app.api.routes.repositories import router as repositories_router

app = FastAPI(title="CodeOracle API", version=__version__)

app.include_router(health_router, prefix="/api/v1")
app.include_router(repositories_router, prefix="/api/v1")
app.include_router(graph_router, prefix="/api/v1")
