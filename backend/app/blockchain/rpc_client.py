import asyncio
from typing import Any

import httpx


class RpcError(Exception):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


class RpcClient:
    def __init__(self, client: httpx.AsyncClient, url: str):
        self.client = client
        self.url = url
        self._id = 0
        self._semaphore = asyncio.Semaphore(8)

    async def call(self, method: str, params: list[Any]) -> Any:
        if method not in {
            "eth_chainId",
            "eth_blockNumber",
            "eth_getTransactionByHash",
            "eth_getTransactionReceipt",
            "eth_getBlockByNumber",
            "eth_getCode",
            "eth_getStorageAt",
            "eth_call",
            "eth_getLogs",
            "eth_getBalance",
            "debug_traceTransaction",
        }:
            raise RpcError("Only read-only RPC operations are permitted.")
        async with self._semaphore:
            for attempt in range(3):
                self._id += 1
                request_id = self._id
                try:
                    response = await self.client.post(
                        self.url,
                        json={
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "method": method,
                            "params": params,
                        },
                    )
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt < 2:
                            await asyncio.sleep(0.25 * (2**attempt))
                            continue
                    response.raise_for_status()
                    body = response.json()
                    if not isinstance(body, dict) or body.get("id") != request_id:
                        raise RpcError("Invalid RPC response envelope.")
                    if "error" in body:
                        raise RpcError(
                            "RPC provider could not complete the operation.",
                            body["error"].get("code"),
                        )
                    if "result" not in body:
                        raise RpcError("RPC result is missing.")
                    return body["result"]
                except (httpx.HTTPError, ValueError) as exc:
                    if attempt == 2:
                        # Do not leak credential-bearing URLs or provider error bodies.
                        raise RpcError(
                            "RPC provider is unavailable or returned invalid data."
                        ) from exc
                    await asyncio.sleep(0.25 * (2**attempt))
        raise RpcError("RPC retry budget exhausted.")
