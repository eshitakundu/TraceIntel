import asyncio
from types import SimpleNamespace

import pytest
from app.main import MAX_MISSED_HEARTBEATS, lease_heartbeat


class FlakyRepository:
    """Fails the first `failures` renewals, then signals once `beats` have happened."""

    def __init__(self, failures: int, beats: int) -> None:
        self.failures, self.beats, self.calls = failures, beats, 0
        self.done = asyncio.Event()

    async def renew_leases(self) -> None:
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("database stall")

    async def recover_interrupted(self) -> None:
        if self.calls >= self.beats:
            self.done.set()


class Analysis:
    closed = 0

    def __init__(self) -> None:
        self.tasks: set[object] = {object()}

    async def close(self) -> None:
        self.closed += 1


async def run_heartbeat(failures: int, beats: int) -> SimpleNamespace:
    state = SimpleNamespace(lease_healthy=True, analysis=Analysis())
    repository = FlakyRepository(failures, beats)
    task = asyncio.create_task(
        lease_heartbeat(state, repository, interval=0.001)  # type: ignore[arg-type]
    )
    await asyncio.wait_for(repository.done.wait(), timeout=5)
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    return state


@pytest.mark.asyncio
async def test_transient_heartbeat_failure_heals_without_cancelling_work() -> None:
    state = await run_heartbeat(failures=1, beats=3)
    assert state.lease_healthy is True
    assert state.analysis.closed == 0


@pytest.mark.asyncio
async def test_sustained_failure_stops_local_work_then_recovers() -> None:
    state = await run_heartbeat(failures=MAX_MISSED_HEARTBEATS, beats=MAX_MISSED_HEARTBEATS + 2)
    assert state.analysis.closed == 1
    assert state.lease_healthy is True


@pytest.mark.asyncio
async def test_idle_worker_does_not_query_database_but_resumes_for_work() -> None:
    analysis = Analysis()
    analysis.tasks.clear()
    state = SimpleNamespace(lease_healthy=True, analysis=analysis)
    repository = FlakyRepository(failures=0, beats=1)
    task = asyncio.create_task(lease_heartbeat(state, repository, interval=0.001))
    try:
        await asyncio.sleep(0.03)
        assert repository.calls == 0
        analysis.tasks.add(object())
        await asyncio.wait_for(repository.done.wait(), timeout=5)
        assert repository.calls >= 1
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_unhealthy_idle_worker_still_retries_database() -> None:
    analysis = Analysis()
    analysis.tasks.clear()
    state = SimpleNamespace(lease_healthy=False, analysis=analysis)
    repository = FlakyRepository(failures=0, beats=1)
    task = asyncio.create_task(lease_heartbeat(state, repository, interval=0.001))
    try:
        await asyncio.wait_for(repository.done.wait(), timeout=5)
        await asyncio.sleep(0)
        assert state.lease_healthy is True
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
