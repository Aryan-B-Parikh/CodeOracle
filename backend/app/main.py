from fastapi import FastAPI

from app import __version__
from app.api.routes.entities import router as entities_router
from app.api.routes.graph import router as graph_router
from app.api.routes.health import router as health_router
from app.api.routes.pipeline import router as pipeline_router
from app.api.routes.refactor import router as refactor_router
from app.api.routes.report import router as report_router
from app.api.routes.repositories import router as repositories_router
from app.api.routes.safety import router as safety_router
from app.api.routes.search import router as search_router
from app.api.routes.summary import router as summary_router
from app.api.routes.tests import router as tests_router

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CodeOracle API", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(repositories_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(graph_router, prefix="/api/v1")
app.include_router(entities_router, prefix="/api/v1")
app.include_router(summary_router, prefix="/api/v1")
app.include_router(tests_router, prefix="/api/v1")
app.include_router(refactor_router, prefix="/api/v1")
app.include_router(safety_router, prefix="/api/v1")
app.include_router(report_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
