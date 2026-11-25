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
from pathlib import Path
from typing import Any

from app.agents.catalog import short
from app.blockchain.contract_inspector import bytecode, delegate_of
from app.blockchain.proxy_detector import BEACON_SLOT, IMPLEMENTATION_SLOT, storage_address
from app.blockchain.rpc_client import RpcClient, RpcError
from app.models.blockchain import Contract, Coverage, Evidence
from app.models.exposure import PersistentExposure
from app.models.interpretation import CitedClaim, ToolName

# keccak256("eip1967.proxy.admin") - 1
ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
OWNER_SELECTOR = "0x8da5cb5b"
ADMIN_SELECTOR = "0xf851a440"  # admin()
SAFE_THRESHOLD_SELECTOR = "0xe75235b8"  # getThreshold()
SAFE_OWNERS_SELECTOR = "0xa0e67e2b"  # getOwners()
MIN_DELAY_SELECTOR = "0xf27a0c92"  # getMinDelay(), OpenZeppelin TimelockController
DELAY_SELECTOR = "0x6a42b8f8"  # delay(), Compound-style Timelock
# An address that is never a proxy admin, used to check that admin() is caller-gated.
PROBE_CALLER = "0x0000000000000000000000000000000000000001"
MAX_CONTROL_HOPS = 3
MAX_SAFE_OWNERS = 50
MAX_TIMELOCK_DELAY = 10 * 365 * 86400

# Published addresses of widely used spender contracts, each with the official page it was
# copied from (spender_registry.json). A match identifies a contract; it is never treated
# as a safety verdict.
REGISTRY_PATH = Path(__file__).with_name("spender_registry.json")


def load_registry(path: Path = REGISTRY_PATH) -> dict[int, list[dict[str, Any]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {int(chain): entries for chain, entries in raw.items() if not chain.startswith("_")}


REGISTRY = load_registry()
KNOWN_SPENDERS: dict[int, dict[str, str]] = {
    chain: {entry["address"]: entry["name"] for entry in entries}
    for chain, entries in REGISTRY.items()
}
SPENDER_SOURCES: dict[int, dict[str, str]] = {
    chain: {entry["address"]: entry["source"] for entry in entries}
    for chain, entries in REGISTRY.items()
}
# Recognised spenders that legitimately take blanket NFT approvals (setApprovalForAll).
NFT_MARKETPLACES = frozenset(
    entry["address"]
    for entries in REGISTRY.values()
    for entry in entries
    if entry.get("nft_marketplace")
)


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
    # Compare the spender with its state at the approval block. Off for pre-sign checks,
    # where no approval exists yet.
    compare_history: bool = True


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
    beacon = None
    if code != "0x" and not delegate:
        implementation = storage_address(
            await ctx.rpc.call("eth_getStorageAt", [spender, IMPLEMENTATION_SLOT, ctx.tag])
        )
        if not implementation:
            beacon = storage_address(
                await ctx.rpc.call("eth_getStorageAt", [spender, BEACON_SLOT, ctx.tag])
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
                        "beacon": beacon,
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
    elif beacon:
        result.facts["proxy"] = True
        text = (
            f"Spender {name} is an upgradeable EIP-1967 beacon proxy; its logic comes from "
            f"beacon {short(beacon)} and can be replaced by the beacon's owner."
        )
    else:
        text = f"Spender {name} is a contract with no EIP-1967 upgrade slot set."
    result.claims.append(CitedClaim(id=f"{pid}:spender", text=text, evidence_ids=(eid,)))
    if not ctx.compare_history:
        return result

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


async def _try_call(ctx: ToolContext, to: str, data: str, sender: str | None = None) -> str | None:
    """eth_call that treats a revert or malformed reply as "no answer"."""
    tx = {"to": to, "data": data} | ({"from": sender} if sender else {})
    try:
        result = await ctx.rpc.call("eth_call", [tx, ctx.tag])
    except (RpcError, ValueError):
        return None
    return result if isinstance(result, str) and result.startswith("0x") else None


def _word_address(word: str | None) -> str | None:
    if word is None or len(word) != 66:
        return None
    try:
        return storage_address(word)
    except ValueError:
        return None


def _word_uint(word: str | None) -> int | None:
    if word is None or len(word) != 66:
        return None
    try:
        return int(word, 16)
    except ValueError:
        return None


def _address_array_length(word: str | None) -> int | None:
    """Length of an ABI-encoded address[] return value, if it is well formed."""
    if word is None or len(word) < 130 or (len(word) - 2) % 64:
        return None
    try:
        offset, length = int(word[2:66], 16), int(word[66:130], 16)
    except ValueError:
        return None
    if offset != 32 or len(word) != 130 + 64 * length:
        return None
    return length


def embedded_addresses(code: str, limit: int = 8) -> list[str]:
    """20-byte constants pushed by the bytecode (PUSH20, or PUSH32 with 12 zero bytes)."""
    try:
        raw = bytes.fromhex(code[2:]) if code.startswith("0x") else b""
    except ValueError:
        return []
    found: list[str] = []
    i = 0
    while i < len(raw) and len(found) < limit:
        op = raw[i]
        size = op - 0x5F if 0x60 <= op <= 0x7F else 0
        value = raw[i + 1 : i + 1 + size]
        if len(value) == size and (size == 20 or (size == 32 and value[:12] == bytes(12))):
            candidate = "0x" + value[-20:].hex()
            if int(candidate, 16) > 0xFFFF and candidate not in found:
                found.append(candidate)
        i += 1 + size
    return found


async def immutable_admin(ctx: ToolContext, proxy: str, code: str) -> str | None:
    """Find an admin fixed in the proxy's code (Aave-style immutable admin proxies).

    A candidate counts only if admin() answers with that address when called from it, and
    not when called from anyone else: that is the caller-gated admin() of a transparent
    proxy, so the answer can't come from the implementation.
    """
    for candidate in embedded_addresses(code):
        if _word_address(await _try_call(ctx, proxy, ADMIN_SELECTOR, candidate)) != candidate:
            continue
        if _word_address(await _try_call(ctx, proxy, ADMIN_SELECTOR, PROBE_CALLER)) == candidate:
            return None
        return candidate
    return None


def _duration(seconds: int) -> str:
    if seconds >= 86400:
        days = round(seconds / 86400, 1)
        return f"{days:g} day" + ("" if days == 1 else "s")
    hours = round(seconds / 3600, 1)
    return f"{hours:g} hour" + ("" if hours == 1 else "s")


async def classify_controller(
    ctx: ToolContext, address: str, chain: list[dict[str, Any]]
) -> tuple[str, str]:
    """Walk an upgrade authority up to MAX_CONTROL_HOPS: key, Safe multisig, timelock, owner()."""
    code = await bytecode(ctx.rpc, address, ctx.tag)
    hop: dict[str, Any] = {"address": address, "code_bytes": (len(code) - 2) // 2}
    chain.append(hop)
    if code == "0x" or delegate_of(code):
        hop["type"] = "key"
        return "single_key", f"{short(address)}, a single externally owned key"
    threshold = _word_uint(await _try_call(ctx, address, SAFE_THRESHOLD_SELECTOR))
    if threshold and threshold <= MAX_SAFE_OWNERS:
        owners = _address_array_length(await _try_call(ctx, address, SAFE_OWNERS_SELECTOR))
        if owners and threshold <= owners <= MAX_SAFE_OWNERS:
            hop.update(type="multisig", threshold=threshold, owners=owners)
            if threshold == 1:
                return "single_key", (
                    f"{short(address)}, a 1-of-{owners} multisig: any one of its keys can act alone"
                )
            return "contract", f"{short(address)}, a {threshold}-of-{owners} multisig"
    for selector in (MIN_DELAY_SELECTOR, DELAY_SELECTOR):
        delay = _word_uint(await _try_call(ctx, address, selector))
        if delay and delay <= MAX_TIMELOCK_DELAY:
            hop.update(type="timelock", delay_seconds=delay)
            return "contract", (
                f"{short(address)}, a timelock that holds every change for {_duration(delay)}"
            )
    owner = _word_address(await _try_call(ctx, address, OWNER_SELECTOR))
    hop["owner"] = owner
    if owner and owner != address and len(chain) < MAX_CONTROL_HOPS:
        control, described = await classify_controller(ctx, owner, chain)
        return control, f"contract {short(address)}, owned by {described}"
    hop["type"] = "contract"
    return "contract", f"contract {short(address)}"


VIA = {"eip1967_beacon": "its beacon, ", "immutable_admin": "an admin fixed in its code, "}


async def upgrade_control(ctx: ToolContext, pid: str) -> ToolResult:
    spender = ctx.targets[pid].historical.spender
    name = short(spender)
    admin = storage_address(await ctx.rpc.call("eth_getStorageAt", [spender, ADMIN_SLOT, ctx.tag]))
    found_by = "eip1967_admin_slot" if admin else None
    if not admin:
        beacon = storage_address(
            await ctx.rpc.call("eth_getStorageAt", [spender, BEACON_SLOT, ctx.tag])
        )
        if beacon:
            admin, found_by = beacon, "eip1967_beacon"
    if not admin:
        admin = await immutable_admin(ctx, spender, await bytecode(ctx.rpc, spender, ctx.tag))
        found_by = "immutable_admin" if admin else None
    eid = f"{ctx.prefix}:agent:{pid}:control"
    chain: list[dict[str, Any]] = []
    data: dict[str, Any] = {
        "spender": spender,
        "block": ctx.tag,
        "admin": admin,
        "found_by": found_by,
        "chain": chain,
    }
    if not admin:
        control = "undetermined"
        text = (
            f"Spender {name} records no EIP-1967 admin or beacon and no admin in its code; if "
            "it is upgradeable, the authority sits inside its implementation (UUPS-style) and "
            "was not determined."
        )
    else:
        control, described = await classify_controller(ctx, admin, chain)
        via = VIA.get(found_by or "", "")
        text = f"Upgrades to spender {name} are controlled by {via}{described}."
        if control == "single_key":
            text += " One private key can replace the spender's logic."
    return ToolResult(
        claims=[CitedClaim(id=f"{pid}:control", text=text, evidence_ids=(eid,))],
        evidence=[
            Evidence(
                id=eid,
                source="eth_getStorageAt / eth_getCode / eth_call",
                description="Upgrade authority at the checked block: EIP-1967 admin, beacon "
                "or code-fixed admin, then multisig threshold, timelock delay and owner()",
                data_json=json.dumps(data),
            )
        ],
        facts={"control": control},
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
                    {
                        "spender": spender,
                        "chain_id": ctx.chain_id,
                        "match": match,
                        "source": SPENDER_SOURCES.get(ctx.chain_id, {}).get(spender),
                    }
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
