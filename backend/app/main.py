from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.routes import analysis, health
from app.config import Settings
from app.services.analysis_service import AnalysisService
from app.storage.sql_repository import SqlReportRepository


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = create_async_engine(settings.database_url.get_secret_value(), pool_pre_ping=True)
        repository = SqlReportRepository(engine)
        try:
            await repository.recover_interrupted()
            async with httpx.AsyncClient(
                timeout=settings.rpc_timeout_seconds,
                limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
            ) as client:
                application.state.analysis = AnalysisService(repository, settings, client)
                try:
                    yield
                finally:
                    await application.state.analysis.close()
        finally:
            await engine.dispose()

    application = FastAPI(
        title="TraceIntel API",
        version="0.1.0",
        lifespan=lifespan,
        description="Deterministic EVM evidence with separately attributed agent interpretation.",
    )
    application.state.settings = settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    application.include_router(health.router, prefix="/api/v1")
    application.include_router(analysis.router, prefix="/api/v1")
    return application


app = create_app()
