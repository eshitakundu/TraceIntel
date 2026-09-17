import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.agents.catalog import build_catalog
from app.blockchain.decoder import decode_transaction
from app.blockchain.exposure_analyzer import analyze_exposure, compare_permission
from app.blockchain.rpc_client import RpcClient
from app.models.blockchain import RawTransaction
from app.models.exposure import CurrentPermissionState, HistoricalPermission
from app.risk.engine import evaluate
from eth_abi.abi import encode

CASES = json.loads(Path("evals/cases/exposure-transitions.json").read_text())["cases"]
RECORDED = Path("evals/cases/ethereum-approval.json").read_text()
NOW = datetime(2026, 9, 17, tzinfo=UTC)
ADDRESS = "0x" + "a" * 40
BLOCK = "0x" + "b" * 64


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_exposure_transition_golden(case: dict[str, Any]) -> None:
    historical = HistoricalPermission(
        token=ADDRESS,
        owner=ADDRESS,
        spender=ADDRESS,
        allowance_raw=case["historical"],
        unlimited=int(case["historical"]) == 2**256 - 1,
        block_number=1,
        timestamp=1,
        evidence_ids=("historical:approval",),
    )
    current = CurrentPermissionState(
        checked_at=NOW,
        allowance_raw=case["current"],
        balance_raw="0",
        spender_has_code=False,
        evidence_ids=("current:allowance",),
    )
    exposure = compare_permission("permission", historical, current)
    assert exposure.status == case["status"]
    assert exposure.permission_active is case["active"]
    assert exposure.evidence_ids == ("historical:approval", "current:allowance")
    replaced = compare_permission("permission", historical, current, ("later:approval",))
    assert replaced.status == "SUPERSEDED"
    assert "later:approval" in replaced.evidence_ids


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["none", "balance", "allowance", "reorg", "block"])
async def test_current_state_reads_are_pinned_and_failures_are_explicit(failure: str) -> None:
    raw = RawTransaction.model_validate_json(RECORDED)
    decoded = decode_transaction(raw)
    before = decoded.model_dump_json()
    risk = evaluate(decoded, ())
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        method, params = body["method"], body["params"]
        result: Any
        if method == "eth_getBlockByNumber":
            if failure == "block":
                result = None
            else:
                result = {
                    "number": hex(decoded.transaction.block_number + 100),
                    "hash": "0x" + "c" * 64
                    if failure == "reorg" and params[0] != "latest"
                    else BLOCK,
                    "timestamp": hex(decoded.transaction.timestamp + 1200),
                }
        else:
            assert params[-1] == {"blockHash": BLOCK, "requireCanonical": True}
            if method == "eth_getCode":
                result = "0x"
            else:
                data = params[0]["data"]
                selector = data[:10]
                assert selector in {
                    "0xdd62ed3e",
                    "0x70a08231",
                    "0x95d89b41",
                    "0x06fdde03",
                    "0x313ce567",
                }
                if selector == "0xdd62ed3e":
                    assert len(data) == 138
                    result = "0x" + encode(["uint256"], [200]).hex()
                    if failure == "allowance":
                        result = "0x"  # Unsupported token response must not become zero.
                elif selector == "0x70a08231":
                    result = "0x" + encode(["uint256"], [0]).hex()
                    if failure == "balance":
                        return httpx.Response(
                            200, json={"id": body["id"], "error": {"code": -32000}}
                        )
                elif selector == "0x313ce567":
                    result = "0x" + encode(["uint256"], [6]).hex()
                else:
                    result = "0x" + encode(["string"], ["TEST"]).hex()
        return httpx.Response(200, json={"id": body["id"], "result": result})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await analyze_exposure(decoded, RpcClient(client, "https://rpc.invalid"), "test")
    assert decoded.model_dump_json() == before
    assert evaluate(decoded, ()) == risk
    assert len(result.permissions) == 13
    ids = {e.id for e in result.evidence} | {e.id for e in decoded.evidence}
    assert all(set(p.evidence_ids) <= ids for p in result.permissions)
    if failure in ("block", "reorg", "allowance"):
        assert all(p.current.allowance_raw is None for p in result.permissions)
        assert result.coverage.status == "unavailable"
    else:
        assert all(p.permission_active is True for p in result.permissions)
        assert all(p.current.spender_has_code is False for p in result.permissions)
        assert result.coverage.status == ("partial" if failure == "balance" else "available")
    if failure in ("block", "reorg"):
        assert not result.evidence
    catalog = build_catalog(decoded, risk, (), (), result)
    assert any(c.id.startswith("exposure:") for c in catalog)
    assert all(set(c.evidence_ids) <= ids for c in catalog)
