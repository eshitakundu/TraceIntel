import asyncio
import os
from uuid import uuid4

import pytest
from app.models.report import AnalysisJob
from app.storage.sql_repository import SqlReportRepository
from app.storage.tables import Base
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_repository_deduplicates_and_recovers(tmp_path) -> None:
    engine = create_async_engine(
        os.environ.get("TRACEINTEL_TEST_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/test.db")
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    repo = SqlReportRepository(engine)
    prefix = uuid4().hex[:20]
    job = AnalysisJob(
        id=prefix + "one",
        chain="ethereum",
        transaction_hash="0x" + "a" * 64,
        status="queued",
        stage="Queued",
    )
    first, created = await repo.submit(job, prefix + "cache-key")
    second, duplicate = await repo.submit(
        job.model_copy(update={"id": prefix + "two"}), prefix + "cache-key"
    )
    assert created and not duplicate and first.id == second.id
    reservations = await asyncio.gather(
        *(repo.reserve_budget(prefix + "daily", 3) for _ in range(8))
    )
    assert sum(reservations) == 3
    await repo.recover_interrupted()
    recovered = await repo.get_job(prefix + "one")
    assert recovered and recovered.status == "failed"
    _, new = await repo.submit(
        job.model_copy(update={"id": prefix + "three"}), prefix + "cache-key"
    )
    assert new
    await engine.dispose()
