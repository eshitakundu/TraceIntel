"""Upgrade-authority detection: code-fixed admins, Safe multisigs, timelocks, owner() chains."""

import asyncio
from types import SimpleNamespace
from typing import Any

from app.agents.tools import (
    ADMIN_SELECTOR,
    MIN_DELAY_SELECTOR,
    OWNER_SELECTOR,
    PROBE_CALLER,
    SAFE_OWNERS_SELECTOR,
    SAFE_THRESHOLD_SELECTOR,
    classify_controller,
    embedded_addresses,
    immutable_admin,
)
from app.blockchain.rpc_client import RpcError
from eth_abi.abi import encode

PROXY = "0x" + "11" * 20
ADMIN = "0x" + "22" * 20
OWNER = "0x" + "33" * 20
KEY = "0x" + "44" * 20
CODE = "0x6080"


def word(value: int | str) -> str:
    if isinstance(value, str):
        return "0x" + value[2:].zfill(64)
    return "0x" + format(value, "064x")


class FakeRpc:
    """Answers eth_getCode from `code` and eth_call from `calls[(to, selector, from)]`."""

    def __init__(self, code: dict[str, str], calls: dict[tuple[str, str, str | None], str]):
        self.code, self.calls = code, calls

    async def call(self, method: str, params: list[Any]) -> Any:
        if method == "eth_getCode":
            return self.code.get(params[0], "0x")
        tx = params[0]
        key = (tx["to"], tx["data"][:10], tx.get("from"))
        if key not in self.calls:
            raise RpcError("execution reverted")
        return self.calls[key]


def ctx(code: dict[str, str], calls: dict[tuple[str, str, str | None], str]) -> Any:
    return SimpleNamespace(rpc=FakeRpc(code, calls), tag="latest")


def classify(code: dict[str, str], calls: dict[tuple[str, str, str | None], str]) -> Any:
    chain: list[dict[str, Any]] = []
    control, text = asyncio.run(classify_controller(ctx(code, calls), ADMIN, chain))
    return control, text, chain


def test_embedded_addresses_reads_push20_and_padded_push32() -> None:
    code = "0x60016002" + "73" + ADMIN[2:] + "7f" + "00" * 12 + OWNER[2:] + "61ffff"
    assert embedded_addresses(code) == [ADMIN, OWNER]
    # Bytes inside another push's data are not opcodes.
    assert embedded_addresses("0x7f" + "73" + ADMIN[2:] + "00" * 11) == []
    assert embedded_addresses("0xzz") == []


def test_immutable_admin_needs_a_caller_gated_answer() -> None:
    code = "0x73" + ADMIN[2:]
    gated = {(PROXY, ADMIN_SELECTOR, ADMIN): word(ADMIN)}
    assert asyncio.run(immutable_admin(ctx({}, gated), PROXY, code)) == ADMIN
    # admin() that answers everyone comes from the implementation: not proof.
    open_to_all = gated | {(PROXY, ADMIN_SELECTOR, PROBE_CALLER): word(ADMIN)}
    assert asyncio.run(immutable_admin(ctx({}, open_to_all), PROXY, code)) is None
    assert asyncio.run(immutable_admin(ctx({}, {}), PROXY, code)) is None


def safe(threshold: int, owners: int) -> dict[tuple[str, str, str | None], str]:
    return {
        (ADMIN, SAFE_THRESHOLD_SELECTOR, None): word(threshold),
        (ADMIN, SAFE_OWNERS_SELECTOR, None): "0x" + encode(["address[]"], [[KEY] * owners]).hex(),
    }


def test_one_signer_safe_is_a_single_key() -> None:
    control, text, chain = classify({ADMIN: CODE}, safe(1, 3))
    assert control == "single_key" and "1-of-3 multisig" in text
    assert chain[0]["type"] == "multisig"


def test_multi_signer_safe_is_a_contract() -> None:
    control, text, _ = classify({ADMIN: CODE}, safe(3, 5))
    assert control == "contract" and "3-of-5 multisig" in text


def test_implausible_safe_answers_are_ignored() -> None:
    # A fallback that echoes an address for every call is not a 1-of-N Safe.
    calls = {(ADMIN, SAFE_THRESHOLD_SELECTOR, None): word(KEY)}
    control, _, chain = classify({ADMIN: CODE}, calls)
    assert control == "contract" and chain[0]["type"] == "contract"


def test_timelock_delay_is_reported() -> None:
    calls = {(ADMIN, MIN_DELAY_SELECTOR, None): word(2 * 86400)}
    control, text, chain = classify({ADMIN: CODE}, calls)
    assert control == "contract" and "2 days" in text
    assert chain[0]["delay_seconds"] == 2 * 86400


def test_owner_chain_ends_at_a_key() -> None:
    calls = {
        (ADMIN, OWNER_SELECTOR, None): word(OWNER),
        (OWNER, OWNER_SELECTOR, None): word(KEY),
    }
    control, text, chain = classify({ADMIN: CODE, OWNER: CODE}, calls)
    assert control == "single_key" and text.endswith("a single externally owned key")
    assert [hop["address"] for hop in chain] == [ADMIN, OWNER, KEY]


def test_owner_chain_stops_after_three_hops() -> None:
    hops = [ADMIN, OWNER, "0x" + "55" * 20, "0x" + "66" * 20]
    calls = {(a, OWNER_SELECTOR, None): word(b) for a, b in zip(hops, hops[1:], strict=False)}
    control, _, chain = classify(dict.fromkeys(hops, CODE), calls)
    assert control == "contract" and len(chain) == 3
