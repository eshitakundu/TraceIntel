"""The evidence catalog: every sentence a model may select, written by code.

Models never author facts. They choose claim IDs from this catalog, and the code expands
those IDs back into claims. Each claim cites the evidence it was derived from.
"""

import re
from dataclasses import dataclass, field

from app.blockchain.event_decoder import is_unlimited
from app.blockchain.ownership import ROLE_ORDER
from app.models.blockchain import Contract, Coverage, DecodedEvidence
from app.models.exposure import ExposureAnalysis, PersistentExposure
from app.models.interpretation import CitedClaim
from app.models.risk import RiskAssessment

MAX_TARGETS = 12
MAX_GAPS = 6
SAFE_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*")


def short(address: str) -> str:
    return address[:6] + "…" + address[-4:] if len(address) > 12 else address


def amount(raw: str, decimals: int | None, unlimited: bool = False) -> str:
    if unlimited:
        return "unlimited"
    value = int(raw)
    if decimals is None:
        return f"{value:,} raw units"
    whole, fraction = divmod(value, 10**decimals)
    if whole >= 10**15:
        return f"≈{value / 10**decimals:.3e}"
    digits = str(fraction).rjust(decimals, "0") if decimals else ""
    shown = digits[:6].rstrip("0")
    if not whole and not shown and fraction:
        return "less than 0.000001"
    prefix = "≈" if digits[6:].strip("0") else ""
    return prefix + f"{whole:,}" + (f".{shown}" if shown else "")


def safe_label(value: str | None, limit: int = 16) -> str | None:
    """Token symbols and contract names are attacker-chosen strings. Only short,
    plain identifiers may reach model input; anything else falls back to an address."""
    if value and len(value) <= limit and SAFE_LABEL.fullmatch(value):
        return value
    return None


def is_live(permission: PersistentExposure) -> bool:
    return permission.permission_active is True


@dataclass
class Catalog:
    claims: list[CitedClaim] = field(default_factory=list)
    targets: dict[str, PersistentExposure] = field(default_factory=dict)

    def add(self, claim: CitedClaim) -> None:
        if all(existing.id != claim.id for existing in self.claims):
            self.claims.append(claim)

    def by_id(self) -> dict[str, CitedClaim]:
        return {claim.id: claim for claim in self.claims}

    def live_targets(self) -> tuple[str, ...]:
        return tuple(pid for pid, p in self.targets.items() if is_live(p))

    def actionable_targets(self) -> tuple[str, ...]:
        """Live permissions the sender can revoke: their own, or the called contract's
        (which may be their smart wallet). Other contracts' approvals are not theirs."""
        return tuple(
            pid
            for pid in self.live_targets()
            if self.targets[pid].historical.owner_role in ("sender", "called_contract", None)
        )


def granter(permission: PersistentExposure) -> str:
    owner = permission.historical.owner
    return {
        "sender": "the sender",
        "called_contract": f"the called contract {short(owner)}",
        "other": f"contract {short(owner)}",
    }.get(permission.historical.owner_role or "", short(owner))


def token_label(permission: PersistentExposure) -> str:
    return safe_label(permission.current.symbol) or short(permission.historical.token)


def distinct_permissions(exposure: ExposureAnalysis) -> list[PersistentExposure]:
    """The latest event per token/owner/spender, the sender's live permissions first."""
    latest: dict[tuple[str, str, str], PersistentExposure] = {}
    for permission in exposure.permissions:
        h = permission.historical
        latest[(h.token, h.owner, h.spender)] = permission
    liveness = {True: 0, None: 1, False: 2}
    return sorted(
        latest.values(),
        key=lambda p: (
            ROLE_ORDER[p.historical.owner_role],
            liveness[p.permission_active],
            not p.historical.unlimited,
        ),
    )


def permission_claims(pid: str, permission: PersistentExposure) -> list[CitedClaim]:
    h, c = permission.historical, permission.current
    label = token_label(permission)
    state = {
        "ACTIVE": "is still active, unchanged since the transaction",
        "PARTIALLY_ACTIVE": "is still active at a reduced amount",
        "REVOKED": "is inactive (the allowance is zero now)",
        "UNKNOWN": "could not be checked (current allowance unavailable)",
        "SUPERSEDED": "was replaced by a different allowance"
        + (" that is still active" if is_live(permission) else ""),
    }[permission.status]
    then = amount(h.allowance_raw, c.decimals, h.unlimited)
    now = (
        "unknown"
        if c.allowance_raw is None
        else amount(c.allowance_raw, c.decimals, is_unlimited(int(c.allowance_raw)))
    )
    claims = [
        CitedClaim(
            id=pid,
            text=f"{label} allowance from {granter(permission)} to spender "
            f"{short(h.spender)} {state}. Approved: {then}; now: {now}.",
            evidence_ids=permission.evidence_ids,
        )
    ]
    if is_live(permission) and c.balance_raw is not None and c.allowance_raw is not None:
        balance = int(c.balance_raw)
        reachable = min(balance, int(c.allowance_raw))
        holder = granter(permission)
        text = (
            f"{holder[0].upper() + holder[1:]} holds {amount(c.balance_raw, c.decimals)} {label} "
            f"now, so {short(h.spender)} could move up to "
            f"{amount(str(reachable), c.decimals)} {label} at the checked block."
            if balance
            else f"{holder[0].upper() + holder[1:]} holds no {label} now, so nothing is "
            f"spendable today, but any {label} received later would be."
        )
        claims.append(CitedClaim(id=f"{pid}:reach", text=text, evidence_ids=c.evidence_ids))
    return claims


def contract_claim(index: int, contract: Contract) -> CitedClaim | None:
    address = short(contract.address)
    if contract.kind == "unknown":
        return None
    if contract.kind == "no_code":
        text = f"{address} has no contract code (an externally owned account)."
    elif contract.kind == "delegated_eoa":
        text = (
            f"{address} is an EIP-7702 delegated account running code from "
            f"{short(contract.implementation or '')}."
        )
    else:
        parts = [f"{address} is a contract"]
        if contract.proxy in ("eip1967", "beacon"):
            parts.append(f"an upgradeable {contract.proxy} proxy")
        if contract.verification == "verified":
            parts.append(f"with verified source ({safe_label(contract.name, 40) or 'unnamed'})")
        elif contract.verification == "unverified":
            parts.append("with unverified source")
        text = ", ".join(parts) + "."
    if contract.state == "current":
        text += " Read at the latest block; the provider no longer serves the transaction block."
    return CitedClaim(id=f"c{index}", text=text, evidence_ids=contract.evidence_ids)


def build_catalog(
    decoded: DecodedEvidence,
    risk: RiskAssessment,
    contracts: tuple[Contract, ...],
    coverage: tuple[Coverage, ...],
    exposure: ExposureAnalysis | None = None,
) -> Catalog:
    tx = decoded.transaction
    catalog = Catalog()
    catalog.add(
        CitedClaim(
            id="tx:status",
            text=f"The transaction {'succeeded' if tx.status == 'success' else 'failed'} in "
            f"block {tx.block_number:,}; sent by {short(tx.sender)}"
            + (f" to {short(tx.recipient)}." if tx.recipient else " to create a contract."),
            evidence_ids=tx.evidence_ids,
        )
    )
    roles = [a.owner_role for a in decoded.approvals]
    if roles:
        catalog.add(
            CitedClaim(
                id="tx:approvals",
                text=f"It emitted {len(roles)} approval event(s): "
                f"{roles.count('sender')} granted by the sender, "
                f"{roles.count('called_contract')} by the called contract and "
                f"{roles.count('other')} by other contracts.",
                evidence_ids=tuple(
                    dict.fromkeys(e for a in decoded.approvals for e in a.evidence_ids)
                )[:6],
            )
        )
    signals: dict[str, list[str]] = {}
    texts: dict[str, str] = {}
    for signal in risk.signals:
        if signal.code == "EXECUTION_STATUS":
            continue
        signals.setdefault(signal.code, []).extend(signal.evidence_ids)
        texts[signal.code] = f"{signal.title}: {signal.description}"
    for code, evidence in signals.items():
        catalog.add(
            CitedClaim(
                id=f"risk:{code.lower()}",
                text=texts[code],
                evidence_ids=tuple(dict.fromkeys(evidence))[:6],
            )
        )
    if exposure:
        for index, permission in enumerate(distinct_permissions(exposure)[:MAX_TARGETS]):
            pid = f"p{index}"
            catalog.targets[pid] = permission
            for claim in permission_claims(pid, permission):
                catalog.add(claim)
    for index, contract in enumerate(contracts):
        described = contract_claim(index, contract)
        if described:
            catalog.add(described)
    reasons: set[str] = set()
    for item in coverage:
        if item.status in ("partial", "unavailable") and item.reason not in reasons:
            reasons.add(item.reason)
            # Coverage is a pipeline observation, not blockchain evidence.
            catalog.add(
                CitedClaim(
                    id=f"gap:{len(reasons) - 1}",
                    text=f"{item.area.split(':')[0]}: {item.reason}",
                    evidence_ids=(),
                )
            )
            if len(reasons) == MAX_GAPS:
                break
    return catalog
