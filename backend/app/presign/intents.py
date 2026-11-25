"""Decode what an unsigned transaction or an EIP-712 signature would grant.

Nothing here touches the network. A transaction's calldata is decoded with the shared
decoder against a fixed ABI of approval functions; typed data is matched against the
permit formats that move spending power without a transaction (EIP-2612 and Permit2).
Anything that is not recognised is reported as such, never guessed.
"""

import json
import re
from typing import Any, Literal

from pydantic import Field

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
    owner, to = tx.sender.lower(), tx.to.lower()
    if not HEX.fullmatch(data):
        return Decoded(source="transaction", status="unrecognised", note="Calldata is not hex.")
    if data == "0x":
        return Decoded(
            source="transaction",
            status="no_approval",
            note="Plain value transfer with no calldata; it grants no token permission.",
        )
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
            "permissions (for example inside a multicall), so it cannot be cleared.",
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
