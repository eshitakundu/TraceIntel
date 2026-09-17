"""Deterministic ERC-20 permission comparison at one revalidated chain block."""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from eth_abi.abi import decode
from eth_abi.exceptions import DecodingError

from app.blockchain.rpc_client import RpcClient, RpcError
from app.models.blockchain import Approval, Coverage, DecodedEvidence
from app.models.exposure import (
    CurrentPermissionState,
    ExposureAnalysis,
    ExposureEvidence,
    ExposureStatus,
    HistoricalPermission,
    PersistentExposure,
)

CURRENT_STATE_TIMEOUT = 30


def compare_permission(
    identifier: str,
    historical: HistoricalPermission,
    current: CurrentPermissionState,
    superseded_ids: tuple[str, ...] = (),
) -> PersistentExposure:
    before = int(historical.allowance_raw)
    now = int(current.allowance_raw) if current.allowance_raw is not None else None
    active = now > 0 if now is not None else None
    status: ExposureStatus
    if superseded_ids:
        status = "SUPERSEDED"
        summary = (
            "A later Approval event in this transaction replaced this event's reported amount."
        )
    elif now is None:
        status = "UNKNOWN"
        summary = "Current allowance could not be determined. Active permission is unknown."
    elif now == 0:
        status = "REVOKED"
        summary = (
            "The current allowance is zero; this permission is inactive at the checked block. "
            "Spending or a later change may have cleared it."
        )
    elif now < before:
        status = "PARTIALLY_ACTIVE"
        summary = "The allowance is reduced, but spending permission remains active."
    elif now > before:
        status = "SUPERSEDED"
        summary = (
            "The current allowance exceeds this event's amount. A different allowance is active; "
            "the original amount no longer describes it."
        )
    else:
        status = "ACTIVE"
        summary = (
            "The historical unlimited amount matches the active allowance at the checked block."
            if historical.unlimited
            else "An allowance matching this transaction's approval is active at the checked block."
        )
    return PersistentExposure(
        id=identifier,
        historical=historical,
        current=current,
        status=status,
        permission_active=active,
        summary=summary,
        evidence_ids=historical.evidence_ids + current.evidence_ids + superseded_ids,
    )


def _uint(value: Any) -> str:
    if not isinstance(value, str) or not value.startswith("0x") or len(value) != 66:
        raise ValueError("Non-standard uint256 response")
    return str(int(value, 16))


def _label(value: Any) -> str:
    data = bytes.fromhex(value[2:])
    text = data.rstrip(b"\0").decode() if len(data) == 32 else str(decode(["string"], data)[0])
    if not text or len(text) > 128 or not text.isprintable():
        raise ValueError("Invalid token label")
    return text


async def analyze_exposure(
    decoded: DecodedEvidence, rpc: RpcClient, prefix: str
) -> ExposureAnalysis:
    checked_at = datetime.now(UTC)
    approvals = [a for a in decoded.approvals if a.standard == "ERC20"]
    if not approvals:
        return ExposureAnalysis(
            checked_at=checked_at,
            permissions=(),
            evidence=(),
            coverage=Coverage(
                area="persistent_exposure",
                status="not_applicable",
                reason="No ERC-20 approvals decoded; other exposure types are not evaluated.",
            ),
        )
    keys = list(dict.fromkeys((a.token, a.owner, a.spender) for a in approvals))
    evidence: list[ExposureEvidence] = []
    states: dict[tuple[str, str, str], CurrentPermissionState] = {}
    block: dict[str, Any] | None = None
    try:
        async with asyncio.timeout(CURRENT_STATE_TIMEOUT):
            candidate = await rpc.call("eth_getBlockByNumber", ["latest", False])
            number, block_hash, timestamp = (
                int(candidate["number"], 16),
                candidate["hash"],
                int(candidate["timestamp"], 16),
            )
            if number < decoded.transaction.block_number:
                raise ValueError("Current block predates transaction")
            # Validate the provider hash before using it as provenance.
            CurrentPermissionState(checked_at=checked_at, block_hash=block_hash)
            block = candidate
            tag = {"blockHash": block_hash, "requireCanonical": True}
            snapshot_id = f"{prefix}:now:{block_hash}:block"
            evidence.append(
                ExposureEvidence(
                    id=snapshot_id,
                    source="eth_getBlockByNumber",
                    description="Current-state reference block, revalidated after reads",
                    data_json=json.dumps(
                        {"number": number, "hash": block_hash, "timestamp": timestamp}
                    ),
                )
            )

            async def inspect(
                key: tuple[str, str, str],
            ) -> tuple[CurrentPermissionState, ExposureEvidence]:
                token, owner, spender = key
                queries: dict[str, tuple[str, list[Any]]] = {
                    "allowance": (
                        "eth_call",
                        [
                            {
                                "to": token,
                                "data": "0xdd62ed3e" + owner[2:].zfill(64) + spender[2:].zfill(64),
                            },
                            tag,
                        ],
                    ),
                    "balance": (
                        "eth_call",
                        [{"to": token, "data": "0x70a08231" + owner[2:].zfill(64)}, tag],
                    ),
                    "spender_code": ("eth_getCode", [spender, tag]),
                    "symbol": ("eth_call", [{"to": token, "data": "0x95d89b41"}, tag]),
                    "name": ("eth_call", [{"to": token, "data": "0x06fdde03"}, tag]),
                    "decimals": ("eth_call", [{"to": token, "data": "0x313ce567"}, tag]),
                }
                values: dict[str, Any] = {}
                errors: list[str] = []

                async def read(name: str, method: str, params: list[Any]) -> None:
                    try:
                        raw = await rpc.call(method, params)
                        if name in ("allowance", "balance", "decimals"):
                            parsed: Any = _uint(raw)
                            if name == "decimals":
                                parsed = int(parsed)
                                if parsed > 255:
                                    raise ValueError("Invalid decimals")
                        elif name == "spender_code":
                            if not isinstance(raw, str) or not raw.startswith("0x"):
                                raise ValueError("Invalid bytecode")
                            parsed = bool(bytes.fromhex(raw[2:]))
                        else:
                            parsed = _label(raw)
                        values[name] = {"raw": raw, "value": parsed}
                    except (
                        RpcError,
                        ValueError,
                        TypeError,
                        AttributeError,
                        DecodingError,
                        UnicodeError,
                    ):
                        errors.append(f"{name} unavailable or non-standard")

                await asyncio.gather(
                    *(read(name, method, params) for name, (method, params) in queries.items())
                )
                eid = f"{prefix}:now:{block_hash}:{token}:{owner}:{spender}"

                def value(name: str) -> Any:
                    return values.get(name, {}).get("value")

                state = CurrentPermissionState(
                    allowance_raw=value("allowance"),
                    balance_raw=value("balance"),
                    spender_has_code=value("spender_code"),
                    symbol=value("symbol"),
                    name=value("name"),
                    decimals=value("decimals"),
                    block_number=number,
                    block_hash=block_hash,
                    block_timestamp=timestamp,
                    checked_at=checked_at,
                    errors=tuple(sorted(errors)),
                    evidence_ids=(snapshot_id, eid),
                )
                item = ExposureEvidence(
                    id=eid,
                    source="eth_call allowance/balanceOf/metadata + eth_getCode",
                    description="Current ERC-20 permission observation; token-reported values",
                    data_json=json.dumps(
                        {
                            "token": token,
                            "owner": owner,
                            "spender": spender,
                            "block_number": number,
                            "block_hash": block_hash,
                            "queries": queries,
                            "results": values,
                            "errors": sorted(errors),
                        }
                    ),
                )
                return state, item

            results = await asyncio.gather(*(inspect(key) for key in keys[:16]))
            for key, (state, item) in zip(keys, results, strict=False):
                states[key] = state
                evidence.append(item)
            after = await rpc.call("eth_getBlockByNumber", [hex(number), False])
            if not after or after.get("hash") != block_hash:
                raise ValueError("Current block changed during reads")
    except (RpcError, ValueError, TypeError, KeyError, TimeoutError):
        states.clear()
        # Do not present inconsistent state as valid evidence after a reorganization.
        evidence.clear()
        block = None
    for key in keys:
        if key not in states:
            states[key] = CurrentPermissionState(
                checked_at=checked_at,
                errors=(
                    "Current block unavailable/inconsistent."
                    if block is None
                    else "Current-state query limit reached (16 distinct permissions).",
                ),
            )
    last: dict[tuple[str, str, str], Approval] = {
        (a.token, a.owner, a.spender): a for a in approvals
    }
    permissions = []
    for index, approval in enumerate(approvals):
        key = (approval.token, approval.owner, approval.spender)
        latest = last[key]
        historical = HistoricalPermission(
            token=approval.token,
            owner=approval.owner,
            spender=approval.spender,
            allowance_raw=approval.amount_raw,
            unlimited=approval.unlimited,
            block_number=decoded.transaction.block_number,
            timestamp=decoded.transaction.timestamp,
            evidence_ids=approval.evidence_ids,
        )
        permissions.append(
            compare_permission(
                f"{prefix}:permission:{index}",
                historical,
                states[key],
                latest.evidence_ids if latest is not approval else (),
            )
        )
    known = sum(s.allowance_raw is not None for s in states.values())
    full = all(not s.errors for s in states.values())
    return ExposureAnalysis(
        checked_at=checked_at,
        permissions=tuple(permissions),
        evidence=tuple(evidence),
        coverage=Coverage(
            area="persistent_exposure",
            status="available" if full else "partial" if known else "unavailable",
            reason=f"Current allowance resolved for {known}/{len(keys)} distinct permissions. "
            "Other query gaps are listed separately. Historical risk is unchanged.",
        ),
    )
