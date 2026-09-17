import asyncio
import json
from pathlib import Path

import httpx
import pytest
from app.blockchain.calldata import decode_calldata
from app.blockchain.decoder import decode_transaction
from app.blockchain.rpc_client import RpcClient
from app.blockchain.token_metadata import enrich_tokens
from app.blockchain.traces import fetch_traces
from app.models.blockchain import Movement, RawTransaction
from eth_abi.abi import encode


def test_calldata_keeps_large_integers_exact() -> None:
    address = "0x" + "a" * 40
    amount = 2**256 - 1
    calldata = "0x095ea7b3" + encode(["address", "uint256"], [address, amount]).hex()
    function, arguments = decode_calldata(calldata)
    assert function == "approve(address,uint256)"
    assert arguments and json.loads(arguments)[1]["value"] == str(amount)
    assert decode_calldata("0x095ea7b300") == (None, None)


@pytest.mark.asyncio
async def test_token_metadata_and_unavailable_calls() -> None:
    raw = RawTransaction.model_validate_json(
        await asyncio.to_thread(Path("evals/cases/ethereum-recorded.json").read_text)
    )
    decoded = decode_transaction(raw)
    token = "0x" + "a" * 40
    movement = Movement(
        standard="ERC20",
        token=token,
        sender=token,
        recipient=token,
        amount_raw="1000000",
        evidence_ids=("log:1",),
    )
    decoded = decoded.model_copy(update={"movements": (movement,)})

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["params"][1] == hex(decoded.transaction.block_number)
        value = (
            encode(["uint256"], [6])
            if body["params"][0]["data"] == "0x313ce567"
            else (encode(["string"], ["USDC"]))
        )
        return httpx.Response(200, json={"id": body["id"], "result": "0x" + value.hex()})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        enriched = await enrich_tokens(decoded, RpcClient(client, "https://rpc.invalid"), "test")
    assert enriched.movements[0].decimals == 6
    assert enriched.movements[0].amount_raw == "1000000"
    assert enriched.movements[0].symbol == "USDC"
    assert decoded.movements[0].decimals is None


@pytest.mark.asyncio
async def test_traces_exclude_reverted_subtrees_and_delegate_value() -> None:
    address = "0x" + "a" * 40
    trace = {
        "type": "CALL",
        "from": address,
        "to": address,
        "value": "0xa",
        "calls": [
            {"type": "CALL", "from": address, "to": address, "value": "0x5"},
            {"type": "DELEGATECALL", "from": address, "to": address, "value": "0xa"},
            {
                "type": "CALL",
                "error": "execution reverted",
                "calls": [{"type": "CALL", "from": address, "to": address, "value": "0x8"}],
            },
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": json.loads(request.content)["id"], "result": trace})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        movements, evidence, coverage = await fetch_traces(
            RpcClient(client, "https://rpc.invalid"), "0x" + "a" * 64, "test", True
        )
    assert [m.amount_raw for m in movements] == ["5"]
    assert movements[0].evidence_ids == (evidence[0].id,)
    assert coverage.status == "partial"
