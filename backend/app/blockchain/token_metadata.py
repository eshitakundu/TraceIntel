import asyncio
import json

from eth_abi.abi import decode
from eth_abi.exceptions import DecodingError

from app.blockchain.rpc_client import RpcClient, RpcError
from app.models.blockchain import Coverage, DecodedEvidence, Evidence


async def enrich_tokens(decoded: DecodedEvidence, rpc: RpcClient, prefix: str) -> DecodedEvidence:
    tokens = list(
        dict.fromkeys(
            [m.token for m in decoded.movements if m.standard == "ERC20"]
            + [a.token for a in decoded.approvals if a.standard == "ERC20"]
        )
    )
    block = hex(decoded.transaction.block_number)

    async def metadata(token: str) -> tuple[str, str | None, int | None, Evidence | None]:
        try:
            decimals_raw, symbol_raw = await asyncio.gather(
                rpc.call("eth_call", [{"to": token, "data": "0x313ce567"}, block]),
                rpc.call("eth_call", [{"to": token, "data": "0x95d89b41"}, block]),
            )
            decimals = int(decimals_raw, 16)
            if len(decimals_raw) != 66 or not 0 <= decimals <= 255:
                raise ValueError("Invalid token decimals")
            data = bytes.fromhex(symbol_raw[2:])
            symbol = (
                data.rstrip(b"\0").decode() if len(data) == 32 else str(decode(["string"], data)[0])
            )
            if len(symbol) > 64 or not symbol.isprintable():
                raise ValueError("Invalid token symbol")
            evidence = Evidence(
                id=f"{prefix}:token:{token}",
                source="eth_call decimals/symbol",
                description="Contract-reported token metadata at block end",
                data_json=json.dumps(
                    {"token": token, "decimals": decimals, "symbol": symbol, "block": block}
                ),
            )
            return token, symbol, decimals, evidence
        except (RpcError, ValueError, DecodingError, UnicodeError):
            return token, None, None, None

    results = await asyncio.gather(*(metadata(token) for token in tokens[:12]))
    found = {token: (symbol, decimals, evidence) for token, symbol, decimals, evidence in results}
    movements = []
    for movement in decoded.movements:
        value = found.get(movement.token)
        if value and value[2]:
            movement = movement.model_copy(
                update={
                    "symbol": value[0],
                    "decimals": value[1],
                    "evidence_ids": movement.evidence_ids + (value[2].id,),
                }
            )
        movements.append(movement)
    evidence = tuple(value[2] for value in found.values() if value[2] is not None)
    coverage = Coverage(
        area="token_metadata",
        status="not_applicable"
        if not tokens
        else "available"
        if len(evidence) == len(tokens)
        else "partial",
        reason=f"Metadata retrieved for {len(evidence)}/{len(tokens)} fungible token contracts. "
        "Symbols are contract-reported labels, not identity attestations.",
    )
    return decoded.model_copy(
        update={
            "movements": tuple(movements),
            "evidence": decoded.evidence + evidence,
            "coverage": tuple(c for c in decoded.coverage if c.area != "token_metadata")
            + (coverage,),
        }
    )
