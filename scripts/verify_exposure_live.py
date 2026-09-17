"""Opt-in current-state RPC check; no model calls or secrets in output."""

import asyncio
import json
from pathlib import Path

import httpx
from app.blockchain.chains import chains
from app.blockchain.decoder import decode_transaction
from app.blockchain.exposure_analyzer import analyze_exposure
from app.blockchain.rpc_client import RpcClient
from app.config import Settings
from app.models.blockchain import RawTransaction


async def main() -> None:
    raw = RawTransaction.model_validate_json(
        await asyncio.to_thread(Path("evals/cases/ethereum-approval.json").read_text)
    )
    decoded = decode_transaction(raw)
    async with httpx.AsyncClient(timeout=15) as client:
        rpc = RpcClient(client, chains(Settings())["ethereum"].rpc_url.get_secret_value())
        result = await analyze_exposure(decoded, rpc, "ethereum:" + raw.tx_hash)
    await asyncio.to_thread(Path(".artifacts").mkdir, exist_ok=True)
    await asyncio.to_thread(
        Path(".artifacts/live-exposure.json").write_text, result.model_dump_json(indent=2)
    )
    print(
        json.dumps(
            {
                "coverage": result.coverage.model_dump(),
                "permissions": len(result.permissions),
                "resolved": sum(p.current.allowance_raw is not None for p in result.permissions),
                "statuses": sorted({p.status for p in result.permissions}),
            }
        )
    )
    if not any(p.current.allowance_raw is not None for p in result.permissions):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
