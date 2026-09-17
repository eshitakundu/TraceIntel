from app.models.blockchain import Contract, Coverage, DecodedEvidence
from app.models.interpretation import CitedClaim
from app.models.risk import RiskAssessment


def build_catalog(
    decoded: DecodedEvidence,
    risk: RiskAssessment,
    contracts: tuple[Contract, ...],
    coverage: tuple[Coverage, ...],
) -> tuple[CitedClaim, ...]:
    tx = decoded.transaction
    claims = [
        CitedClaim(
            id="tx:status",
            text=f"Transaction {tx.status} in block {tx.block_number}.",
            evidence_ids=tx.evidence_ids,
        ),
        CitedClaim(
            id="tx:fee",
            text=f"Execution gas cost: {tx.gas_fee_wei} wei.",
            evidence_ids=tx.evidence_ids,
        ),
    ]
    for index, signal in enumerate(risk.signals):
        claims.append(
            CitedClaim(
                id=f"risk:{index}",
                text=f"{signal.title}. {signal.description}",
                evidence_ids=signal.evidence_ids,
            )
        )
    for index, contract in enumerate(contracts):
        if contract.evidence_ids:
            claims.append(
                CitedClaim(
                    id=f"contract:{index}",
                    text=f"{contract.address}: {contract.kind}; source {contract.verification}; "
                    f"proxy {contract.proxy}.",
                    evidence_ids=contract.evidence_ids,
                )
            )
    for index, item in enumerate(coverage):
        if item.status in ("partial", "unavailable"):
            # Coverage is a pipeline observation rather than a blockchain fact.
            claims.append(
                CitedClaim(
                    id=f"limitation:{index}", text=f"{item.area}: {item.reason}", evidence_ids=()
                )
            )
    return tuple(claims)
