from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.models.report import AnalysisJob, Report
from app.storage.tables import BudgetRow, JobRow, ReportRow


class SqlReportRepository:
    def __init__(self, engine: AsyncEngine):
        self.sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def submit(self, job: AnalysisJob, cache_key: str) -> tuple[AnalysisJob, bool]:
        async with self.sessions() as session:
            found = await session.scalar(select(JobRow).where(JobRow.cache_key == cache_key))
            if found:
                return AnalysisJob.model_validate_json(found.payload), False
            session.add(
                JobRow(
                    id=job.id, cache_key=cache_key, status=job.status, payload=job.model_dump_json()
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
            await session.execute(update(JobRow).where(JobRow.id == job.id).values(**values))

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

    async def recover_interrupted(self) -> None:
        async with self.sessions() as session:
            rows = (
                await session.scalars(
                    select(JobRow).where(JobRow.status.in_(("queued", "running")))
                )
            ).all()
            for row in rows:
                job = AnalysisJob.model_validate_json(row.payload).model_copy(
                    update={
                        "status": "failed",
                        "error": "API restarted during analysis; please retry.",
                        "stage": "Interrupted",
                    }
                )
                row.status, row.payload, row.cache_key = "failed", job.model_dump_json(), None
            await session.commit()
