from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from app.models.base import FrozenModel
from app.models.blockchain import Address, Coverage, Evidence, TxHash

Quantity = Annotated[str, Field(pattern=r"^(0|[1-9][0-9]*)$")]
ExposureStatus = Literal["ACTIVE", "PARTIALLY_ACTIVE", "REVOKED", "SUPERSEDED", "UNKNOWN"]


class HistoricalPermission(FrozenModel):
    token: Address
    owner: Address
    spender: Address
    allowance_raw: Quantity
    unlimited: bool
    block_number: int
    timestamp: int
    evidence_ids: tuple[str, ...]


class CurrentPermissionState(FrozenModel):
    allowance_raw: Quantity | None = None
    balance_raw: Quantity | None = None
    spender_has_code: bool | None = None
    symbol: str | None = None
    name: str | None = None
    decimals: int | None = None
    block_number: int | None = None
    block_hash: TxHash | None = None
    block_timestamp: int | None = None
    checked_at: datetime
    errors: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()


class PersistentExposure(FrozenModel):
    id: str
    historical: HistoricalPermission
    current: CurrentPermissionState
    status: ExposureStatus
    permission_active: bool | None
    summary: str
    evidence_ids: tuple[str, ...]


class ExposureEvidence(Evidence):
    """Immutable current-state observation, kept separate from historical evidence."""


class ExposureAnalysis(FrozenModel):
    version: str = "1.0.0"
    checked_at: datetime
    permissions: tuple[PersistentExposure, ...]
    evidence: tuple[ExposureEvidence, ...]
    coverage: Coverage
    limitations: tuple[str, ...] = (
        "Current means the recorded block, not a continuously monitored state.",
        "An Approval event is a reported allowance, not proof of standard token behavior.",
        "Matching amounts do not prove uninterrupted permission since the transaction.",
        "A reduced allowance may reflect spending or a later change; causation is not inferred.",
        "Zero balance or absent spender bytecode does not revoke a spending permission.",
        "Only ERC-20 event-pattern approvals are evaluated; other exposure types are not covered.",
    )
