import json
from pathlib import Path

from app.agents.validation import validate_selection
from app.blockchain.decoder import decode_transaction
from app.blockchain.event_decoder import APPROVAL
from app.models.blockchain import RawTransaction
from app.models.interpretation import AgentSelection, CitedClaim
from app.risk.engine import evaluate


def run_cases() -> list[dict[str, object]]:
    cases = json.loads(Path("evals/cases/synthetic-approvals.json").read_text())
    results: list[dict[str, object]] = []
    for index, case in enumerate(cases):
        tx_hash = "0x" + format(index + 1, "064x")
        block_hash = "0x" + "b" * 64
        owner, spender, token = ("0x" + char * 40 for char in ("1", "2", "3"))
        log = {
            "address": token,
            "topics": [APPROVAL, "0x" + "0" * 24 + owner[2:], "0x" + "0" * 24 + spender[2:]],
            "logIndex": "0x0",
            "data": "0x" + format(int(case["amount"]), "064x"),
        }
        tx = {"from": owner, "to": token, "nonce": "0x0", "value": "0x0", "input": "0x"}
        receipt = {
            "status": case["status"],
            "gasUsed": "0x5208",
            "effectiveGasPrice": "0x1",
            "blockNumber": "0x1",
            "blockHash": block_hash,
            "logs": [log],
        }
        raw = RawTransaction(
            chain="synthetic",
            tx_hash=tx_hash,
            transaction_json=json.dumps(tx),
            receipt_json=json.dumps(receipt),
            block_json=json.dumps({"timestamp": "0x1"}),
        )
        decoded = decode_transaction(raw)
        risk = evaluate(decoded, ())
        codes = sorted(s.code for s in risk.signals if s.score)
        expected = case["expected"]
        ids = {e.id for e in decoded.evidence}
        references_valid = all(set(s.evidence_ids) <= ids for s in risk.signals)
        passed = (
            risk.score == expected["score"]
            and codes == expected["codes"]
            and len(decoded.approvals) == expected["approvals"]
            and references_valid
        )
        results.append(
            {
                "case": case["name"],
                "passed": passed,
                "score": risk.score,
                "codes": codes,
                "evidence_references_valid": references_valid,
            }
        )
    recorded = RawTransaction.model_validate_json(
        Path("evals/cases/ethereum-approval.json").read_text()
    )
    decoded = decode_transaction(recorded)
    risk = evaluate(decoded, ())
    codes = sorted({signal.code for signal in risk.signals if signal.score})
    passed = (
        len(decoded.approvals) == 13
        and sum(a.unlimited for a in decoded.approvals) == 2
        and risk.score == 40
        and codes == ["TOKEN_APPROVAL", "UNLIMITED_TOKEN_APPROVAL"]
    )
    results.append(
        {
            "case": "recorded Ethereum approval activity",
            "passed": passed,
            "approvals": len(decoded.approvals),
            "score": risk.score,
            "codes": codes,
        }
    )
    claim = CitedClaim(id="known", text="Transaction success.", evidence_ids=("receipt:1",))
    valid = AgentSelection(
        summary=(claim,),
        important_findings=(),
        uncertainties=(),
        recommended_checks=(),
        confidence=0.5,
    )
    accepted = validate_selection(valid, (claim,)) == valid
    rejected = 0
    for field, value in (
        ("text", "Transaction is safe."),
        ("id", "invented"),
        ("evidence_ids", ("invented",)),
    ):
        altered = valid.model_copy(update={"summary": (claim.model_copy(update={field: value}),)})
        try:
            validate_selection(altered, (claim,))
        except ValueError:
            rejected += 1
    results.append(
        {
            "case": "agent grounding adversarial cases",
            "passed": accepted and rejected == 3,
            "valid_claim_accepted": accepted,
            "unsupported_outputs_rejected": rejected,
        }
    )
    return results


def main() -> None:
    results = run_cases()
    print(json.dumps(results, indent=2))
    if not all(result["passed"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
