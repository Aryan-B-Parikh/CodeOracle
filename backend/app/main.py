from fastapi import FastAPI

from app import __version__
from app.api.routes.entities import router as entities_router
from app.api.routes.graph import router as graph_router
from app.api.routes.health import router as health_router
from app.api.routes.pipeline import router as pipeline_router
from app.api.routes.repositories import router as repositories_router
from app.api.routes.search import router as search_router
from app.api.routes.summary import router as summary_router
from app.api.routes.tests import router as tests_router

app = FastAPI(title="CodeOracle API", version=__version__)

app.include_router(health_router, prefix="/api/v1")
app.include_router(repositories_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(graph_router, prefix="/api/v1")
app.include_router(entities_router, prefix="/api/v1")
app.include_router(summary_router, prefix="/api/v1")
app.include_router(tests_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
