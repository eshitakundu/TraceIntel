import json

import httpx
import pytest
from app.blockchain.chains import chains
from app.blockchain.rpc_client import RpcClient, RpcError
from app.blockchain.transaction_fetcher import TransactionUnavailable, fetch_transaction
from app.config import Settings

HASH = "0x" + "a" * 64
BLOCK = "0x" + "b" * 64


@pytest.mark.asyncio
async def test_fetch_links_transaction_receipt_and_block() -> None:
    data = {
        "eth_chainId": "0x1",
        "eth_getTransactionByHash": {"hash": HASH, "blockHash": BLOCK, "blockNumber": "0x1"},
        "eth_getTransactionReceipt": {
            "transactionHash": HASH,
            "blockHash": BLOCK,
            "blockNumber": "0x1",
        },
        "eth_getBlockByNumber": {"hash": BLOCK},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(200, json={"id": body["id"], "result": data[body["method"]]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rpc = RpcClient(client, "https://rpc.invalid")
        result = await fetch_transaction(rpc, chains(Settings())["ethereum"], HASH)
        assert result.tx_hash == HASH
        data["eth_chainId"] = "0x8f"
        with pytest.raises(RpcError, match="network"):
            await fetch_transaction(rpc, chains(Settings())["ethereum"], HASH)
        data["eth_chainId"] = "0x1"
        data["eth_getTransactionReceipt"] = None  # type: ignore[assignment]
        with pytest.raises(TransactionUnavailable, match="pending"):
            await fetch_transaction(rpc, chains(Settings())["ethereum"], HASH)


@pytest.mark.asyncio
async def test_rpc_rejects_writes_and_hides_provider_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"id": 1, "error": {"code": -32601, "message": "private-secret"}}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rpc = RpcClient(client, "https://rpc.invalid/private-secret")
        with pytest.raises(RpcError, match="read-only"):
            await rpc.call("eth_sendRawTransaction", ["0x"])
        with pytest.raises(RpcError) as error:
            await rpc.call("debug_traceTransaction", [HASH])
        assert error.value.code == -32601
        assert "private-secret" not in str(error.value)
