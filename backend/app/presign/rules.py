"""Deterministic pre-sign verdict rules.

Each rule reads facts gathered by code (decoded payload, chain reads, spender tools)
and, when it fires, adds a reason with a severity and the claim IDs behind it. The
verdict is the most severe reason. A model never takes part: missing facts make a rule
fire as "could not verify", they never let a payload through.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from app.agents.catalog import short
from app.agents.tools import NFT_MARKETPLACES
from app.blockchain.event_decoder import is_unlimited
from app.models.base import FrozenModel
from app.presign.intents import Decoded, Intent, unlimited
from app.presign.reads import State

Severity = Literal["allow", "warn", "block"]
RANK: dict[Severity, int] = {"allow": 0, "warn": 1, "block": 2}
LONG_LIVED_SECONDS = 30 * 24 * 3600
MAX_REASONS = 10


class Reason(FrozenModel):
    rule: str
    severity: Severity
    text: str
    permission_id: str | None = None
    claim_ids: tuple[str, ...] = ()


@dataclass
class Facts:
    """Everything the rules may look at for one intent."""

    pid: str
    intent: Intent
    state: State | None = None
    # Facts reported by the spender tools: kind, proxy, control, known.
    spender: dict[str, Any] = field(default_factory=dict)
    failed_tools: list[str] = field(default_factory=list)

    @property
    def effective_amount(self) -> int | None:
        """The allowance the spender would hold after signing."""
        amount = int(self.intent.amount_raw) if self.intent.amount_raw is not None else None
        if self.intent.mode != "increase" or amount is None:
            return amount
        if self.state is None or self.state.allowance is None:
            return None
        return self.state.allowance + amount

    @property
    def effective_unlimited(self) -> bool | None:
        if self.intent.kind == "nft_operator":
            return True
        amount = self.effective_amount
        if amount is None:
            return None
        bits = 160 if self.intent.target != self.intent.token else 256
        return unlimited(amount, bits) or is_unlimited(amount)


def verdict(reasons: list[Reason]) -> Severity:
    return max((r.severity for r in reasons), key=RANK.__getitem__, default="allow")


def payload_reasons(decoded: Decoded, chain_id: int) -> list[Reason]:
    reasons: list[Reason] = []
    if decoded.status == "unrecognised":
        reasons.append(
            Reason(
                rule="UNRECOGNISED_PAYLOAD",
                severity="warn",
                text=f"Could not verify: {decoded.note}",
                claim_ids=("input",),
            )
        )
    elif decoded.status == "no_approval":
        reasons.append(
            Reason(
                rule="NOT_AN_APPROVAL",
                severity="allow",
                text=f"{decoded.note} Only token permissions are checked; this is not a "
                "simulation of everything the payload does.",
                claim_ids=("input",),
            )
        )
    if decoded.domain_chain_id is not None and decoded.domain_chain_id != chain_id:
        reasons.append(
            Reason(
                rule="WRONG_CHAIN",
                severity="block",
                text=f"The signature is for chain {decoded.domain_chain_id}, but the check "
                f"was asked about chain {chain_id}. Signing for a chain you did not intend "
                "is a common phishing pattern.",
                claim_ids=("input",),
            )
        )
    if decoded.partial:
        reasons.append(
            Reason(
                rule="UNRECOGNISED_PAYLOAD",
                severity="warn",
                text=f"Could not verify part of the batch: {decoded.note}",
                claim_ids=("input",),
            )
        )
    if decoded.truncated:
        reasons.append(
            Reason(
                rule="COULD_NOT_VERIFY",
                severity="warn",
                text="Could not verify: the payload grants more permissions than are checked.",
                claim_ids=("input",),
            )
        )
    return reasons


def intent_reasons(facts: Facts, claims: set[str], block_timestamp: int | None) -> list[Reason]:
    pid, intent, state = facts.pid, facts.intent, facts.state
    spender = short(intent.spender)

    def cite(*suffixes: str) -> tuple[str, ...]:
        ids = [pid] + [f"{pid}:{s}" for s in suffixes]
        return tuple(i for i in ids if i in claims)

    def reason(rule: str, severity: Severity, text: str, *suffixes: str) -> Reason:
        return Reason(
            rule=rule,
            severity=severity,
            text=text,
            permission_id=pid,
            claim_ids=cite(*suffixes),
        )

    if not intent.grants:
        return [
            reason(
                "REDUCES_EXPOSURE",
                "allow",
                f"This lowers or removes {spender}'s permission; it grants nothing new.",
            )
        ]
    reasons: list[Reason] = []
    gaps: list[str] = []
    if state is None:
        gaps.append("chain state")
    else:
        if state.target_has_code is False:
            gaps.append(f"target {short(intent.target)} has no contract code")
        gaps += state.unverified
    if intent.mode == "increase" and facts.effective_amount is None:
        gaps.append("the current allowance, so the new total is unknown")
    if "spender_profile" in facts.failed_tools or "kind" not in facts.spender:
        gaps.append("the spender's code")
    if gaps:
        reasons.append(
            reason(
                "COULD_NOT_VERIFY",
                "warn",
                "Could not verify " + "; ".join(dict.fromkeys(gaps)) + ".",
                "target",
            )
        )

    kind = facts.spender.get("kind")
    known = facts.spender.get("known")
    proxy = bool(facts.spender.get("proxy"))
    control = facts.spender.get("control")
    wide = facts.effective_unlimited
    if kind in ("eoa", "delegated"):
        reasons.append(
            reason(
                "SPENDER_IS_KEY",
                "block",
                f"Spender {spender} is controlled by a private key, not fixed contract code: "
                "whoever holds that key could move the tokens at any time.",
                "spender",
            )
        )
    if (
        intent.kind == "nft_operator"
        and kind is not None
        and intent.spender not in NFT_MARKETPLACES
    ):
        reasons.append(
            reason(
                "NFT_OPERATOR_UNKNOWN",
                "block",
                f"This hands {spender} every NFT in the collection, now and later, and it is "
                "not a recognised marketplace contract.",
                "spender",
                "known",
            )
        )
    if proxy and wide and control == "single_key":
        reasons.append(
            reason(
                "UNLIMITED_TO_SINGLE_KEY_PROXY",
                "block",
                f"An unlimited grant to {spender}, an upgradeable proxy whose upgrades one key "
                "controls: that key could swap in new logic and take everything approved.",
                "control",
                "spender",
            )
        )
    elif proxy and control != "contract":
        reasons.append(
            reason(
                "UPGRADEABLE_SPENDER",
                "warn",
                f"Spender {spender} is upgradeable and its upgrade authority is "
                + ("a single key." if control == "single_key" else "not determined."),
                "control",
                "spender",
            )
        )
    if intent.kind != "nft_operator" and kind is not None and not known:
        reasons.append(
            reason(
                "UNKNOWN_SPENDER",
                "warn",
                f"Spender {spender} is not a recognised protocol contract. Confirm it is the "
                "contract you meant to use.",
                "known",
            )
        )
    if intent.kind != "nft_operator" and wide:
        reasons.append(
            reason(
                "UNLIMITED_AMOUNT",
                "warn",
                f"The grant to {spender} is unlimited. A finite amount covers a single trade.",
                "reach",
                "known",
            )
        )
    if (
        intent.kind in ("permit2_approve", "permit2_permit")
        and intent.expiration
        and block_timestamp is not None
        and intent.expiration - block_timestamp > LONG_LIVED_SECONDS
    ):
        reasons.append(
            reason(
                "LONG_LIVED",
                "warn",
                f"The Permit2 grant to {spender} stays valid for more than 30 days.",
            )
        )
    return reasons


def evaluate(
    decoded: Decoded,
    chain_id: int,
    items: list[Facts],
    claims: set[str],
    block_timestamp: int | None,
) -> tuple[Severity, list[Reason]]:
    reasons = payload_reasons(decoded, chain_id)
    for facts in items:
        reasons += intent_reasons(facts, claims, block_timestamp)
    # Most severe first; then keep the order the rules were written in.
    ordered = sorted(reasons, key=lambda r: -RANK[r.severity])[:MAX_REASONS]
    return verdict(reasons), ordered
