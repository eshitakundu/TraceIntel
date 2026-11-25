"""Decode what an unsigned transaction or an EIP-712 signature would grant.

Nothing here touches the network. A transaction's calldata is decoded with the shared
decoder against a fixed ABI of approval functions; typed data is matched against the
permit formats that move spending power without a transaction (EIP-2612 and Permit2).
Anything that is not recognised is reported as such, never guessed.
"""

import json
import re
from typing import Any, Literal

from eth_abi.abi import decode as abi_decode
from eth_abi.exceptions import DecodingError
from eth_utils.crypto import keccak
from pydantic import Field

from app.agents.tools import REGISTRY
from app.blockchain.calldata import decode_calldata
from app.blockchain.event_decoder import is_unlimited
from app.blockchain.signature_resolver import resolve
from app.models.base import FrozenModel
from app.models.blockchain import Address
from app.models.exposure import Quantity

# Uniswap's Permit2 is deployed at the same address on every chain it supports.
PERMIT2 = "0x000000000022d473030f116ddee9f6b43ac78ba3"
MAX_INTENTS = 8
ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
HEX = re.compile(r"^0x([0-9a-fA-F]{2})*$")

IntentKind = Literal[
    "erc20_approve",
    "erc20_increase",
    "erc20_decrease",
    "erc20_permit",
    "permit2_approve",
    "permit2_permit",
    "permit2_transfer",
    "nft_operator",
]
Mode = Literal["set", "increase", "decrease", "one_time", "operator"]


def _fn(name: str, *inputs: tuple[str, str]) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "inputs": [{"name": n, "type": t} for n, t in inputs],
    }


# The approval surface a transaction can call. Passed to the shared calldata decoder.
APPROVAL_ABI = json.dumps(
    [
        _fn("approve", ("spender", "address"), ("amount", "uint256")),
        _fn("increaseAllowance", ("spender", "address"), ("added", "uint256")),
        _fn("decreaseAllowance", ("spender", "address"), ("subtracted", "uint256")),
        _fn("setApprovalForAll", ("operator", "address"), ("approved", "bool")),
        _fn(
            "approve",
            ("token", "address"),
            ("spender", "address"),
            ("amount", "uint160"),
            ("expiration", "uint48"),
        ),
    ]
)


APPROVAL_SIGNATURES = {
    f["name"] + "(" + ",".join(i["type"] for i in f["inputs"]) + ")"
    for f in json.loads(APPROVAL_ABI)
}


class Intent(FrozenModel):
    """One permission the payload would create or change."""

    kind: IntentKind
    mode: Mode
    # The contract that stores the permission: the token, the NFT collection or Permit2.
    target: Address
    token: Address
    owner: Address
    spender: Address
    # None for NFT operator approvals, which are all-or-nothing.
    amount_raw: Quantity | None = None
    unlimited: bool = False
    # False when the change only lowers or removes a permission.
    grants: bool = True
    # Unix seconds: Permit2 allowance expiry, or the signature's deadline.
    expiration: int | None = None


class Decoded(FrozenModel):
    source: Literal["transaction", "signature"]
    # recognised: an approval format; no_approval: a known call that grants nothing;
    # unrecognised: cannot tell what it grants.
    status: Literal["recognised", "no_approval", "unrecognised"]
    intents: tuple[Intent, ...] = Field(default=(), max_length=MAX_INTENTS)
    function: str | None = None
    note: str = ""
    domain_chain_id: int | None = None
    truncated: bool = False
    # A batch where some inner calls were decoded and others could not be.
    partial: bool = False


class TxInput(FrozenModel):
    sender: Address = Field(alias="from")
    to: Address
    data: str = "0x"
    value: str = "0"

    model_config = FrozenModel.model_config | {"populate_by_name": True}


def unlimited(amount: int, bits: int = 256) -> bool:
    return is_unlimited(amount) or amount >= 2 ** (bits - 1)


def _address(value: Any) -> str:
    if not isinstance(value, str) or not ADDRESS.fullmatch(value):
        raise ValueError("expected an address")
    return value.lower()


def _int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("expected an integer")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.lower().startswith("0x"):
        number = int(value, 16)
    elif isinstance(value, str) and value.isdigit():
        number = int(value)
    else:
        raise ValueError("expected an integer")
    if not 0 <= number < 2**256:
        raise ValueError("integer out of range")
    return number


def decode_transaction_intent(tx: TxInput) -> Decoded:
    data = tx.data.lower()
    if not HEX.fullmatch(data):
        return Decoded(source="transaction", status="unrecognised", note="Calldata is not hex.")
    return _decode_call(tx.sender.lower(), tx.to.lower(), data, 0)


def _decode_call(owner: str, to: str, data: str, depth: int) -> Decoded:
    """One call made by `owner` to `to`: an approval, a batch of calls, or neither."""
    if data == "0x":
        return Decoded(
            source="transaction",
            status="no_approval",
            note="Plain value transfer with no calldata; it grants no token permission.",
        )
    if data[:10] in SELF_PERMITS:
        try:
            return _self_permit(owner, to, data)
        except (DecodingError, ValueError, OverflowError) as exc:
            return _unknown(f"The permit calldata is malformed ({type(exc).__name__}).")
    batch = _decode_batch(owner, to, data, depth)
    if batch is not None:
        return batch
    signature, arguments = decode_calldata(data, APPROVAL_ABI)
    # The shared decoder also falls back to other well-known functions (transfer, ...).
    if signature is None or signature not in APPROVAL_SIGNATURES or arguments is None:
        known = signature or resolve(data)
        if known:
            return Decoded(
                source="transaction",
                status="no_approval",
                function=known,
                note=f"{known} grants no token permission.",
            )
        return Decoded(
            source="transaction",
            status="unrecognised",
            note=f"Function {data[:10]} is not a recognised approval call. It may still grant "
            "permissions, so it cannot be cleared.",
        )
    args = {a["name"]: a["value"] for a in json.loads(arguments)}
    if signature == "setApprovalForAll(address,bool)":
        approved = bool(args["approved"])
        intent = Intent(
            kind="nft_operator",
            mode="operator",
            token=to,
            spender=args["operator"].lower(),
            grants=approved,
            target=to,
            owner=owner,
        )
    elif signature.startswith("approve(address,address"):
        if to != PERMIT2:
            return Decoded(
                source="transaction",
                status="unrecognised",
                function=signature,
                note="A Permit2-style approve sent to a contract that is not Permit2.",
            )
        amount = int(args["amount"])
        intent = Intent(
            kind="permit2_approve",
            mode="set",
            token=args["token"].lower(),
            spender=args["spender"].lower(),
            amount_raw=str(amount),
            unlimited=unlimited(amount, 160),
            grants=amount > 0,
            expiration=int(args["expiration"]),
            target=to,
            owner=owner,
        )
    else:
        amount = int(args.get("amount") or args.get("added") or args.get("subtracted") or 0)
        kind: IntentKind
        mode: Mode
        if signature.startswith("increaseAllowance"):
            kind, mode, grants = "erc20_increase", "increase", amount > 0
        elif signature.startswith("decreaseAllowance"):
            kind, mode, grants = "erc20_decrease", "decrease", False
        else:
            kind, mode, grants = "erc20_approve", "set", amount > 0
        intent = Intent(
            kind=kind,
            mode=mode,
            token=to,
            spender=args["spender"].lower(),
            amount_raw=str(amount),
            unlimited=grants and mode != "decrease" and unlimited(amount),
            grants=grants,
            target=to,
            owner=owner,
        )
    return Decoded(source="transaction", status="recognised", function=signature, intents=(intent,))


# --- Batches: calls that carry other calls ---------------------------------------------
# Inner calls are decoded only when it is certain whose permissions they change:
#   multicall(...) on a contract   -> each inner call runs as the sender, against that contract
#   Universal Router execute(...)  -> commands; PERMIT2_PERMIT(_BATCH) carry signed permits
#   execute(bytes32,bytes) to self -> an EIP-7702 / ERC-7821 batch run as the sender
# Anything else that carries calls is never cleared by its name alone.


def selector(signature: str) -> str:
    return "0x" + keccak(text=signature).hex()[:8]


MAX_DEPTH = 2
MAX_INNER_CALLS = 32
MULTICALLS = {
    selector(sig): (sig, types)
    for sig, types in (
        ("multicall(bytes[])", ["bytes[]"]),
        ("multicall(uint256,bytes[])", ["uint256", "bytes[]"]),
        ("multicall(bytes32,bytes[])", ["bytes32", "bytes[]"]),
    )
}
PERMIT_ARGS = ["address", "uint256", "uint256", "uint8", "bytes32", "bytes32"]
SELF_PERMITS = {
    selector(sig): sig
    for sig in (
        "selfPermit(address,uint256,uint256,uint8,bytes32,bytes32)",
        "selfPermitIfNecessary(address,uint256,uint256,uint8,bytes32,bytes32)",
        # DAI-style permit(holder, spender, nonce, expiry, allowed): always unlimited.
        "selfPermitAllowed(address,uint256,uint256,uint8,bytes32,bytes32)",
        "selfPermitAllowedIfNecessary(address,uint256,uint256,uint8,bytes32,bytes32)",
    )
}
ROUTER_EXECUTES = {
    selector(sig): (sig, types)
    for sig, types in (
        ("execute(bytes,bytes[],uint256)", ["bytes", "bytes[]", "uint256"]),
        ("execute(bytes,bytes[])", ["bytes", "bytes[]"]),
    )
}
ACCOUNT_EXECUTE = selector("execute(bytes32,bytes)")
# Calls that make another account act (a Safe, Multicall3, a smart account). Their inner
# calls change that account's permissions, so a recognised name must not clear them.
OPAQUE_BATCHES = {
    selector(sig): sig
    for sig in (
        "execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)",
        "multiSend(bytes)",
        "aggregate((address,bytes)[])",
        "aggregate3((address,bool,bytes)[])",
        "aggregate3Value((address,bool,uint256,bytes)[])",
        "tryAggregate(bool,(address,bytes)[])",
    )
}
# Universal Router commands (command byte & 0x3f). These codes mean the same thing in
# every Universal Router version; any other code is reported as not inspected.
ROUTER_PERMIT = 0x0A
ROUTER_PERMIT_BATCH = 0x03
ROUTER_NO_GRANT = {
    0x00: "V3_SWAP_EXACT_IN",
    0x01: "V3_SWAP_EXACT_OUT",
    0x02: "PERMIT2_TRANSFER_FROM",
    0x04: "SWEEP",
    0x05: "TRANSFER",
    0x06: "PAY_PORTION",
    0x08: "V2_SWAP_EXACT_IN",
    0x09: "V2_SWAP_EXACT_OUT",
    0x0B: "WRAP_ETH",
    0x0C: "UNWRAP_WETH",
    0x0D: "PERMIT2_TRANSFER_FROM_BATCH",
    0x0E: "BALANCE_CHECK_ERC20",
}
PERMIT_DETAILS = "(address,uint160,uint48,uint48)"
PERMIT_SINGLE = f"({PERMIT_DETAILS},address,uint256)"
PERMIT_BATCH = f"({PERMIT_DETAILS}[],address,uint256)"
UNIVERSAL_ROUTERS = frozenset(
    entry["address"]
    for entries in REGISTRY.values()
    for entry in entries
    if entry["name"].startswith("Uniswap Universal Router")
)


def _unknown(note: str, function: str | None = None) -> Decoded:
    return Decoded(source="transaction", status="unrecognised", function=function, note=note)


def _no_grant(function: str, note: str) -> Decoded:
    return Decoded(source="transaction", status="no_approval", function=function, note=note)


def _merge(function: str, parts: list[Decoded]) -> Decoded:
    """One result for a batch: every inner permission, and whether any part is unknown."""
    if not parts:
        return _unknown(f"{function} carries no inner calls.", function)
    intents = [intent for part in parts for intent in part.intents]
    unknown = [p for p in parts if p.status == "unrecognised" or p.partial]
    truncated = any(p.truncated for p in parts) or len(intents) > MAX_INTENTS
    if unknown:
        note = (
            f"{function}: {len(unknown)} of {len(parts)} inner calls could not be decoded "
            f"({unknown[0].note.rstrip('.')})."
        )
    elif intents:
        note = f"{function}: {len(intents)} permission change(s) in {len(parts)} inner calls."
    else:
        note = f"{function}: none of its {len(parts)} inner calls grants a token permission."
    if intents:
        return Decoded(
            source="transaction",
            status="recognised",
            function=function,
            intents=tuple(intents[:MAX_INTENTS]),
            note=note,
            truncated=truncated,
            partial=bool(unknown),
        )
    return Decoded(
        source="transaction",
        status="unrecognised" if unknown else "no_approval",
        function=function,
        note=note,
    )


def _self_permit(owner: str, router: str, data: str) -> Decoded:
    sig = SELF_PERMITS[data[:10]]
    token, amount_or_nonce, deadline, *_ = abi_decode(PERMIT_ARGS, bytes.fromhex(data[10:]))
    dai_style = "Allowed" in sig
    amount = 2**256 - 1 if dai_style else int(amount_or_nonce)
    intent = Intent(
        kind="erc20_permit",
        mode="set",
        target=token.lower(),
        token=token.lower(),
        owner=owner,
        spender=router,
        amount_raw=str(amount),
        unlimited=unlimited(amount),
        grants=amount > 0,
        expiration=int(deadline) or None,
    )
    return Decoded(source="transaction", status="recognised", function=sig, intents=(intent,))


def _permit2_intents(owner: str, details: list[Any], spender: str) -> list[Intent]:
    return [
        Intent(
            kind="permit2_permit",
            mode="set",
            target=PERMIT2,
            token=token.lower(),
            owner=owner,
            spender=spender.lower(),
            amount_raw=str(int(amount)),
            unlimited=unlimited(int(amount), 160),
            grants=int(amount) > 0,
            expiration=int(expiration),
        )
        for token, amount, expiration, _nonce in details
    ]


def _universal_router(owner: str, to: str, data: str) -> Decoded:
    sig, types = ROUTER_EXECUTES[data[:10]]
    commands, inputs = abi_decode(types, bytes.fromhex(data[10:]))[:2]
    if len(commands) != len(inputs) or len(commands) > MAX_INNER_CALLS:
        return _unknown("Universal Router commands and inputs do not line up.", sig)
    parts: list[Decoded] = []
    for raw, payload in zip(commands, inputs, strict=True):
        command = raw & 0x3F
        if command == ROUTER_PERMIT:
            (details, spender, _deadline), _sig = abi_decode([PERMIT_SINGLE, "bytes"], payload)
            intents = _permit2_intents(owner, [details], spender)
        elif command == ROUTER_PERMIT_BATCH:
            (details, spender, _deadline), _sig = abi_decode([PERMIT_BATCH, "bytes"], payload)
            intents = _permit2_intents(owner, list(details), spender)
        elif command in ROUTER_NO_GRANT:
            parts.append(_no_grant(ROUTER_NO_GRANT[command], f"{ROUTER_NO_GRANT[command]}."))
            continue
        else:
            parts.append(_unknown(f"Universal Router command 0x{command:02x} is not inspected"))
            continue
        parts.append(
            Decoded(
                source="transaction",
                status="recognised",
                function="PERMIT2_PERMIT",
                intents=tuple(intents[:MAX_INTENTS]),
                truncated=len(intents) > MAX_INTENTS,
            )
        )
    return _merge(f"Universal Router {sig}", parts)


def _account_batch(owner: str, data: str, depth: int) -> Decoded:
    mode, execution = abi_decode(["bytes32", "bytes"], bytes.fromhex(data[10:]))
    call_type = mode[0]
    calls: list[tuple[str, int, bytes]]
    if call_type == 0x01:
        try:
            calls = list(abi_decode(["(address,uint256,bytes)[]"], execution)[0])
        except (DecodingError, ValueError, OverflowError):
            calls = list(abi_decode(["(address,uint256,bytes)[]", "bytes"], execution)[0])
    elif call_type == 0x00 and len(execution) >= 52:
        calls = [("0x" + execution[:20].hex(), int.from_bytes(execution[20:52]), execution[52:])]
    else:
        return _unknown(f"Account execute call type 0x{call_type:02x} is not inspected.")
    if len(calls) > MAX_INNER_CALLS:
        return _unknown(f"The batch has more than {MAX_INNER_CALLS} calls.")
    parts = [
        _decode_call(owner, target.lower(), "0x" + inner.hex(), depth + 1)
        for target, _value, inner in calls
    ]
    return _merge("execute(bytes32,bytes) batch from your own account", parts)


def _decode_batch(owner: str, to: str, data: str, depth: int) -> Decoded | None:
    """Decode a call that carries other calls, or None if this is not one."""
    head = data[:10]
    if head not in MULTICALLS and head not in ROUTER_EXECUTES and head != ACCOUNT_EXECUTE:
        if head in OPAQUE_BATCHES:
            return _unknown(
                f"{OPAQUE_BATCHES[head]} makes another account act; its inner calls are not "
                "inspected, so it cannot be cleared.",
                OPAQUE_BATCHES[head],
            )
        return None
    if depth >= MAX_DEPTH:
        return _unknown("Batches nested this deep are not inspected.")
    try:
        if head in MULTICALLS:
            sig, types = MULTICALLS[head]
            calls = abi_decode(types, bytes.fromhex(data[10:]))[-1]
            if len(calls) > MAX_INNER_CALLS:
                return _unknown(f"The multicall has more than {MAX_INNER_CALLS} calls.", sig)
            return _merge(sig, [_decode_call(owner, to, "0x" + c.hex(), depth + 1) for c in calls])
        if head in ROUTER_EXECUTES:
            if to not in UNIVERSAL_ROUTERS:
                return _unknown(
                    f"{ROUTER_EXECUTES[head][0]} sent to {to}, which is not a published "
                    "Uniswap Universal Router; its commands are not inspected.",
                    ROUTER_EXECUTES[head][0],
                )
            return _universal_router(owner, to, data)
        if to != owner:
            return _unknown(
                "execute(bytes32,bytes) sent to another account runs its calls as that "
                "account; they are not inspected.",
                "execute(bytes32,bytes)",
            )
        return _account_batch(owner, data, depth)
    except (DecodingError, ValueError, OverflowError, TypeError) as exc:
        return _unknown(f"The batch calldata is malformed ({type(exc).__name__}).")


def decode_typed_data(typed: dict[str, Any], owner: str | None) -> Decoded:
    """EIP-712 payloads that grant spending power: EIP-2612 Permit and Permit2 formats."""

    def unknown(note: str) -> Decoded:
        return Decoded(source="signature", status="unrecognised", note=note)

    try:
        domain = typed.get("domain") or {}
        primary = str(typed.get("primaryType") or "")
        message = typed.get("message") or {}
        if not isinstance(domain, dict) or not isinstance(message, dict):
            return unknown("Typed data must have object domain and message fields.")
        chain_id = _int(domain["chainId"]) if "chainId" in domain else None
        verifying = _address(domain.get("verifyingContract"))
        intents: list[Intent] = []
        if primary == "Permit":
            amount = _int(message["value"])
            intents.append(
                Intent(
                    kind="erc20_permit",
                    mode="set",
                    target=verifying,
                    token=verifying,
                    owner=_address(message["owner"]),
                    spender=_address(message["spender"]),
                    amount_raw=str(amount),
                    unlimited=unlimited(amount),
                    grants=amount > 0,
                    expiration=_int(message["deadline"]),
                )
            )
        elif primary in ("PermitSingle", "PermitBatch") or "TransferFrom" in primary:
            if verifying != PERMIT2:
                return unknown(
                    f"{primary} names verifying contract {verifying}, which is not Permit2."
                )
            signer = _address(owner)
            spender = _address(message["spender"])
            if primary in ("PermitSingle", "PermitBatch"):
                details = message["details"]
                for item in details if isinstance(details, list) else [details]:
                    amount = _int(item["amount"])
                    intents.append(
                        Intent(
                            kind="permit2_permit",
                            mode="set",
                            target=PERMIT2,
                            token=_address(item["token"]),
                            owner=signer,
                            spender=spender,
                            amount_raw=str(amount),
                            unlimited=unlimited(amount, 160),
                            grants=amount > 0,
                            expiration=_int(item["expiration"]),
                        )
                    )
            elif primary.startswith(
                (
                    "PermitTransferFrom",
                    "PermitBatchTransferFrom",
                    "PermitWitnessTransferFrom",
                    "PermitBatchWitnessTransferFrom",
                )
            ):
                permitted = message["permitted"]
                for item in permitted if isinstance(permitted, list) else [permitted]:
                    amount = _int(item["amount"])
                    intents.append(
                        Intent(
                            kind="permit2_transfer",
                            mode="one_time",
                            target=PERMIT2,
                            token=_address(item["token"]),
                            owner=signer,
                            spender=spender,
                            amount_raw=str(amount),
                            unlimited=unlimited(amount),
                            grants=amount > 0,
                            expiration=_int(message["deadline"]),
                        )
                    )
            else:
                return unknown(f"Permit2 message type {primary} is not recognised.")
        else:
            return unknown(
                f"Typed data of type {primary or 'unknown'} is not a recognised permit. It may "
                "still authorise transfers (for example a marketplace order)."
            )
    except (KeyError, TypeError, ValueError) as exc:
        return unknown(f"Typed data is malformed: {exc}.")
    return Decoded(
        source="signature",
        status="recognised",
        function=primary,
        intents=tuple(intents[:MAX_INTENTS]),
        domain_chain_id=chain_id,
        truncated=len(intents) > MAX_INTENTS,
    )
