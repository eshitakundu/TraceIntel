from app.models.blockchain import Approval, Contract, DecodedEvidence
from app.models.risk import RiskAssessment, RiskSignal
from app.risk.scoring import aggregate

ZERO_ADDRESS = "0x" + "0" * 40


def grants_permission(approval: Approval) -> bool:
    """Whether an approval event leaves a live permission behind."""
    if approval.standard == "ERC20":
        return int(approval.amount_raw) > 0
    if approval.standard == "ERC721":
        # Approval(owner, approved, tokenId): the zero address clears the token's approval.
        return approval.spender != ZERO_ADDRESS
    return approval.unlimited


def evaluate(decoded: DecodedEvidence, contracts: tuple[Contract, ...]) -> RiskAssessment:
    signals: list[RiskSignal] = []
    granted_elsewhere: list[Approval] = []
    for approval in decoded.approvals:
        # Only the sender's own approvals describe the sender's exposure. Approvals owned
        # by the called contract or other contracts are reported, but not scored.
        if approval.owner_role not in (None, "sender"):
            if grants_permission(approval):
                granted_elsewhere.append(approval)
            continue
        if approval.standard == "ERC20" and approval.unlimited:
            signals.append(
                RiskSignal(
                    code="UNLIMITED_TOKEN_APPROVAL",
                    severity="high",
                    score=30,
                    title="Unlimited token allowance",
                    description="Spender may use the full token balance.",
                    reason="Sender's ERC20-pattern Approval uses an unlimited sentinel amount.",
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
                    reason="Sender's ApprovalForAll emitted approved=true.",
                    source="receipt.logs",
                    evidence_ids=approval.evidence_ids,
                )
            )
        elif approval.standard == "ERC20" and grants_permission(approval):
            signals.append(
                RiskSignal(
                    code="TOKEN_APPROVAL",
                    severity="low",
                    score=10,
                    title="Token spending permission",
                    description="A positive token allowance was emitted.",
                    reason="Sender's ERC20-pattern Approval amount is positive and finite.",
                    source="receipt.logs",
                    evidence_ids=approval.evidence_ids,
                )
            )
        if grants_permission(approval):
            spender = next((c for c in contracts if c.address == approval.spender), None)
            if spender and spender.kind == "contract":
                signals.append(
                    RiskSignal(
                        code="CONTRACT_SPENDER",
                        severity="medium",
                        score=10,
                        title="Permission granted to contract",
                        description="Review the spender's behavior.",
                        reason="Sender granted a permission; spender has contract bytecode.",
                        source="receipt.logs + eth_getCode",
                        evidence_ids=approval.evidence_ids + spender.evidence_ids[:1],
                    )
                )
    if granted_elsewhere:
        signals.append(
            RiskSignal(
                code="APPROVAL_BY_OTHER_OWNER",
                severity="info",
                score=0,
                title="Approvals granted by other addresses",
                description=f"{len(granted_elsewhere)} approval event(s) belong to the called "
                "contract or other contracts, not the sender.",
                reason="Approval owner differs from the transaction sender; reported separately.",
                source="receipt.logs",
                evidence_ids=tuple(
                    dict.fromkeys(e for a in granted_elsewhere for e in a.evidence_ids)
                ),
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
