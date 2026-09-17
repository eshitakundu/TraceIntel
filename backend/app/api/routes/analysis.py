import hashlib
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.api.protection import trusted_proxy
from app.blockchain.chains import chains
from app.blockchain.rpc_client import RpcError
from app.models.report import AnalysisJob, AnalysisRequest, Report
from app.services.analysis_service import AnalysisService, CapacityError

router = APIRouter()


def service(request: Request) -> AnalysisService:
    value: AnalysisService = request.app.state.analysis
    return value


@router.get("/chains", tags=["networks"])
async def supported_chains(request: Request) -> list[dict[str, str | int]]:
    return [
        {
            "slug": chain.slug,
            "name": chain.name,
            "chain_id": chain.chain_id,
            "native_symbol": chain.native_symbol,
            "explorer_url": chain.explorer_url,
        }
        for chain in chains(service(request).settings).values()
    ]


@router.post("/analyses", response_model=AnalysisJob, status_code=202, tags=["analysis"])
async def analyze(payload: AnalysisRequest, request: Request) -> AnalysisJob:
    app = service(request)
    ip = request.client.host if request.client else "unknown"
    if trusted_proxy(request, app.settings):
        ip = request.headers.get("x-traceintel-client-ip", ip)
    hour = datetime.now(UTC).strftime("%Y-%m-%dT%H")
    key = f"ip:{hashlib.sha256(ip.encode()).hexdigest()}:{hour}"
    if not await app.repository.reserve_budget(key, app.settings.requests_per_hour):
        raise HTTPException(429, "Hourly request limit reached.", headers={"Retry-After": "3600"})
    try:
        return await app.submit(payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RpcError as exc:
        raise HTTPException(503, "Cached evidence could not be revalidated. Retry later.") from exc
    except CapacityError as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": "60"}) from exc


@router.get("/analyses/{job_id}", response_model=AnalysisJob, tags=["analysis"])
async def get_analysis(job_id: UUID, request: Request) -> AnalysisJob:
    job = await service(request).repository.get_job(str(job_id))
    if job is None:
        raise HTTPException(404, "Analysis not found.")
    return job


@router.get("/reports/{report_id}", response_model=Report, tags=["reports"])
async def get_report(report_id: UUID, request: Request) -> Report:
    report = await service(request).repository.get_report(str(report_id))
    if report is None:
        raise HTTPException(404, "Report not found.")
    return report


@router.get("/reports/{report_id}/download", tags=["reports"])
async def download_report(report_id: UUID, request: Request) -> Response:
    report = await get_report(report_id, request)
    return Response(
        report.model_dump_json(indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="traceintel-{report_id}.json"'},
    )
