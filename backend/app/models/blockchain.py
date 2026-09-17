import json
from typing import Annotated, Any, Literal

from pydantic import Field

from app.models.base import FrozenModel

TxHash = Annotated[str, Field(pattern=r"^0x[0-9a-fA-F]{64}$")]
Address = Annotated[str, Field(pattern=r"^0x[0-9a-fA-F]{40}$")]


class Evidence(FrozenModel):
    id: str
    source: str
    description: str
    # JSON text avoids the shallow immutability of a frozen model containing a dict.
    data_json: str

    def data(self) -> dict[str, Any]:
        value: dict[str, Any] = json.loads(self.data_json)
        return value


class Coverage(FrozenModel):
    area: str
    status: Literal["available", "partial", "unavailable", "not_applicable"]
    reason: str


class RawTransaction(FrozenModel):
    chain: str
    tx_hash: TxHash
    transaction_json: str
    receipt_json: str
    block_json: str


class Transaction(FrozenModel):
    hash: TxHash
    sender: Address
    recipient: Address | None
    created_contract: Address | None
    nonce: int
    value_wei: str
    gas_used: int
    gas_price_wei: str
    gas_fee_wei: str
    status: Literal["success", "failed"]
    block_number: int
    block_hash: TxHash
    timestamp: int
    selector: str | None
    function: str | None
    arguments_json: str | None = None
    calldata: str
    evidence_ids: tuple[str, ...]


class Movement(FrozenModel):
    standard: Literal["native", "ERC20", "ERC721", "ERC1155"]
    token: str
    sender: str
    recipient: str
    amount_raw: str
    token_id: str | None = None
    symbol: str | None = None
    decimals: int | None = None
    evidence_ids: tuple[str, ...]


class Approval(FrozenModel):
    standard: Literal["ERC20", "ERC721", "operator"]
    token: str
    owner: str
    spender: str
    amount_raw: str
    unlimited: bool
    evidence_ids: tuple[str, ...]


class Contract(FrozenModel):
    address: Address
    kind: Literal["contract", "no_code", "unknown"]
    verification: Literal["verified", "unverified", "unavailable"] = "unavailable"
    name: str | None = None
    proxy: Literal["eip1967", "beacon", "not_detected", "unknown"] = "unknown"
    implementation: str | None = None
    abi_json: str | None = None
    evidence_ids: tuple[str, ...] = ()


class DecodedEvidence(FrozenModel):
    transaction: Transaction
    movements: tuple[Movement, ...]
    approvals: tuple[Approval, ...]
    evidence: tuple[Evidence, ...]
    coverage: tuple[Coverage, ...]
