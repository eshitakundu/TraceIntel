"""Read the owner and target state a pre-sign verdict needs, at one pinned block.

Every read goes through the shared read-only RPC client and its method allowlist. A
failed or non-standard read is recorded as an error, never filled with a default.
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from eth_abi.exceptions import DecodingError
from eth_utils.crypto import keccak

from app.blockchain.exposure_analyzer import _label, _uint
from app.blockchain.rpc_client import RpcClient, RpcError
from app.models.blockchain import Evidence
from app.presign.intents import PERMIT2, Intent


def selector(signature: str) -> str:
    return "0x" + keccak(text=signature).hex()[:8]


BALANCE_OF = selector("balanceOf(address)")
ALLOWANCE = selector("allowance(address,address)")
PERMIT2_ALLOWANCE = selector("allowance(address,address,address)")
IS_APPROVED_FOR_ALL = selector("isApprovedForAll(address,address)")
SYMBOL = selector("symbol()")
DECIMALS = selector("decimals()")
# Reads whose failure leaves the verdict unverifiable. Labels are cosmetic.
REQUIRED = {
    "target_code",
    "token_code",
    "balance",
    "allowance",
    "permit2_allowance",
    "token_to_permit2",
    "operator",
}


def arg(address: str) -> str:
    return address[2:].lower().zfill(64)


@dataclass
class State:
    """What the chain says now about one intent's owner, token and spender."""

    target_has_code: bool | None = None
    balance: int | None = None
    # ERC-20 allowance to the spender, or the Permit2 allowance amount.
    allowance: int | None = None
    permit2_expiration: int | None = None
    # How much Permit2 itself may move from the owner (the ERC-20 allowance to Permit2).
    token_to_permit2: int | None = None
    operator_approved: bool | None = None
    symbol: str | None = None
    decimals: int | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def unverified(self) -> list[str]:
        return [e for e in self.errors if e.split(" ")[0].rstrip(":") in REQUIRED]


async def read_state(rpc: RpcClient, intent: Intent, tag: Any, eid: str) -> tuple[State, Evidence]:
    owner, spender, token = intent.owner, intent.spender, intent.token
    queries: dict[str, tuple[str, list[Any]]] = {
        "target_code": ("eth_getCode", [intent.target, tag]),
    }

    def call(to: str, data: str) -> tuple[str, list[Any]]:
        return ("eth_call", [{"to": to, "data": data}, tag])

    if intent.kind == "nft_operator":
        queries["operator"] = call(token, IS_APPROVED_FOR_ALL + arg(owner) + arg(spender))
    else:
        queries |= {
            "balance": call(token, BALANCE_OF + arg(owner)),
            "symbol": call(token, SYMBOL),
            "decimals": call(token, DECIMALS),
        }
        if intent.target == PERMIT2:
            queries["permit2_allowance"] = call(
                PERMIT2, PERMIT2_ALLOWANCE + arg(owner) + arg(token) + arg(spender)
            )
            queries["token_to_permit2"] = call(token, ALLOWANCE + arg(owner) + arg(PERMIT2))
            queries["token_code"] = ("eth_getCode", [token, tag])
        else:
            queries["allowance"] = call(token, ALLOWANCE + arg(owner) + arg(spender))

    state = State()
    results: dict[str, Any] = {}

    async def read(name: str, method: str, params: list[Any]) -> None:
        try:
            raw = await rpc.call(method, params)
            results[name] = raw
            if name in ("target_code", "token_code"):
                if not isinstance(raw, str) or not raw.startswith("0x"):
                    raise ValueError("invalid bytecode")
                has_code = bool(bytes.fromhex(raw[2:]))
                if name == "target_code":
                    state.target_has_code = has_code
                elif not has_code:
                    state.errors.append("token_code: the token address has no contract code")
            elif name == "permit2_allowance":
                if not isinstance(raw, str) or len(raw) != 2 + 64 * 3:
                    raise ValueError("non-standard Permit2 response")
                state.allowance = int(raw[2:66], 16)
                state.permit2_expiration = int(raw[66:130], 16)
            elif name == "operator":
                value = int(_uint(raw))
                if value > 1:
                    raise ValueError("non-boolean response")
                state.operator_approved = bool(value)
            elif name == "symbol":
                state.symbol = _label(raw)
            else:
                value = int(_uint(raw))
                if name == "decimals":
                    if value > 255:
                        raise ValueError("invalid decimals")
                    state.decimals = value
                elif name == "balance":
                    state.balance = value
                elif name == "allowance":
                    state.allowance = value
                else:
                    state.token_to_permit2 = value
        except (RpcError, ValueError, TypeError, AttributeError, DecodingError, UnicodeError):
            state.errors.append(f"{name} unavailable or non-standard")

    await asyncio.gather(*(read(n, m, p) for n, (m, p) in queries.items()))
    state.errors.sort()
    evidence = Evidence(
        id=eid,
        source="eth_getCode / eth_call balanceOf, allowance, isApprovedForAll",
        description="Owner, token and target state at the pinned block",
        data_json=json.dumps(
            {
                "target": intent.target,
                "token": token,
                "owner": owner,
                "spender": spender,
                "block": tag,
                "queries": queries,
                "results": results,
                "errors": state.errors,
            }
        ),
    )
    return state, evidence
