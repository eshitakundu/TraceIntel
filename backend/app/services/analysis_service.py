import asyncio
import hashlib
import logging
import time
import traceback
from datetime import UTC, datetime
from uuid import uuid4

import httpx

from app.agents.catalog import build_catalog
from app.agents.service import interpret
from app.blockchain.calldata import decode_calldata
from app.blockchain.chains import chains
from app.blockchain.contract_inspector import inspect_contract
from app.blockchain.decoder import UnsupportedTransaction, decode_transaction
from app.blockchain.exposure_analyzer import analyze_exposure
from app.blockchain.rpc_client import RpcClient, RpcError
from app.blockchain.token_metadata import enrich_tokens
from app.blockchain.traces import fetch_traces
from app.blockchain.transaction_fetcher import TransactionUnavailable, fetch_transaction
from app.config import Settings
from app.models.blockchain import Coverage
from app.models.interpretation import Interpretation
from app.models.report import AnalysisJob, AnalysisRequest, Report
from app.risk.engine import evaluate
from app.services.repository import ReportRepository

logger = logging.getLogger(__name__)


class CapacityError(Exception):
    pass


class LeaseLost(Exception):
    """This process no longer owns the job; another worker may have recovered it."""


def failure_site(exc: BaseException) -> str:
    """Where an unexpected error happened, without its message.

    Exception messages can embed credential-bearing RPC URLs, so only the exception
    type and the innermost application frames are logged.
    """
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if "/app/" in f.filename]
    where = " <- ".join(f"{f.filename.rsplit('/app/', 1)[1]}:{f.lineno}" for f in frames[-3:])
    return f"{type(exc).__name__} at {where or 'unknown'}"


class AnalysisService:
    def __init__(self, repository: ReportRepository, settings: Settings, client: httpx.AsyncClient):
        self.repository, self.settings, self.client = repository, settings, client
        self.tasks: set[asyncio.Task[None]] = set()
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_analyses)

    async def submit(self, request: AnalysisRequest) -> AnalysisJob:
        if request.chain not in chains(self.settings):
            raise ValueError("Unsupported chain. Choose Ethereum or Monad.")
        if len(self.tasks) >= 16:
            raise CapacityError("Analysis queue is full. Please retry later.")
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        config_id = hashlib.sha256(
            f"{self.settings.openrouter_model}:{bool(self.settings.openrouter_api_key.get_secret_value())}:{self.settings.traces_enabled}:{bool(self.settings.explorer_api_key.get_secret_value())}".encode()
        ).hexdigest()[:12]
        snapshot_bucket = int(datetime.now(UTC).timestamp()) // 300
        key = (
            f"{request.chain}:{request.transaction_hash.lower()}:v1.3:{snapshot_bucket}:{config_id}"
        )
        job = AnalysisJob(
            id=str(uuid4()),
            chain=request.chain,
            transaction_hash=request.transaction_hash.lower(),
            status="queued",
            stage="Queued",
        )
        job, created = await self.repository.submit(job, key)
        if not created and job.status == "complete" and job.report_id:
            cached = await self.repository.get_report(job.report_id)
            if cached is not None:
                chain = chains(self.settings)[job.chain]
                rpc = RpcClient(self.client, chain.rpc_url.get_secret_value())
                current = await rpc.call(
                    "eth_getBlockByNumber", [hex(cached.decoded.transaction.block_number), False]
                )
                if not current or current.get("hash") != cached.decoded.transaction.block_hash:
                    if not await self.fail(job, "Cached block changed; reanalysis required."):
                        raise RpcError("Cached analysis could not be invalidated.")
                    return await self.submit(request)
        if created:
            if not await self.repository.reserve_budget(
                f"analyses:{day}", self.settings.daily_analyses
            ):
                failed = job.model_copy(
                    update={
                        "status": "failed",
                        "stage": "Capacity limit",
                        "error": "Daily analysis capacity reached. Try again tomorrow.",
                    }
                )
                await self.repository.update_job(failed)
                raise CapacityError(failed.error)
            task = asyncio.create_task(self.run(job, f"analyses:{day}"))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
        return job

    async def stage(self, job: AnalysisJob, stage: str) -> AnalysisJob:
        updated = job.model_copy(update={"status": "running", "stage": stage})
        if not await self.repository.update_job(updated):
            raise LeaseLost(job.id)
        logger.info("job=%s stage=%r", job.id, stage)
        return updated

    async def run(self, job: AnalysisJob, budget_key: str = "") -> None:
        started = time.monotonic()
        async with self.semaphore:
            try:
                async with asyncio.timeout(180):
                    await self._analyze(job)
                logger.info("job=%s complete ms=%d", job.id, (time.monotonic() - started) * 1000)
            except LeaseLost:
                logger.warning("job=%s lease lost; abandoning local work", job.id)
            except TransactionUnavailable as exc:
                # Nothing was analyzed, so a missing or pending hash does not spend daily capacity.
                if budget_key:
                    await self.repository.refund_budget(budget_key)
                await self.fail(job, str(exc))
            except (UnsupportedTransaction, RpcError) as exc:
                logger.info("job=%s failed: %s", job.id, type(exc).__name__)
                await self.fail(job, str(exc))
            except TimeoutError:
                logger.warning("job=%s timed out", job.id)
                await self.fail(job, "Analysis exceeded its time limit. Please retry.")
            except Exception as exc:
                logger.error("job=%s failed: %s", job.id, failure_site(exc))
                await self.fail(job, "Analysis could not complete safely. Please retry.")

    async def fail(self, job: AnalysisJob, reason: str) -> bool:
        return await self.repository.update_job(
            job.model_copy(update={"status": "failed", "stage": "Failed", "error": reason})
        )

    async def _analyze(self, job: AnalysisJob) -> None:
        chain = chains(self.settings)[job.chain]
        rpc = RpcClient(self.client, chain.rpc_url.get_secret_value())
        job = await self.stage(job, "Fetching transaction")
        raw = await fetch_transaction(rpc, chain, job.transaction_hash)
        job = await self.stage(job, "Decoding calldata and event logs")
        decoded = decode_transaction(raw)
        job = await self.stage(job, "Inspecting contracts")
        addresses = list(
            dict.fromkeys(
                address
                for address in [
                    decoded.transaction.recipient or decoded.transaction.created_contract,
                    *(a.spender for a in decoded.approvals),
                    *(a.token for a in decoded.approvals),
                    *(m.token for m in decoded.movements if m.standard != "native"),
                ]
                if address
            )
        )
        results = await asyncio.gather(
            *(
                inspect_contract(
                    rpc,
                    self.client,
                    chain,
                    address,
                    hex(decoded.transaction.block_number),
                    f"{job.chain}:{job.transaction_hash}",
                    self.settings.explorer_api_key.get_secret_value(),
                )
                for address in addresses[:16]
            )
        )
        decoded = await enrich_tokens(decoded, rpc, f"{job.chain}:{job.transaction_hash}")
        contracts = tuple(item[0] for item in results)
        target_contract = next(
            (c for c in contracts if c.address == decoded.transaction.recipient), None
        )
        if target_contract and target_contract.abi_json:
            function, arguments = decode_calldata(
                decoded.transaction.calldata, target_contract.abi_json
            )
            decoded = decoded.model_copy(
                update={
                    "transaction": decoded.transaction.model_copy(
                        update={"function": function, "arguments_json": arguments}
                    )
                }
            )
        contract_evidence = tuple(e for item in results for e in item[1])
        coverage = decoded.coverage + tuple(c for item in results for c in item[2])
        if len(addresses) > 16:
            coverage += (
                Coverage(
                    area="contracts",
                    status="partial",
                    reason=f"Inspected 16/{len(addresses)} addresses; others unknown.",
                ),
            )
        movements, trace_evidence, trace_coverage = await fetch_traces(
            rpc,
            job.transaction_hash,
            f"{job.chain}:{job.transaction_hash}",
            self.settings.traces_enabled,
        )
        coverage += (trace_coverage,)
        decoded = decoded.model_copy(
            update={
                "movements": decoded.movements + movements,
                "evidence": decoded.evidence + contract_evidence + trace_evidence,
            }
        )
        job = await self.stage(job, "Evaluating deterministic signals")
        risk = evaluate(decoded, contracts)
        job = await self.stage(job, "Checking current approval exposure")
        exposure = await analyze_exposure(decoded, rpc, f"{job.chain}:{job.transaction_hash}")
        coverage += (exposure.coverage,)
        job = await self.stage(job, "Running NOOA intelligence analysis")
        catalog = build_catalog(decoded, risk, contracts, coverage, exposure)
        interpretation = Interpretation(status="unavailable", reason="Model/key is not configured.")
        if self.settings.openrouter_api_key.get_secret_value() and self.settings.openrouter_model:
            day = datetime.now(UTC).strftime("%Y-%m-%d")
            if await self.repository.reserve_budget(f"llm:{day}", self.settings.daily_llm_analyses):
                interpretation = await interpret(
                    catalog, self.settings, any(c.kind == "contract" for c in contracts)
                )
            else:
                interpretation = Interpretation(
                    status="unavailable", reason="Daily interpretation budget reached."
                )
        job = await self.stage(job, "Generating report")
        report = Report(
            id=job.id,
            created_at=datetime.now(UTC),
            chain=job.chain,
            transaction_hash=job.transaction_hash,
            explorer_url=f"{chain.explorer_url}/tx/{job.transaction_hash}",
            decoded=decoded,
            contracts=contracts,
            coverage=coverage,
            risk=risk,
            interpretation=interpretation,
            exposure=exposure,
        )
        await self.repository.save_report(report)
        if not await self.repository.update_job(
            job.model_copy(
                update={"status": "complete", "stage": "Complete", "report_id": report.id}
            )
        ):
            raise LeaseLost(job.id)

    async def close(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
