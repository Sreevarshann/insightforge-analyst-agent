"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from insightforge import __version__
from insightforge.agent.explain import llm_explainer
from insightforge.api import analyses, datasets, evaluation, health, ops, query, relationships
from insightforge.api.middleware import SSENoTransform
from insightforge.config import Settings, get_settings
from insightforge.db.session import make_engine, make_sessionmaker, run_migrations
from insightforge.logging import configure_logging

log = logging.getLogger("insightforge")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        settings.datasets_dir.mkdir(parents=True, exist_ok=True)
        engine = make_engine(settings.metadata_db_path)
        run_migrations(engine)
        app.state.engine = engine
        app.state.sessionmaker = make_sessionmaker(engine)
        log.info("startup", extra={"environment": settings.environment})
        yield
        engine.dispose()

    app = FastAPI(
        title="InsightForge API",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.explain_factory = llm_explainer
    app.add_middleware(SSENoTransform)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internals (paths, SQL, data) to the client.
        log.exception("unhandled_error", extra={"path": request.url.path})
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(health.router, prefix="/api")
    app.include_router(datasets.router, prefix="/api")
    app.include_router(query.router, prefix="/api")
    app.include_router(ops.router, prefix="/api")
    app.include_router(analyses.router, prefix="/api")
    app.include_router(relationships.router, prefix="/api")
    app.include_router(evaluation.router, prefix="/api")
    return app


app = create_app()
