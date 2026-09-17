from datetime import datetime
from typing import Literal

from app.models.base import FrozenModel
from app.models.blockchain import Contract, Coverage, DecodedEvidence, TxHash
from app.models.interpretation import Interpretation
from app.models.risk import RiskAssessment


class Report(FrozenModel):
    id: str
    schema_version: str = "1.0.0"
    created_at: datetime
    chain: str
    transaction_hash: TxHash
    explorer_url: str
    decoded: DecodedEvidence
    contracts: tuple[Contract, ...]
    coverage: tuple[Coverage, ...]
    risk: RiskAssessment
    interpretation: Interpretation


class AnalysisRequest(FrozenModel):
    chain: str
    transaction_hash: TxHash


class AnalysisJob(FrozenModel):
    id: str
    chain: str
    transaction_hash: TxHash
    status: Literal["queued", "running", "complete", "failed"]
    stage: str
    report_id: str | None = None
    error: str | None = None
