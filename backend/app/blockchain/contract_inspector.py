import asyncio
import json
import weakref
from typing import Any, Literal

import httpx

from app.blockchain.chains import Chain
from app.blockchain.proxy_detector import (
    BEACON_SLOT,
    IMPLEMENTATION_SLOT,
    resolve_beacon,
    storage_address,
)
from app.blockchain.rpc_client import RpcClient, RpcError
from app.models.blockchain import Contract, Coverage, Evidence

# EIP-7702: an EOA's code is 0xef0100 followed by the 20-byte delegate address.
DELEGATION_PREFIX = "0xef0100"
# Etherscan's free tier allows a handful of calls per second; one gate per event loop.
_explorer_gates: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = (
    weakref.WeakKeyDictionary()
)


def _explorer_slots() -> asyncio.Semaphore:
    return _explorer_gates.setdefault(asyncio.get_running_loop(), asyncio.Semaphore(3))


async def bytecode(rpc: RpcClient, address: str, block: str) -> str:
    code = await rpc.call("eth_getCode", [address, block])
    if not isinstance(code, str) or not code.startswith("0x"):
        raise RpcError("Invalid bytecode response")
    return code


def delegate_of(code: str) -> str | None:
    """Return the EIP-7702 delegate when code is a delegation designator."""
    if code.startswith(DELEGATION_PREFIX) and len(code) == len(DELEGATION_PREFIX) + 40:
        return "0x" + code[len(DELEGATION_PREFIX) :]
    return None


async def inspect_contract(
    rpc: RpcClient,
    client: httpx.AsyncClient,
    chain: Chain,
    address: str,
    block: str,
    prefix: str,
    explorer_key: str = "",
) -> tuple[Contract, tuple[Evidence, ...], tuple[Coverage, ...]]:
    evidence: list[Evidence] = []
    coverage: list[Coverage] = []
    eid = f"{prefix}:contract:{address}"
    state: Literal["historical", "current"] = "historical"
    try:
        code = await bytecode(rpc, address, block)
    except RpcError:
        # Non-archive providers prune old state; labelled current state is the honest fallback.
        try:
            code = await bytecode(rpc, address, "latest")
            block, state = "latest", "current"
        except RpcError:
            return (
                Contract(address=address, kind="unknown"),
                (),
                (
                    Coverage(
                        area=f"contract:{address}",
                        status="unavailable",
                        reason="Bytecode lookup failed at the transaction block and latest block.",
                    ),
                ),
            )
        coverage.append(
            Coverage(
                area=f"state:{address}",
                status="partial",
                reason="Provider pruned transaction-block state; current bytecode and slots used.",
            )
        )
    evidence.append(
        Evidence(
            id=eid,
            source="eth_getCode",
            description="Bytecode at transaction block"
            if state == "historical"
            else "Bytecode at latest block (transaction-block state unavailable)",
            data_json=json.dumps({"address": address, "block": block, "code": code}),
        )
    )
    delegate = delegate_of(code)
    if delegate:
        return (
            Contract(
                address=address,
                kind="delegated_eoa",
                implementation=delegate,
                state=state,
                evidence_ids=(eid,),
            ),
            tuple(evidence),
            (
                *coverage,
                Coverage(
                    area=f"contract:{address}",
                    status="available",
                    reason="EIP-7702 delegation: an externally owned account using delegate code.",
                ),
            ),
        )
    if code == "0x":
        return (
            Contract(address=address, kind="no_code", state=state, evidence_ids=(eid,)),
            tuple(evidence),
            (
                *coverage,
                Coverage(
                    area=f"contract:{address}",
                    status="available",
                    reason="No bytecode at block end; this alone does not prove account type.",
                ),
            ),
        )
    proxy: Any = "unknown"
    implementation = None
    try:
        impl_word, beacon_word = await asyncio.gather(
            rpc.call("eth_getStorageAt", [address, IMPLEMENTATION_SLOT, block]),
            rpc.call("eth_getStorageAt", [address, BEACON_SLOT, block]),
        )
        implementation, beacon = storage_address(impl_word), storage_address(beacon_word)
        proxy = "eip1967" if implementation else "not_detected"
        if not implementation and beacon:
            proxy = "beacon"
            implementation = await resolve_beacon(rpc, beacon, block)
        evidence.append(
            Evidence(
                id=eid + ":proxy",
                source="eth_getStorageAt / eth_call",
                description="EIP-1967 slots at transaction block end"
                if state == "historical"
                else "EIP-1967 slots at latest block",
                data_json=json.dumps(
                    {
                        "implementation_slot": impl_word,
                        "beacon_slot": beacon_word,
                        "implementation": implementation,
                        "block": block,
                    }
                ),
            )
        )
        coverage.append(
            Coverage(
                area=f"proxy:{address}",
                status="partial",
                reason="EIP-1967 only. Custom proxies not excluded. Block-end state.",
            )
        )
    except (RpcError, ValueError):
        coverage.append(
            Coverage(
                area=f"proxy:{address}",
                status="unavailable",
                reason="Proxy slot lookup unavailable.",
            )
        )
    verification: Any = "unavailable"
    name = abi_json = None
    if explorer_key:
        try:
            async with _explorer_slots():
                response = await client.get(
                    "https://api.etherscan.io/v2/api",
                    params={
                        "chainid": chain.chain_id,
                        "module": "contract",
                        "action": "getsourcecode",
                        "address": address,
                        "apikey": explorer_key,
                    },
                )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") == "1" and isinstance(payload.get("result"), list):
                source = payload["result"][0]
                verification = "verified" if source.get("SourceCode") else "unverified"
                name = source.get("ContractName") or None
                if verification == "verified":
                    abi_json = json.dumps(json.loads(source["ABI"]))
                evidence.append(
                    Evidence(
                        id=eid + ":explorer",
                        source="Etherscan v2",
                        description="Current explorer verification; not historical attestation",
                        data_json=json.dumps(
                            {
                                "verification": verification,
                                "name": name,
                                "address": address,
                                "abi": abi_json,
                            }
                        ),
                    )
                )
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError):
            verification = "unavailable"
    coverage.append(
        Coverage(
            area=f"explorer:{address}",
            status="available" if verification != "unavailable" else "unavailable",
            reason="Current explorer metadata."
            if verification != "unavailable"
            else "Explorer key missing, chain unsupported, or provider lookup failed.",
        )
    )
    return (
        Contract(
            address=address,
            kind="contract",
            proxy=proxy,
            implementation=implementation,
            verification=verification,
            name=name,
            abi_json=abi_json,
            state=state,
            evidence_ids=tuple(item.id for item in evidence),
        ),
        tuple(evidence),
        tuple(coverage),
    )
