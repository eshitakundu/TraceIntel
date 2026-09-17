import asyncio
import json
from typing import Any

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
    try:
        code = await rpc.call("eth_getCode", [address, block])
        if not isinstance(code, str) or not code.startswith("0x"):
            raise RpcError("Invalid bytecode response")
    except RpcError:
        return (
            Contract(address=address, kind="unknown"),
            (),
            (
                Coverage(
                    area=f"contract:{address}",
                    status="unavailable",
                    reason="Historical bytecode lookup failed.",
                ),
            ),
        )
    evidence.append(
        Evidence(
            id=eid,
            source="eth_getCode",
            description="Bytecode at transaction block",
            data_json=json.dumps({"address": address, "block": block, "code": code}),
        )
    )
    if code == "0x":
        return (
            Contract(address=address, kind="no_code", evidence_ids=(eid,)),
            tuple(evidence),
            (
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
                description="EIP-1967 slots at transaction block end",
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
                reason="Historical proxy lookup unavailable.",
            )
        )
    verification: Any = "unavailable"
    name = abi_json = None
    if explorer_key:
        try:
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
        except (httpx.HTTPError, ValueError, KeyError, IndexError):
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
            evidence_ids=tuple(item.id for item in evidence),
        ),
        tuple(evidence),
        tuple(coverage),
    )
