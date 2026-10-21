"""FastAPI application factory.

Run locally with ``uv run uvicorn simforge.main:app --reload``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from simforge import __version__
from simforge.api.body_limit import BodySizeLimitMiddleware
from simforge.api.errors import register_error_handlers
from simforge.api.routes import economy, experiments, health, physics, quant
from simforge.config import Settings
from simforge.persistence.experiments import ExperimentRepository, init_db
from simforge.quant.profiling.limits import MAX_REQUEST_BYTES

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_db(settings.db_path)
        app.state.experiments = ExperimentRepository(settings.db_path)
        yield

    app = FastAPI(
        title="SimForge API",
        version=__version__,
        description="Validated scientific simulations with explicit assumptions and units.",
        lifespan=lifespan,
    )
    # Starlette runs the last-added middleware first. The size guard is added before CORS so
    # that CORS wraps it, and its 413 response still carries the CORS headers.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_REQUEST_BYTES)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    register_error_handlers(app)
    for router in (
        health.router,
        physics.router,
        economy.router,
        quant.router,
        experiments.router,
    ):
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
