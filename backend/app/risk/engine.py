from app.models.blockchain import Contract, DecodedEvidence
from app.models.risk import RiskAssessment, RiskSignal
from app.risk.scoring import aggregate


def evaluate(decoded: DecodedEvidence, contracts: tuple[Contract, ...]) -> RiskAssessment:
    signals: list[RiskSignal] = []
    for approval in decoded.approvals:
        if approval.standard == "ERC20" and approval.unlimited:
            signals.append(
                RiskSignal(
                    code="UNLIMITED_TOKEN_APPROVAL",
                    severity="high",
                    score=30,
                    title="Unlimited token allowance",
                    description="Spender may use the full token balance.",
                    reason="ERC20-pattern Approval emitted with uint256 maximum.",
                    source="receipt.logs",
                    evidence_ids=approval.evidence_ids,
                )
            )
        elif approval.standard == "operator" and approval.unlimited:
            signals.append(
                RiskSignal(
                    code="NFT_OPERATOR_APPROVAL",
                    severity="high",
                    score=30,
                    title="Collection-wide operator permission",
                    description="Operator permission applies across the emitting collection.",
                    reason="ApprovalForAll emitted approved=true.",
                    source="receipt.logs",
                    evidence_ids=approval.evidence_ids,
                )
            )
        elif approval.standard == "ERC20" and int(approval.amount_raw) > 0:
            signals.append(
                RiskSignal(
                    code="TOKEN_APPROVAL",
                    severity="low",
                    score=10,
                    title="Token spending permission",
                    description="A positive token allowance was emitted.",
                    reason="ERC20-pattern Approval amount is positive and below uint256 maximum.",
                    source="receipt.logs",
                    evidence_ids=approval.evidence_ids,
                )
            )
        if int(approval.amount_raw) > 0:
            spender = next((c for c in contracts if c.address == approval.spender), None)
            if spender and spender.kind == "contract":
                signals.append(
                    RiskSignal(
                        code="CONTRACT_SPENDER",
                        severity="medium",
                        score=10,
                        title="Permission granted to contract",
                        description="Review the spender's behavior.",
                        reason="Positive approval; spender has bytecode at block end.",
                        source="receipt.logs + eth_getCode",
                        evidence_ids=approval.evidence_ids + spender.evidence_ids[:1],
                    )
                )
    target = decoded.transaction.recipient or decoded.transaction.created_contract
    for contract in contracts:
        if contract.address == target and contract.verification == "unverified":
            signals.append(
                RiskSignal(
                    code="UNVERIFIED_TARGET",
                    severity="medium",
                    score=12,
                    title="Target source is unverified",
                    description="Explorer reports no verified source; not proof of malice.",
                    reason="Successful explorer response contains no source code.",
                    source="explorer",
                    evidence_ids=tuple(e for e in contract.evidence_ids if e.endswith(":explorer")),
                )
            )
        if contract.proxy in ("eip1967", "beacon"):
            signals.append(
                RiskSignal(
                    code="PROXY_DETECTED",
                    severity="info",
                    score=0,
                    title="Proxy architecture detected",
                    description="Proxy usage alone is not malicious.",
                    reason="Nonzero standard implementation or beacon slot.",
                    source="eth_getStorageAt",
                    evidence_ids=tuple(e for e in contract.evidence_ids if e.endswith(":proxy")),
                )
            )
    signals.append(
        RiskSignal(
            code="EXECUTION_STATUS",
            severity="info",
            score=0,
            title=f"Transaction {decoded.transaction.status}",
            description="Receipt status describes execution, not safety.",
            reason=f"Receipt status is {decoded.transaction.status}.",
            source="eth_getTransactionReceipt",
            evidence_ids=(decoded.transaction.evidence_ids[1],),
        )
    )
    return aggregate(tuple(signals))
