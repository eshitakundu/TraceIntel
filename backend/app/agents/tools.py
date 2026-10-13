"""Read-only investigation tools.

Each tool takes a permission ID that already exists in the evidence catalog (never a
free-form address), performs bounded read-only RPC calls, and returns claims written by
code with fresh evidence. A model can choose which tools run; it cannot change what they
observe or how the observation is phrased.
"""

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.agents.catalog import short
from app.blockchain.contract_inspector import bytecode, delegate_of
from app.blockchain.proxy_detector import IMPLEMENTATION_SLOT, storage_address
from app.blockchain.rpc_client import RpcClient, RpcError
from app.models.blockchain import Contract, Coverage, Evidence
from app.models.exposure import PersistentExposure
from app.models.interpretation import CitedClaim, ToolName

# keccak256("eip1967.proxy.admin") - 1
ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
OWNER_SELECTOR = "0x8da5cb5b"

# Published addresses of widely used spender contracts. A match identifies a contract;
# it is never treated as a safety verdict.
KNOWN_SPENDERS: dict[int, dict[str, str]] = {
    1: {
        "0x000000000022d473030f116ddee9f6b43ac78ba3": "Uniswap Permit2",
        "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2 Router 02",
        "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 SwapRouter",
        "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 SwapRouter02",
        "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch Aggregation Router v5",
        "0xdef1c0ded9bec7f1a1670819833240f027b25eff": "0x Exchange Proxy",
        "0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb": "Morpho Blue",
    }
}


@dataclass
class ToolContext:
    rpc: RpcClient
    chain_id: int
    chain_name: str
    prefix: str
    targets: dict[str, PersistentExposure]
    contracts: dict[str, Contract]
    evidence: dict[str, Evidence]
    # Block tag for "now": pinned to the exposure snapshot when one exists.
    tag: Any = "latest"


@dataclass
class ToolResult:
    claims: list[CitedClaim] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    coverage: list[Coverage] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)


def fingerprint(code: str) -> str:
    return hashlib.sha256(bytes.fromhex(code[2:])).hexdigest()[:16]


def _historical_record(ctx: ToolContext, spender: str) -> tuple[str | None, str | None] | None:
    """Spender code and implementation recorded at the approval block, if that state was read."""
    contract = ctx.contracts.get(spender)
    if not contract or contract.state != "historical" or not contract.evidence_ids:
        return None
    record = ctx.evidence.get(contract.evidence_ids[0])
    if record is None:
        return None
    code = json.loads(record.data_json).get("code")
    return (code if isinstance(code, str) else None), contract.implementation


async def spender_profile(ctx: ToolContext, pid: str) -> ToolResult:
    spender = ctx.targets[pid].historical.spender
    code = await bytecode(ctx.rpc, spender, ctx.tag)
    delegate = delegate_of(code)
    implementation = None
    if code != "0x" and not delegate:
        implementation = storage_address(
            await ctx.rpc.call("eth_getStorageAt", [spender, IMPLEMENTATION_SLOT, ctx.tag])
        )
    eid = f"{ctx.prefix}:agent:{pid}:spender"
    result = ToolResult(
        evidence=[
            Evidence(
                id=eid,
                source="eth_getCode / eth_getStorageAt",
                description="Spender code and EIP-1967 implementation at the checked block",
                data_json=json.dumps(
                    {
                        "spender": spender,
                        "block": ctx.tag,
                        "code_bytes": (len(code) - 2) // 2,
                        "code_fingerprint": fingerprint(code) if code != "0x" else None,
                        "delegate": delegate,
                        "implementation": implementation,
                    }
                ),
            )
        ],
        facts={"kind": "eoa" if code == "0x" else "delegated" if delegate else "contract"},
    )
    name = short(spender)
    if code == "0x":
        text = (
            f"Spender {name} has no contract code: it is an externally owned account, so "
            "whoever holds its private key can move the approved tokens."
        )
    elif delegate:
        text = (
            f"Spender {name} is an EIP-7702 delegated account running code from "
            f"{short(delegate)}; its key holder can change that code at any time."
        )
    elif implementation:
        result.facts["proxy"] = True
        text = (
            f"Spender {name} is an upgradeable EIP-1967 proxy; its logic currently lives at "
            f"{short(implementation)} and can be replaced by its upgrade authority."
        )
    else:
        text = f"Spender {name} is a contract with no EIP-1967 upgrade slot set."
    result.claims.append(CitedClaim(id=f"{pid}:spender", text=text, evidence_ids=(eid,)))

    record = _historical_record(ctx, spender)
    if record is None or record[0] is None:
        result.claims.append(
            CitedClaim(
                id=f"{pid}:drift",
                text=f"Whether spender {name} changed since the approval cannot be verified: "
                "the RPC provider no longer serves state from the approval block.",
                evidence_ids=(),
            )
        )
        result.coverage.append(
            Coverage(
                area=f"drift:{spender}",
                status="unavailable",
                reason="Approval-block state unavailable; use an archive-capable RPC.",
            )
        )
        return result
    code_then, implementation_then = record
    then_id = ctx.contracts[spender].evidence_ids
    if implementation_then != implementation and (implementation_then or implementation):
        result.facts["drift"] = "upgraded"
        text = (
            f"Spender {name} was upgraded after the approval: its implementation changed from "
            f"{short(implementation_then or 'none')} to {short(implementation or 'none')}."
        )
    elif code_then != code:
        result.facts["drift"] = "code_changed"
        text = f"Spender {name}'s bytecode changed after the approval block."
    else:
        result.facts["drift"] = "unchanged"
        text = f"Spender {name} is unchanged since the approval block" + (
            ": same bytecode and same implementation." if implementation else ": same bytecode."
        )
    result.claims.append(CitedClaim(id=f"{pid}:drift", text=text, evidence_ids=(*then_id[:2], eid)))
    return result


async def upgrade_control(ctx: ToolContext, pid: str) -> ToolResult:
    spender = ctx.targets[pid].historical.spender
    name = short(spender)
    admin = storage_address(await ctx.rpc.call("eth_getStorageAt", [spender, ADMIN_SLOT, ctx.tag]))
    eid = f"{ctx.prefix}:agent:{pid}:control"
    data: dict[str, Any] = {"spender": spender, "block": ctx.tag, "admin": admin}
    facts: dict[str, Any] = {}
    if not admin:
        facts["control"] = "undetermined"
        text = (
            f"Spender {name} records no EIP-1967 admin; if it is upgradeable, the authority sits "
            "inside its implementation (UUPS-style) and was not determined."
        )
    else:
        admin_code = await bytecode(ctx.rpc, admin, ctx.tag)
        data["admin_code_bytes"] = (len(admin_code) - 2) // 2
        if admin_code == "0x" or delegate_of(admin_code):
            facts["control"] = "single_key"
            text = (
                f"Upgrades to spender {name} are controlled by {short(admin)}, a single "
                "externally owned key: one private key can replace the spender's logic."
            )
        else:
            owner = None
            try:
                word = await ctx.rpc.call(
                    "eth_call", [{"to": admin, "data": OWNER_SELECTOR}, ctx.tag]
                )
                owner = storage_address(word) if isinstance(word, str) and len(word) == 66 else None
            except (RpcError, ValueError):
                owner = None
            data["admin_owner"] = owner
            if owner:
                owner_code = await bytecode(ctx.rpc, owner, ctx.tag)
                single = owner_code == "0x" or bool(delegate_of(owner_code))
                facts["control"] = "single_key" if single else "contract"
                text = (
                    f"Upgrades to spender {name} go through contract {short(admin)}, owned by "
                    + (
                        f"{short(owner)}, a single externally owned key."
                        if single
                        else f"contract {short(owner)} (for example a multisig or timelock)."
                    )
                )
            else:
                facts["control"] = "contract"
                text = (
                    f"Upgrades to spender {name} are controlled by contract {short(admin)} "
                    "(for example a multisig, timelock or proxy admin)."
                )
    return ToolResult(
        claims=[CitedClaim(id=f"{pid}:control", text=text, evidence_ids=(eid,))],
        evidence=[
            Evidence(
                id=eid,
                source="eth_getStorageAt / eth_getCode / eth_call owner()",
                description="EIP-1967 upgrade authority at the checked block",
                data_json=json.dumps(data),
            )
        ],
        facts=facts,
    )


async def known_spender(ctx: ToolContext, pid: str) -> ToolResult:
    spender = ctx.targets[pid].historical.spender
    match = KNOWN_SPENDERS.get(ctx.chain_id, {}).get(spender)
    eid = f"{ctx.prefix}:agent:{pid}:known"
    text = (
        f"Spender {short(spender)} is the published {match} contract on {ctx.chain_name}. "
        "That identifies who was approved; it is not a safety guarantee."
        if match
        else f"Spender {short(spender)} is not one of the widely used protocol contracts "
        "TraceIntel recognises; that alone says nothing about its safety."
    )
    return ToolResult(
        claims=[CitedClaim(id=f"{pid}:known", text=text, evidence_ids=(eid,))],
        evidence=[
            Evidence(
                id=eid,
                source="TraceIntel spender registry",
                description="Static list of published protocol contract addresses",
                data_json=json.dumps(
                    {"spender": spender, "chain_id": ctx.chain_id, "match": match}
                ),
            )
        ],
        facts={"known": match},
    )


TOOLS: dict[ToolName, Callable[[ToolContext, str], Awaitable[ToolResult]]] = {
    "spender_profile": spender_profile,
    "upgrade_control": upgrade_control,
    "known_spender": known_spender,
}
