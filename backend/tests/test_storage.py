import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.models.report import AnalysisJob
from app.storage.sql_repository import SqlReportRepository
from app.storage.tables import Base, JobRow
from sqlalchemy import update
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
    replacement = SqlReportRepository(engine)
    await replacement.recover_interrupted()
    still_running = await repo.get_job(prefix + "one")
    assert still_running and still_running.status == "queued"
    await repo.renew_leases()
    async with repo.sessions.begin() as session:
        await session.execute(
            update(JobRow)
            .where(JobRow.id == job.id)
            .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    with pytest.raises(RuntimeError, match="expired"):
        await repo.renew_leases()
    await replacement.recover_interrupted()
    # A delayed old worker must not resurrect a recovered terminal job.
    await repo.update_job(job.model_copy(update={"status": "complete", "stage": "Complete"}))
    recovered = await repo.get_job(prefix + "one")
    assert recovered and recovered.status == "failed"
    _, new = await repo.submit(
        job.model_copy(update={"id": prefix + "three"}), prefix + "cache-key"
    )
    assert new
    foreign = job.model_copy(update={"id": prefix + "foreign"})
    await replacement.submit(foreign, prefix + "foreign-key")
    await repo.release_owned()
    released = await repo.get_job(prefix + "three")
    untouched = await repo.get_job(foreign.id)
    assert released and released.status == "failed"
    assert untouched and untouched.status == "queued"
    await replacement.release_owned()
    await engine.dispose()
