from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.models.report import AnalysisJob, Report
from app.storage.tables import BudgetRow, JobRow, ReportRow


class SqlReportRepository:
    def __init__(self, engine: AsyncEngine):
        self.owner_id = str(uuid4())
        self.sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def submit(self, job: AnalysisJob, cache_key: str) -> tuple[AnalysisJob, bool]:
        async with self.sessions() as session:
            found = await session.scalar(select(JobRow).where(JobRow.cache_key == cache_key))
            if found:
                return AnalysisJob.model_validate_json(found.payload), False
            session.add(
                JobRow(
                    id=job.id,
                    cache_key=cache_key,
                    status=job.status,
                    payload=job.model_dump_json(),
                    owner_id=self.owner_id,
                    lease_expires_at=datetime.now(UTC) + timedelta(seconds=60),
                )
            )
            try:
                await session.commit()
                return job, True
            except IntegrityError:
                await session.rollback()
                existing = await session.scalar(select(JobRow).where(JobRow.cache_key == cache_key))
                if existing is None:
                    raise
                return AnalysisJob.model_validate_json(existing.payload), False

    async def get_job(self, job_id: str) -> AnalysisJob | None:
        async with self.sessions() as session:
            row = await session.get(JobRow, job_id)
            return AnalysisJob.model_validate_json(row.payload) if row else None

    async def update_job(self, job: AnalysisJob) -> None:
        async with self.sessions.begin() as session:
            values: dict[str, object] = {"status": job.status, "payload": job.model_dump_json()}
            if job.status == "failed":
                values["cache_key"] = None
            await session.execute(
                update(JobRow)
                .where(
                    JobRow.id == job.id,
                    or_(
                        (JobRow.owner_id == self.owner_id)
                        & JobRow.status.in_(("queued", "running"))
                        & (JobRow.lease_expires_at >= datetime.now(UTC)),
                        (JobRow.status == "complete") & (job.status == "failed"),
                    ),
                )
                .values(**values)
            )

    async def save_report(self, report: Report) -> None:
        async with self.sessions.begin() as session:
            session.add(ReportRow(id=report.id, payload=report.model_dump_json()))

    async def get_report(self, report_id: str) -> Report | None:
        async with self.sessions() as session:
            row = await session.get(ReportRow, report_id)
            return Report.model_validate_json(row.payload) if row else None

    async def reserve_budget(self, key: str, limit: int) -> bool:
        async with self.sessions() as session:
            session.add(BudgetRow(key=key, used=0))
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
            result = await session.execute(
                update(BudgetRow)
                .where(BudgetRow.key == key, BudgetRow.used < limit)
                .values(used=BudgetRow.used + 1)
                .returning(BudgetRow.used)
            )
            accepted = result.scalar_one_or_none() is not None
            await session.commit()
            return accepted

    async def renew_leases(self) -> None:
        async with self.sessions.begin() as session:
            expired = await session.scalar(
                select(JobRow.id)
                .where(
                    JobRow.owner_id == self.owner_id,
                    JobRow.status.in_(("queued", "running")),
                    JobRow.lease_expires_at < datetime.now(UTC),
                )
                .limit(1)
            )
            if expired:
                raise RuntimeError("Job lease expired.")
            await session.execute(
                update(JobRow)
                .where(JobRow.owner_id == self.owner_id, JobRow.status.in_(("queued", "running")))
                .values(lease_expires_at=datetime.now(UTC) + timedelta(seconds=60))
            )

    async def recover_interrupted(self) -> None:
        await self._interrupt(owned=False)

    async def release_owned(self) -> None:
        await self._interrupt(owned=True)

    async def _interrupt(self, *, owned: bool) -> None:
        # Conditional update prevents a heartbeat/status change racing with recovery.
        condition = (
            JobRow.owner_id == self.owner_id
            if owned
            else or_(JobRow.lease_expires_at.is_(None), JobRow.lease_expires_at < datetime.now(UTC))
        )
        async with self.sessions.begin() as session:
            rows = (
                await session.scalars(
                    select(JobRow).where(JobRow.status.in_(("queued", "running")), condition)
                )
            ).all()
            for row in rows:
                job = AnalysisJob.model_validate_json(row.payload).model_copy(
                    update={
                        "status": "failed",
                        "stage": "Interrupted",
                        "error": "Analysis worker stopped; please retry.",
                    }
                )
                await session.execute(
                    update(JobRow)
                    .where(JobRow.id == row.id, JobRow.status.in_(("queued", "running")), condition)
                    .values(status="failed", payload=job.model_dump_json(), cache_key=None)
                    .execution_options(synchronize_session=False)
                )
