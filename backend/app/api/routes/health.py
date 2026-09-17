import asyncio

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from app.models.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Process liveness. Does not assert external provider availability."""
    return HealthResponse()


@router.get("/ready", response_model=HealthResponse)
async def ready(request: Request) -> HealthResponse:
    """Database and job-lease readiness; never calls paid or external providers."""
    if not request.app.state.lease_healthy:
        raise HTTPException(503, "Job coordination is unavailable.")
    try:
        async with asyncio.timeout(2):
            async with request.app.state.database.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Persistence is unavailable.") from None
    return HealthResponse()
