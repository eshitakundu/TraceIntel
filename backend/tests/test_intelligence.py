import json
from pathlib import Path

import httpx
import pytest
from app.blockchain.chains import chains
from app.blockchain.contract_inspector import inspect_contract
from app.blockchain.decoder import decode_transaction
from app.blockchain.proxy_detector import storage_address
from app.blockchain.rpc_client import RpcClient
from app.config import Settings
from app.models.blockchain import Approval, Contract, RawTransaction
from app.risk.engine import evaluate


def test_proxy_address_and_invalid_padding() -> None:
    assert storage_address("0x" + "0" * 64) is None
    assert storage_address("0x" + "0" * 24 + "a" * 40) == "0x" + "a" * 40
    with pytest.raises(ValueError):
        storage_address("0x" + "f" * 64)


@pytest.mark.asyncio
async def test_missing_explorer_is_not_unverified() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        value = "0x6000" if body["method"] == "eth_getCode" else "0x" + "0" * 64
        return httpx.Response(200, json={"id": body["id"], "result": value})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        contract, evidence, coverage = await inspect_contract(
            RpcClient(client, "https://rpc.invalid"),
            client,
            chains(Settings())["ethereum"],
            "0x" + "1" * 40,
            "0x1",
            "test",
        )
        assert contract.kind == "contract"
        assert contract.verification == "unavailable"
        assert any(c.area.startswith("explorer") and c.status == "unavailable" for c in coverage)
        assert evidence[0].source == "eth_getCode"


def test_risk_deduplicates_and_preserves_unknowns() -> None:
    raw = RawTransaction.model_validate_json(Path("evals/cases/ethereum-recorded.json").read_text())
    decoded = decode_transaction(raw)
    approval = Approval(
        standard="ERC20",
        token="0x" + "1" * 40,
        owner="0x" + "2" * 40,
        spender="0x" + "3" * 40,
        amount_raw=str(2**256 - 1),
        unlimited=True,
        evidence_ids=("synthetic:approval",),
    )
    decoded = decoded.model_copy(update={"approvals": (approval, approval)})
    result = evaluate(decoded, ())
    assert result.score == 30
    unknown = Contract(address=decoded.transaction.recipient or "0x" + "4" * 40, kind="unknown")
    assert evaluate(decoded, (unknown,)).score == 30
    assert all(signal.score >= 0 for signal in result.signals)
    assert not any(s.code == "UNVERIFIED_TARGET" for s in evaluate(decoded, (unknown,)).signals)
