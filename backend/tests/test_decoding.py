import json
from pathlib import Path

import pytest
from app.blockchain.decoder import decode_transaction
from app.blockchain.event_decoder import APPROVAL, TRANSFER, decode_events
from app.models.blockchain import RawTransaction
from pydantic import ValidationError

OWNER = "0x" + "11" * 20
SPENDER = "0x" + "22" * 20
TOKEN = "0x" + "33" * 20
HASH = "0x" + "a" * 64


def approval_log(amount: int) -> dict[str, object]:
    return {
        "address": TOKEN,
        "topics": [APPROVAL, "0x" + "0" * 24 + OWNER[2:], "0x" + "0" * 24 + SPENDER[2:]],
        "data": "0x" + format(amount, "064x"),
        "logIndex": "0x0",
    }


def test_unlimited_and_zero_approvals() -> None:
    for value, expected in [(2**256 - 1, True), (0, False), (10**18, False)]:
        movements, approvals, evidence, coverage = decode_events([approval_log(value)], HASH)
        assert not movements
        assert approvals[0].unlimited is expected
        assert approvals[0].amount_raw == str(value)
        assert approvals[0].spender == SPENDER
        assert approvals[0].evidence_ids == (evidence[0].id,)
        assert coverage.status == "available"
        with pytest.raises(ValidationError):
            approvals[0].amount_raw = "1"  # type: ignore[misc]


def test_nft_transfer_is_not_fungible_amount() -> None:
    log = approval_log(9)
    log["topics"] = [
        TRANSFER,
        "0x" + "0" * 24 + OWNER[2:],
        "0x" + "0" * 24 + SPENDER[2:],
        "0x" + format(9, "064x"),
    ]
    log["data"] = "0x"
    movements, _, _, _ = decode_events([log], HASH)
    assert movements[0].standard == "ERC721"
    assert movements[0].amount_raw == "1"
    assert movements[0].token_id == "9"


def test_malformed_events_remain_raw_evidence() -> None:
    log = approval_log(1)
    log["data"] = "0x01"
    _, approvals, evidence, coverage = decode_events([log], HASH)
    assert not approvals
    assert evidence[0].data()["data"] == "0x01"
    assert coverage.status == "partial"


@pytest.mark.parametrize("chain", ["ethereum", "monad"])
def test_recorded_chain_data_and_reverted_movement(chain: str) -> None:
    raw = RawTransaction.model_validate_json(Path(f"evals/cases/{chain}-recorded.json").read_text())
    result = decode_transaction(raw)
    assert result.transaction.hash == raw.tx_hash
    assert int(result.transaction.gas_fee_wei) == (
        result.transaction.gas_used * int(result.transaction.gas_price_wei)
    )
    receipt = json.loads(raw.receipt_json)
    receipt["status"] = "0x0"
    failed = decode_transaction(raw.model_copy(update={"receipt_json": json.dumps(receipt)}))
    assert not failed.approvals and not failed.movements
