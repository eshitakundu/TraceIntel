"""Run the pre-sign check on recent real Ethereum transactions and publish the verdict mix.

    PYTHONPATH=backend uv run python scripts/presign_scoreboard.py [--approvals 60] [--batches 40]

Scans back from the chain head for transactions that call an approval function (approve,
increaseAllowance, setApprovalForAll, Permit2 approve) or a batch that can carry one
(multicall, Universal Router execute, EIP-7702 execute), then runs the same check the MCP
server runs on each. These transactions were already mined, so each is checked against the
chain head after it, not the block before it. Writes evals/results/presign-live-<date>.json.
Read-only: it only reads public chain data.
"""

import argparse
import asyncio
import json
import logging
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from eth_utils.crypto import keccak

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.blockchain.chains import chains  # noqa: E402
from app.blockchain.rpc_client import RpcClient  # noqa: E402
from app.config import Settings  # noqa: E402
from app.presign.intents import TxInput, decode_transaction_intent  # noqa: E402
from app.presign.service import check  # noqa: E402

logging.getLogger("httpx").setLevel(logging.WARNING)


def selector(signature: str) -> str:
    return "0x" + keccak(text=signature).hex()[:8]


APPROVALS = {
    selector(s): s
    for s in (
        "approve(address,uint256)",
        "increaseAllowance(address,uint256)",
        "setApprovalForAll(address,bool)",
        "approve(address,address,uint160,uint48)",
    )
}
BATCHES = {
    selector(s): s
    for s in (
        "multicall(bytes[])",
        "multicall(uint256,bytes[])",
        "multicall(bytes32,bytes[])",
        "execute(bytes,bytes[],uint256)",
        "execute(bytes,bytes[])",
        "execute(bytes32,bytes)",
    )
}
MAX_BLOCKS = 400


async def collect(
    rpc: RpcClient, approvals: int, batches: int, to_block: int | None = None
) -> tuple[list[dict[str, Any]], int, int]:
    head = to_block or int(await rpc.call("eth_blockNumber", []), 16)
    picked: list[dict[str, Any]] = []
    counts = {"approval": 0, "batch": 0}
    caps = {"approval": approvals, "batch": batches}
    number = head
    while number > head - MAX_BLOCKS and (
        counts["approval"] < approvals or counts["batch"] < batches
    ):
        block = await rpc.call("eth_getBlockByNumber", [hex(number), True])
        for tx in block["transactions"]:
            data, to = (tx.get("input") or "0x").lower(), tx.get("to")
            head4 = data[:10]
            group = "approval" if head4 in APPROVALS else "batch" if head4 in BATCHES else None
            if not to or group is None or counts[group] >= caps[group]:
                continue
            counts[group] += 1
            picked.append(
                {
                    "hash": tx["hash"],
                    "block": number,
                    "group": group,
                    "function": APPROVALS.get(head4) or BATCHES[head4],
                    "tx": TxInput.model_validate({"from": tx["from"], "to": to, "data": data}),
                }
            )
        number -= 1
    return picked, number + 1, head


async def run_one(
    chain: Any, rpc: RpcClient, item: dict[str, Any], gate: asyncio.Semaphore
) -> dict[str, Any]:
    tx: TxInput = item["tx"]
    decoded = decode_transaction_intent(tx)
    async with gate:
        try:
            report = await check(chain, rpc, decoded, tx.model_dump(by_alias=True))
        except Exception as exc:  # a crash here is a finding, not a skip
            return {**_row(item), "verdict": "error", "error": type(exc).__name__}
    return {
        **_row(item),
        "decoded": decoded.status,
        "note": decoded.note,
        "partial": getattr(decoded, "partial", False),
        "kinds": [i.kind for i in decoded.intents],
        "spenders": sorted({i.spender for i in decoded.intents}),
        "verdict": report.verdict,
        "rules": [r.rule for r in report.reasons],
        "reasons": [r.text for r in report.reasons if r.severity != "allow"][:3],
        "gaps": len(report.coverage_gaps),
    }


def _row(item: dict[str, Any]) -> dict[str, Any]:
    return {k: item[k] for k in ("hash", "block", "group", "function")} | {
        "to": item["tx"].to.lower()
    }


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_group: dict[str, Counter[str]] = {}
    for r in rows:
        by_group.setdefault(r["group"], Counter())[r["verdict"]] += 1
    rule_hits = Counter(rule for r in rows for rule in set(r.get("rules", [])))
    return {
        "verdicts": dict(Counter(r["verdict"] for r in rows)),
        "by_group": {g: dict(c) for g, c in by_group.items()},
        "rules": dict(rule_hits.most_common()),
        "batches_fully_decoded": sum(
            1
            for r in rows
            if r["group"] == "batch" and r.get("decoded") != "unrecognised" and not r.get("partial")
        ),
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approvals", type=int, default=60)
    parser.add_argument("--batches", type=int, default=40)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--to-block", type=int, help="Scan back from this block (repeatable runs).")
    parser.add_argument("--out", help="Output file name inside evals/results/.")
    args = parser.parse_args()
    settings = Settings()
    chain = chains(settings)["ethereum"]
    async with httpx.AsyncClient(timeout=settings.rpc_timeout_seconds) as client:
        rpc = RpcClient(client, chain.rpc_url.get_secret_value())
        items, first, last = await collect(rpc, args.approvals, args.batches, args.to_block)
        gate = asyncio.Semaphore(args.concurrency)
        rows = await asyncio.gather(*(run_one(chain, rpc, item, gate) for item in items))
    out = {
        "date": datetime.now(UTC).date().isoformat(),
        "chain": "ethereum",
        "blocks": [first, last],
        "note": "Mined transactions, each checked against the chain head after it was mined.",
        "summary": summarise(rows),
        "cases": rows,
    }
    name = args.out or f"presign-live-{out['date']}.json"
    path = Path(__file__).resolve().parents[1] / "evals" / "results" / name
    path.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=1))
    print(f"{len(rows)} transactions from blocks {first}-{last} -> {path.name}")


if __name__ == "__main__":
    asyncio.run(main())
