"""Capture public, reproducible chain evidence; never reads or writes private keys."""

import asyncio
from pathlib import Path

import httpx
from app.blockchain.chains import chains
from app.blockchain.rpc_client import RpcClient
from app.blockchain.transaction_fetcher import fetch_transaction
from app.config import Settings


async def main() -> None:
    async with httpx.AsyncClient(timeout=20) as client:
        for chain in chains(Settings()).values():
            rpc = RpcClient(client, chain.rpc_url.get_secret_value())
            block = await rpc.call("eth_getBlockByNumber", ["finalized", False])
            if not block or not block["transactions"]:
                block = await rpc.call("eth_getBlockByNumber", ["latest", False])
            raw = await fetch_transaction(rpc, chain, block["transactions"][0])
            target = Path("evals/cases") / f"{chain.slug}-recorded.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(raw.model_dump_json(indent=2) + "\n")
            print(chain.slug, raw.tx_hash)


if __name__ == "__main__":
    asyncio.run(main())
