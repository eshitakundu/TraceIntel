from typing import Any

import httpx
import pytest
from app.evaluation import presign as ev
from app.evaluation.presign import (
    KEY,
    MAX,
    NOW,
    OWNER,
    PROXY_ONE_KEY,
    SPENDER,
    TOKEN,
    UNISWAP_V3_ROUTER,
    ChainState,
    approve,
    erc2612_permit,
    grounded,
    permit2_single,
    run_check,
    set_approval_for_all,
)
from app.evaluation.scenarios import scripted
from app.models.interpretation import ReportDraft
from app.presign.intents import (
    PERMIT2,
    TxInput,
    decode_transaction_intent,
    decode_typed_data,
)
from app.presign.reads import State
from app.presign.rules import Facts, evaluate

SEAPORT_CONDUIT = "0x1e0049783f008a0085193e00003d00cd54003c71"


def tx(data: str, to: str = TOKEN) -> TxInput:
    return TxInput.model_validate({"from": OWNER, "to": to, "data": data})


def call(selector: str, *words: int | str) -> str:
    body = "".join(
        w[2:].lower().zfill(64) if isinstance(w, str) else format(w, "064x") for w in words
    )
    return selector + body


# ——— Decoding ———


def test_decodes_erc20_approve_and_unlimited() -> None:
    decoded = decode_transaction_intent(approve(SPENDER.upper().replace("0X", "0x"), MAX))
    (intent,) = decoded.intents
    assert decoded.status == "recognised"
    assert (intent.kind, intent.mode, intent.spender) == ("erc20_approve", "set", SPENDER)
    assert intent.unlimited and intent.grants and intent.owner == OWNER


def test_decodes_increase_and_decrease() -> None:
    up = decode_transaction_intent(tx(call("0x39509351", SPENDER, 5))).intents[0]
    down = decode_transaction_intent(tx(call("0xa457c2d7", SPENDER, 5))).intents[0]
    assert (up.kind, up.mode, up.grants) == ("erc20_increase", "increase", True)
    assert (down.kind, down.mode, down.grants) == ("erc20_decrease", "decrease", False)


def test_approve_zero_is_a_revoke() -> None:
    (intent,) = decode_transaction_intent(approve(SPENDER, 0)).intents
    assert not intent.grants and not intent.unlimited


def test_decodes_nft_operator_both_ways() -> None:
    on = decode_transaction_intent(set_approval_for_all(SPENDER)).intents[0]
    off = decode_transaction_intent(set_approval_for_all(SPENDER, False)).intents[0]
    assert on.kind == "nft_operator" and on.grants and not off.grants


def test_permit2_approve_only_counts_when_sent_to_permit2() -> None:
    data = call("0x87517c45", TOKEN, SPENDER, 2**160 - 1, NOW + 60)
    good = decode_transaction_intent(tx(data, to=PERMIT2))
    bad = decode_transaction_intent(tx(data, to=SPENDER))
    assert good.intents[0].kind == "permit2_approve" and good.intents[0].unlimited
    assert good.intents[0].expiration == NOW + 60
    assert bad.status == "unrecognised"


@pytest.mark.parametrize(
    ("data", "status"),
    [
        ("0x", "no_approval"),
        (call("0xa9059cbb", SPENDER, 1), "no_approval"),  # transfer
        ("0xac9650d8" + "00" * 64, "unrecognised"),  # multicall
        ("0x095ea7b3" + "00" * 10, "unrecognised"),  # truncated approve
        ("0xzz", "unrecognised"),
    ],
)
def test_non_approval_calldata(data: str, status: str) -> None:
    assert decode_transaction_intent(tx(data)).status == status


def test_decodes_eip2612_permit() -> None:
    decoded = decode_typed_data(erc2612_permit(SPENDER, 10**18), None)
    (intent,) = decoded.intents
    assert (intent.kind, intent.token, intent.owner) == ("erc20_permit", TOKEN, OWNER)
    assert decoded.domain_chain_id == 1 and intent.expiration == NOW + 600


def test_decodes_permit2_single_batch_and_transfer() -> None:
    single = decode_typed_data(permit2_single(SPENDER, 2**160 - 1), OWNER)
    assert single.intents[0].kind == "permit2_permit" and single.intents[0].unlimited
    batch = permit2_single(SPENDER, 5)
    batch["primaryType"] = "PermitBatch"
    batch["message"]["details"] = [batch["message"]["details"]] * 3
    assert len(decode_typed_data(batch, OWNER).intents) == 3
    transfer = {
        "domain": {"chainId": 1, "verifyingContract": PERMIT2},
        "primaryType": "PermitWitnessTransferFrom",
        "message": {
            "permitted": {"token": TOKEN, "amount": "7"},
            "spender": SPENDER,
            "nonce": 1,
            "deadline": NOW,
        },
    }
    (intent,) = decode_typed_data(transfer, OWNER).intents
    assert (intent.kind, intent.mode, intent.amount_raw) == ("permit2_transfer", "one_time", "7")


def test_fake_permit2_and_unknown_typed_data_are_unrecognised() -> None:
    fake = permit2_single(SPENDER, 5)
    fake["domain"]["verifyingContract"] = SPENDER
    order = {"domain": {"verifyingContract": SPENDER}, "primaryType": "OrderComponents"}
    assert decode_typed_data(fake, OWNER).status == "unrecognised"
    assert decode_typed_data(order, OWNER).status == "unrecognised"
    assert decode_typed_data({"domain": "x"}, OWNER).status == "unrecognised"
    assert decode_typed_data(permit2_single(SPENDER, 5), None).status == "unrecognised"


# ——— Rules (pure: no chain) ———


def facts(tx_input: TxInput, state: State | None = None, **spender: Any) -> tuple[Any, list[Facts]]:
    decoded = decode_transaction_intent(tx_input)
    items = [
        Facts(
            pid="p0",
            intent=decoded.intents[0],
            state=state if state is not None else State(target_has_code=True, balance=1),
            spender=spender,
        )
    ]
    return decoded, items


def rules_of(decoded: Any, items: list[Facts], ts: int | None = NOW) -> tuple[str, list[str]]:
    verdict, reasons = evaluate(decoded, 1, items, {"p0", "p0:spender"}, ts)
    return verdict, [r.rule for r in reasons]


def test_known_contract_finite_amount_is_allowed() -> None:
    decoded, items = facts(approve(UNISWAP_V3_ROUTER, 5), kind="contract", known="Router")
    assert rules_of(decoded, items) == ("allow", [])


def test_missing_spender_facts_never_allow() -> None:
    decoded, items = facts(approve(UNISWAP_V3_ROUTER, 5))
    assert rules_of(decoded, items)[0] == "warn"


def test_unread_state_never_allows() -> None:
    state = State(target_has_code=True, errors=["balance unavailable or non-standard"])
    decoded, items = facts(approve(UNISWAP_V3_ROUTER, 5), state, kind="contract", known="R")
    assert rules_of(decoded, items) == ("warn", ["COULD_NOT_VERIFY"])
    # Labels are cosmetic: a missing symbol does not make the check unverifiable.
    state = State(target_has_code=True, errors=["symbol unavailable or non-standard"])
    decoded, items = facts(approve(UNISWAP_V3_ROUTER, 5), state, kind="contract", known="R")
    assert rules_of(decoded, items) == ("allow", [])


def test_target_without_code_warns() -> None:
    decoded, items = facts(
        approve(UNISWAP_V3_ROUTER, 5), State(target_has_code=False), kind="contract", known="R"
    )
    assert rules_of(decoded, items) == ("warn", ["COULD_NOT_VERIFY"])


@pytest.mark.parametrize("kind", ["eoa", "delegated"])
def test_key_held_spender_blocks(kind: str) -> None:
    decoded, items = facts(approve(KEY, 5), kind=kind)
    verdict, rules = rules_of(decoded, items)
    assert verdict == "block" and rules[0] == "SPENDER_IS_KEY"


def test_upgrade_control_rules() -> None:
    decoded, items = facts(approve(SPENDER, MAX), kind="contract", proxy=True, control="single_key")
    assert "UNLIMITED_TO_SINGLE_KEY_PROXY" in rules_of(decoded, items)[1]
    decoded, items = facts(approve(SPENDER, 5), kind="contract", proxy=True, control="undetermined")
    verdict, rules = rules_of(decoded, items)
    assert verdict == "warn" and "UPGRADEABLE_SPENDER" in rules
    decoded, items = facts(
        approve(SPENDER, 5), kind="contract", proxy=True, control="contract", known="X"
    )
    assert rules_of(decoded, items) == ("allow", [])


def test_increase_needs_the_current_allowance() -> None:
    data = tx(call("0x39509351", UNISWAP_V3_ROUTER, 5))
    decoded, items = facts(data, State(target_has_code=True, balance=1), kind="contract", known="R")
    assert rules_of(decoded, items) == ("warn", ["COULD_NOT_VERIFY"])
    state = State(target_has_code=True, balance=1, allowance=MAX - 2)
    decoded, items = facts(data, state, kind="contract", known="R")
    assert rules_of(decoded, items) == ("warn", ["UNLIMITED_AMOUNT"])


def test_nft_operator_rules() -> None:
    state = State(target_has_code=True, operator_approved=False)
    decoded, items = facts(set_approval_for_all(SEAPORT_CONDUIT), state, kind="contract", known="C")
    assert rules_of(decoded, items) == ("allow", [])
    decoded, items = facts(set_approval_for_all(SPENDER), state, kind="contract")
    assert rules_of(decoded, items) == ("block", ["NFT_OPERATOR_UNKNOWN"])


def test_long_lived_permit2_grant_warns() -> None:
    data = tx(call("0x87517c45", TOKEN, UNISWAP_V3_ROUTER, 5, NOW + 90 * 86400), to=PERMIT2)
    state = State(target_has_code=True, balance=1, allowance=0, token_to_permit2=MAX)
    decoded, items = facts(data, state, kind="contract", known="R")
    assert rules_of(decoded, items) == ("warn", ["LONG_LIVED"])
    assert rules_of(decoded, items, ts=None)[0] == "allow"


# ——— End to end on the scripted chain ———


async def test_report_cites_evidence_and_reach() -> None:
    decoded = decode_transaction_intent(approve(SPENDER, MAX))
    report = await run_check(PROXY_ONE_KEY, decoded, {})
    claims = {c.id: c.text for c in report.claims}
    assert report.verdict == "block" and grounded(report)
    assert report.block is not None and report.block.timestamp == NOW
    assert "could move all of it" in claims["p0:reach"]
    assert "single externally owned key" in claims["p0:control"]
    assert {s.name for s in report.checks} == {
        "spender_profile",
        "known_spender",
        "upgrade_control",
    }
    assert report.to_json()["evidence"][0]["id"] == "input"


async def test_permit2_reach_is_capped_by_the_allowance_to_permit2() -> None:
    world = ChainState(to_permit2=0)
    typed = permit2_single(UNISWAP_V3_ROUTER, 10**18)
    report = await run_check(world, decode_typed_data(typed, OWNER), typed)
    reach = {c.id: c.text for c in report.claims}["p0:reach"]
    assert "up to 0 WETH" in reach and "no allowance" in reach


async def test_model_explanation_is_validated() -> None:
    decoded = decode_transaction_intent(approve(KEY, 5))
    good = ReportDraft(summary=["v0"], findings=["p0:spender"])
    report = await run_check(ChainState(), decoded, {}, explain=True, llm=scripted(good))
    assert report.explanation is not None and report.explanation.author == "model"
    assert [c.id for c in report.explanation.summary] == ["v0"]
    assert report.verdict == "block" and grounded(report)


async def test_explain_without_a_model_uses_rules() -> None:
    decoded = decode_transaction_intent(approve(KEY, 5))
    report = await run_check(ChainState(), decoded, {}, explain=True)
    assert report.explanation is not None and report.explanation.author == "baseline"
    assert "No model configured" in (report.explanation.reason or "")


# ——— MCP surface ———


async def test_mcp_tools_are_listed_read_only() -> None:
    from app.presign.mcp_server import server

    tools = {t.name: t for t in await server.list_tools()}
    assert set(tools) == {"check_approval_before_signing", "check_signature_before_signing"}
    for tool in tools.values():
        assert tool.annotations is not None and tool.annotations.readOnlyHint is True


async def test_mcp_tool_call_returns_structured_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.presign import mcp_server

    real = httpx.AsyncClient
    monkeypatch.setattr(
        mcp_server.httpx,
        "AsyncClient",
        lambda **_: real(transport=ev.scripted_chain(PROXY_ONE_KEY)),
    )
    result = await mcp_server.server.call_tool(
        "check_approval_before_signing",
        {"chain": "ethereum", "tx": approve(SPENDER, MAX).model_dump(by_alias=True)},
    )
    structured = result[1] if isinstance(result, tuple) else result
    assert isinstance(structured, dict)
    assert structured["verdict"] == "block"
    assert structured["reasons"][0]["rule"] == "UNLIMITED_TO_SINGLE_KEY_PROXY"
    assert structured["note"].startswith("Read-only")
