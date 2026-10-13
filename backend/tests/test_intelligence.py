import json
from pathlib import Path

import httpx
import pytest
from app.blockchain.chains import chains
from app.blockchain.contract_inspector import inspect_contract
from app.blockchain.decoder import decode_transaction
from app.blockchain.proxy_detector import storage_address
from app.blockchain.rpc_client import RpcClient
from app.config import Settings
from app.models.blockchain import Approval, Contract, RawTransaction
from app.risk.engine import evaluate


def test_proxy_address_and_invalid_padding() -> None:
    assert storage_address("0x" + "0" * 64) is None
    assert storage_address("0x" + "0" * 24 + "a" * 40) == "0x" + "a" * 40
    with pytest.raises(ValueError):
        storage_address("0x" + "f" * 64)


@pytest.mark.asyncio
async def test_missing_explorer_is_not_unverified() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        value = "0x6000" if body["method"] == "eth_getCode" else "0x" + "0" * 64
        return httpx.Response(200, json={"id": body["id"], "result": value})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        contract, evidence, coverage = await inspect_contract(
            RpcClient(client, "https://rpc.invalid"),
            client,
            chains(Settings())["ethereum"],
            "0x" + "1" * 40,
            "0x1",
            "test",
        )
        assert contract.kind == "contract"
        assert contract.verification == "unavailable"
        assert any(c.area.startswith("explorer") and c.status == "unavailable" for c in coverage)
        assert evidence[0].source == "eth_getCode"


def test_risk_deduplicates_and_preserves_unknowns() -> None:
    raw = RawTransaction.model_validate_json(Path("evals/cases/ethereum-recorded.json").read_text())
    decoded = decode_transaction(raw)
    approval = Approval(
        standard="ERC20",
        token="0x" + "1" * 40,
        owner="0x" + "2" * 40,
        spender="0x" + "3" * 40,
        amount_raw=str(2**256 - 1),
        unlimited=True,
        evidence_ids=("synthetic:approval",),
    )
    decoded = decoded.model_copy(update={"approvals": (approval, approval)})
    result = evaluate(decoded, ())
    assert result.score == 30
    unknown = Contract(address=decoded.transaction.recipient or "0x" + "4" * 40, kind="unknown")
    assert evaluate(decoded, (unknown,)).score == 30
    assert all(signal.score >= 0 for signal in result.signals)
    assert not any(s.code == "UNVERIFIED_TARGET" for s in evaluate(decoded, (unknown,)).signals)


def _code_rpc(code_by_block: dict[str, str]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body["method"] == "eth_getCode":
            code = code_by_block.get(body["params"][1])
            if code is None:
                error = {"code": -32000, "message": "missing trie node"}
                return httpx.Response(200, json={"id": body["id"], "error": error})
            return httpx.Response(200, json={"id": body["id"], "result": code})
        return httpx.Response(200, json={"id": body["id"], "result": "0x" + "0" * 64})

    return httpx.MockTransport(handler)


async def _inspect(transport: httpx.MockTransport) -> tuple[Contract, tuple, tuple]:  # type: ignore[type-arg]
    async with httpx.AsyncClient(transport=transport) as client:
        return await inspect_contract(
            RpcClient(client, "https://rpc.invalid"),
            client,
            chains(Settings())["ethereum"],
            "0x" + "1" * 40,
            "0x1",
            "test",
        )


@pytest.mark.asyncio
async def test_pruned_history_falls_back_to_labelled_current_state() -> None:
    contract, evidence, coverage = await _inspect(_code_rpc({"latest": "0x6000"}))
    assert contract.kind == "contract"
    assert contract.state == "current"
    assert "latest block" in evidence[0].description
    assert any(c.status == "partial" and "pruned" in c.reason for c in coverage)


@pytest.mark.asyncio
async def test_eip7702_delegation_is_an_eoa_not_a_contract() -> None:
    contract, _, _ = await _inspect(_code_rpc({"0x1": "0xef0100" + "a" * 40}))
    assert contract.kind == "delegated_eoa"
    assert contract.implementation == "0x" + "a" * 40
    assert contract.state == "historical"


def _recorded_with(*approvals: Approval) -> tuple:  # type: ignore[type-arg]
    raw = RawTransaction.model_validate_json(Path("evals/cases/ethereum-recorded.json").read_text())
    decoded = decode_transaction(raw)
    return decoded.model_copy(update={"approvals": approvals}), decoded.transaction


def test_owner_roles_and_only_sender_approvals_are_scored() -> None:
    from app.blockchain.ownership import owner_role

    decoded, tx = _recorded_with()
    assert owner_role(tx.sender, tx) == "sender"
    assert tx.recipient and owner_role(tx.recipient.upper(), tx) == "called_contract"
    assert owner_role("0x" + "9" * 40, tx) == "other"
    unlimited = Approval(
        standard="ERC20",
        token="0x" + "1" * 40,
        owner="0x" + "9" * 40,
        spender="0x" + "3" * 40,
        amount_raw=str(2**256 - 1),
        unlimited=True,
        evidence_ids=("synthetic:other",),
        owner_role="other",
    )
    risk = evaluate(decoded.model_copy(update={"approvals": (unlimited,)}), ())
    assert risk.score == 0
    assert [s.code for s in risk.signals if s.code == "APPROVAL_BY_OTHER_OWNER"]
    mine = unlimited.model_copy(update={"owner": tx.sender, "owner_role": "sender"})
    assert evaluate(decoded.model_copy(update={"approvals": (mine,)}), ()).score == 30


def test_erc721_approval_semantics_use_the_approved_address() -> None:
    decoded, tx = _recorded_with()
    spender = "0x" + "3" * 40
    contract = Contract(address=spender, kind="contract", evidence_ids=("synthetic:code",))
    token_zero = Approval(
        standard="ERC721",
        token="0x" + "1" * 40,
        owner=tx.sender,
        spender=spender,
        amount_raw="0",
        unlimited=False,
        evidence_ids=("synthetic:nft",),
        owner_role="sender",
    )
    granted = evaluate(decoded.model_copy(update={"approvals": (token_zero,)}), (contract,))
    assert any(s.code == "CONTRACT_SPENDER" for s in granted.signals)
    cleared = token_zero.model_copy(update={"spender": "0x" + "0" * 40, "amount_raw": "7"})
    risk = evaluate(decoded.model_copy(update={"approvals": (cleared,)}), (contract,))
    assert not any(s.code == "CONTRACT_SPENDER" for s in risk.signals)
