import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from uuid import uuid4

import httpx

from app.agents.catalog import build_catalog
from app.agents.service import interpret
from app.blockchain.calldata import decode_calldata
from app.blockchain.chains import chains
from app.blockchain.contract_inspector import inspect_contract
from app.blockchain.decoder import decode_transaction
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
            f"{self.settings.openrouter_model}:{bool(self.settings.openrouter_api_key.get_secret_value())}".encode()
        ).hexdigest()[:12]
        key = f"{request.chain}:{request.transaction_hash.lower()}:v1.1:{day}:{config_id}"
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
                    await self.fail(job, "Cached block changed; a fresh analysis is required.")
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
            task = asyncio.create_task(self.run(job))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
        return job

    async def stage(self, job: AnalysisJob, stage: str) -> AnalysisJob:
        updated = job.model_copy(update={"status": "running", "stage": stage})
        await self.repository.update_job(updated)
        return updated

    async def run(self, job: AnalysisJob) -> None:
        async with self.semaphore:
            try:
                async with asyncio.timeout(180):
                    await self._analyze(job)
            except (TransactionUnavailable, RpcError) as exc:
                await self.fail(job, str(exc))
            except TimeoutError:
                await self.fail(job, "Analysis exceeded its time limit. Please retry.")
            except Exception as exc:
                logger.error("Analysis failed (%s)", type(exc).__name__)
                await self.fail(job, "Analysis could not complete safely. Please retry.")

    async def fail(self, job: AnalysisJob, reason: str) -> None:
        await self.repository.update_job(
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
        job = await self.stage(job, "Running NOOA intelligence analysis")
        catalog = build_catalog(decoded, risk, contracts, coverage)
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
        )
        await self.repository.save_report(report)
        await self.repository.update_job(
            job.model_copy(
                update={"status": "complete", "stage": "Complete", "report_id": report.id}
            )
        )

    async def close(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
