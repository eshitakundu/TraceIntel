import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.protection import RequestProtection
from app.api.routes import analysis, health
from app.config import Settings
from app.services.analysis_service import AnalysisService
from app.storage.sql_repository import SqlReportRepository

logger = logging.getLogger(__name__)
# Leases expire after 60s, so three missed 15s heartbeats may mean another
# worker can recover our jobs; stop local work before that can race.
MAX_MISSED_HEARTBEATS = 3


async def lease_heartbeat(
    state: Any, repository: SqlReportRepository, interval: float = 15
) -> None:
    """Renew job leases forever. Fail closed while unhealthy, and heal when it recovers."""
    missed = 0
    while True:
        await asyncio.sleep(interval)
        try:
            async with asyncio.timeout(10):
                await repository.renew_leases()
                await repository.recover_interrupted()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            missed += 1
            state.lease_healthy = False
            logger.error("lease heartbeat missed=%d error=%s", missed, type(exc).__name__)
            if missed == MAX_MISSED_HEARTBEATS:
                await state.analysis.close()
            continue
        if not state.lease_healthy:
            logger.info("lease heartbeat recovered after %d missed", missed)
        missed = 0
        state.lease_healthy = True


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    if not logging.getLogger().handlers:
        # Uvicorn only configures its own loggers; make application events visible too.
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
        )

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
                application.state.database = engine
                application.state.lease_healthy = True
                application.state.analysis = AnalysisService(repository, settings, client)

                heartbeat = asyncio.create_task(lease_heartbeat(application.state, repository))
                try:
                    yield
                finally:
                    heartbeat.cancel()
                    await asyncio.gather(heartbeat, return_exceptions=True)
                    await application.state.analysis.close()
                    await repository.release_owned()
        finally:
            await engine.dispose()

    application = FastAPI(
        title="TraceIntel API",
        version="0.1.0",
        lifespan=lifespan,
        description="Deterministic EVM evidence with separately attributed agent interpretation.",
    )
    application.state.settings = settings
    application.add_middleware(RequestProtection)
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
