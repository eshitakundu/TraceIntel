import json

from app.blockchain.calldata import decode_calldata
from app.blockchain.event_decoder import decode_events
from app.models.blockchain import (
    Coverage,
    DecodedEvidence,
    Evidence,
    Movement,
    RawTransaction,
    Transaction,
)


def decode_transaction(raw: RawTransaction) -> DecodedEvidence:
    tx, receipt, block = (
        json.loads(raw.transaction_json),
        json.loads(raw.receipt_json),
        json.loads(raw.block_json),
    )
    prefix = f"{raw.chain}:{raw.tx_hash}"
    status = int(receipt["status"], 16)
    if status not in (0, 1):
        raise ValueError("Invalid receipt status")
    gas_used = int(receipt["gasUsed"], 16)
    gas_price = int(receipt["effectiveGasPrice"], 16)
    calldata = tx.get("input", "0x")
    target = tx.get("to")
    created = receipt.get("contractAddress")
    signature, arguments = decode_calldata(calldata) if target else (None, None)
    transaction = Transaction(
        hash=raw.tx_hash,
        sender=tx["from"].lower(),
        recipient=target.lower() if target else None,
        created_contract=created.lower() if created else None,
        nonce=int(tx["nonce"], 16),
        value_wei=str(int(tx["value"], 16)),
        gas_used=gas_used,
        gas_price_wei=str(gas_price),
        gas_fee_wei=str(gas_used * gas_price),
        status="success" if status else "failed",
        block_number=int(receipt["blockNumber"], 16),
        block_hash=receipt["blockHash"],
        timestamp=int(block["timestamp"], 16),
        selector=calldata[:10] if len(calldata) >= 10 else None,
        function=signature,
        arguments_json=arguments,
        calldata=calldata,
        evidence_ids=(f"{prefix}:tx", f"{prefix}:receipt", f"{prefix}:block"),
    )
    evidence = (
        Evidence(
            id=f"{prefix}:tx",
            source="eth_getTransactionByHash",
            description="Transaction envelope",
            data_json=raw.transaction_json,
        ),
        Evidence(
            id=f"{prefix}:receipt",
            source="eth_getTransactionReceipt",
            description="Execution receipt",
            data_json=raw.receipt_json,
        ),
        Evidence(
            id=f"{prefix}:block",
            source="eth_getBlockByNumber",
            description="Canonical block at acquisition",
            data_json=raw.block_json,
        ),
    )
    movements, approvals, logs, coverage = decode_events(receipt["logs"] if status else [], prefix)
    if status and int(tx["value"], 16) and (target or created):
        movements = (
            Movement(
                standard="native",
                token="native",
                sender=tx["from"].lower(),
                recipient=(target or created).lower(),
                amount_raw=transaction.value_wei,
                decimals=18,
                evidence_ids=(f"{prefix}:tx", f"{prefix}:receipt"),
            ),
        ) + movements
    return DecodedEvidence(
        transaction=transaction,
        movements=movements,
        approvals=approvals,
        evidence=evidence + logs,
        coverage=(
            coverage,
            Coverage(
                area="calldata",
                status="partial" if calldata != "0x" else "not_applicable",
                reason="Known selectors are candidates, not verified ABI identities. "
                "Unknown calldata is preserved without guessing.",
            ),
            Coverage(
                area="token_metadata",
                status="unavailable",
                reason="Raw integer quantities retained until decimals/symbols can be verified.",
            ),
        ),
    )
