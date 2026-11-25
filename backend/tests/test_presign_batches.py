"""Approvals hidden inside batches: multicall, Universal Router commands, EIP-7702 batches."""

from app.presign.intents import (
    ACCOUNT_EXECUTE,
    MAX_DEPTH,
    PERMIT2,
    TxInput,
    decode_transaction_intent,
    selector,
)
from eth_abi.abi import encode

OWNER = "0x" + "0a" * 20
TOKEN = "0x" + "70" * 20
KEY = "0x" + "e0" * 20
ROUTER = "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45"  # Uniswap V3 SwapRouter02
UNIVERSAL_ROUTER = "0x66a9893cc07d91d95644aedd05d03f95e1dba8af"
MAX = 2**256 - 1


def call(signature: str, types: list[str], values: list[object]) -> str:
    return selector(signature) + encode(types, values).hex()


def approve(spender: str, amount: int) -> str:
    return call("approve(address,uint256)", ["address", "uint256"], [spender, amount])


def multicall(*calls: str) -> str:
    return call("multicall(bytes[])", ["bytes[]"], [[bytes.fromhex(c[2:]) for c in calls]])


def decode(to: str, data: str, sender: str = OWNER):  # type: ignore[no-untyped-def]
    return decode_transaction_intent(
        TxInput.model_validate({"from": sender, "to": to, "data": data})
    )


SELF_PERMIT = call(
    "selfPermit(address,uint256,uint256,uint8,bytes32,bytes32)",
    ["address", "uint256", "uint256", "uint8", "bytes32", "bytes32"],
    [TOKEN, 5 * 10**18, 1_800_000_000, 27, b"\x01" * 32, b"\x02" * 32],
)
UNKNOWN_CALL = "0xdeadbeef" + "00" * 32


def test_approval_hidden_in_a_token_multicall_is_found() -> None:
    decoded = decode(TOKEN, multicall(approve(KEY, MAX)))
    assert decoded.status == "recognised" and not decoded.partial
    (intent,) = decoded.intents
    assert (intent.kind, intent.token, intent.spender, intent.owner) == (
        "erc20_approve",
        TOKEN,
        KEY,
        OWNER,
    )
    assert intent.unlimited


def test_router_self_permit_grants_the_router() -> None:
    decoded = decode(ROUTER, multicall(SELF_PERMIT))
    (intent,) = decoded.intents
    assert intent.kind == "erc20_permit" and intent.spender == ROUTER and intent.token == TOKEN
    assert intent.amount_raw == str(5 * 10**18) and not intent.unlimited


def test_dai_style_self_permit_is_unlimited() -> None:
    data = call(
        "selfPermitAllowed(address,uint256,uint256,uint8,bytes32,bytes32)",
        ["address", "uint256", "uint256", "uint8", "bytes32", "bytes32"],
        [TOKEN, 0, 0, 27, b"\x01" * 32, b"\x02" * 32],
    )
    (intent,) = decode(ROUTER, data).intents
    assert intent.unlimited and intent.expiration is None


def test_unknown_inner_call_marks_the_batch_partial() -> None:
    decoded = decode(ROUTER, multicall(SELF_PERMIT, UNKNOWN_CALL))
    assert decoded.status == "recognised" and decoded.partial
    assert "1 of 2 inner calls could not be decoded" in decoded.note
    only_unknown = decode(ROUTER, multicall(UNKNOWN_CALL))
    assert only_unknown.status == "unrecognised"


def test_empty_malformed_and_deep_batches_are_not_cleared() -> None:
    assert decode(TOKEN, multicall()).status == "unrecognised"
    assert decode(TOKEN, selector("multicall(bytes[])") + "00" * 64).status == "unrecognised"
    nested = approve(KEY, 1)
    for _ in range(MAX_DEPTH + 1):
        nested = multicall(nested)
    assert decode(TOKEN, nested).status == "unrecognised"


def universal_router(commands: bytes, inputs: list[bytes]) -> str:
    return call(
        "execute(bytes,bytes[],uint256)", ["bytes", "bytes[]", "uint256"], [commands, inputs, 2**40]
    )


def permit2_permit(spender: str, amount: int) -> bytes:
    return encode(
        ["((address,uint160,uint48,uint48),address,uint256)", "bytes"],
        [((TOKEN, amount, 1_800_000_000, 0), spender, 1_800_000_000), b"\x00" * 65],
    )


def test_universal_router_permit_and_swap() -> None:
    data = universal_router(bytes([0x0A, 0x00]), [permit2_permit(UNIVERSAL_ROUTER, 10**18), b""])
    decoded = decode(UNIVERSAL_ROUTER, data)
    assert decoded.status == "recognised" and not decoded.partial
    (intent,) = decoded.intents
    assert (intent.kind, intent.target, intent.spender) == (
        "permit2_permit",
        PERMIT2,
        UNIVERSAL_ROUTER,
    )


def test_universal_router_swap_only_grants_nothing() -> None:
    decoded = decode(UNIVERSAL_ROUTER, universal_router(bytes([0x00, 0x04]), [b"", b""]))
    assert decoded.status == "no_approval"


def test_universal_router_unknown_command_and_lookalike_router() -> None:
    assert decode(UNIVERSAL_ROUTER, universal_router(bytes([0x10]), [b""])).status == "unrecognised"
    lookalike = universal_router(bytes([0x0A]), [permit2_permit(KEY, 2**160 - 1)])
    assert decode(KEY, lookalike).status == "unrecognised"


def account_batch(*calls: tuple[str, str]) -> str:
    mode = bytes([0x01]) + bytes(31)
    execution = encode(
        ["(address,uint256,bytes)[]"], [[(to, 0, bytes.fromhex(d[2:])) for to, d in calls]]
    )
    return ACCOUNT_EXECUTE + encode(["bytes32", "bytes"], [mode, execution]).hex()


def test_eip7702_batch_to_self_is_decoded() -> None:
    decoded = decode(OWNER, account_batch((TOKEN, approve(KEY, MAX)), (KEY, "0x")))
    assert decoded.status == "recognised" and not decoded.partial
    assert decoded.intents[0].spender == KEY and decoded.intents[0].owner == OWNER


def test_account_execute_on_another_account_is_not_cleared() -> None:
    assert decode(KEY, account_batch((TOKEN, approve(KEY, MAX)))).status == "unrecognised"


def test_safe_and_multicall3_batches_are_never_cleared_by_name() -> None:
    exec_tx = call(
        "execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)",
        [
            "address",
            "uint256",
            "bytes",
            "uint8",
            "uint256",
            "uint256",
            "uint256",
            "address",
            "address",
            "bytes",
        ],
        [TOKEN, 0, bytes.fromhex(approve(KEY, MAX)[2:]), 0, 0, 0, 0, KEY, KEY, b""],
    )
    assert decode(KEY, exec_tx).status == "unrecognised"
    aggregate = call("aggregate3((address,bool,bytes)[])", ["(address,bool,bytes)[]"], [[]])
    assert decode(KEY, aggregate).status == "unrecognised"
