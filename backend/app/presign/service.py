"""Pre-sign check: decode → read at one pinned block → spender tools → rules → report.

The verdict comes from rules.py. The optional explanation (explain.py) can only select
claims this module wrote, and cannot change the verdict.
"""

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Any, Literal

from app.agents.catalog import Catalog, amount, safe_label, short
from app.agents.tools import TOOLS, ToolContext, ToolResult
from app.blockchain.chains import Chain
from app.blockchain.rpc_client import RpcClient, RpcError
from app.models.base import FrozenModel
from app.models.blockchain import Evidence
from app.models.exposure import CurrentPermissionState, HistoricalPermission, PersistentExposure
from app.models.interpretation import CitedClaim, ReportDraft, ToolName
from app.presign.intents import Decoded, Intent, unlimited
from app.presign.reads import State, read_state
from app.presign.rules import Facts, Reason, Severity, evaluate

CHECK_TIMEOUT = 20


class BlockRef(FrozenModel):
    number: int
    hash: str
    timestamp: int


class CheckStep(FrozenModel):
    name: str
    permission_id: str
    status: Literal["ok", "error"]
    duration_ms: int


class Explanation(FrozenModel):
    author: Literal["model", "baseline"]
    model: str | None = None
    summary: tuple[CitedClaim, ...]
    findings: tuple[CitedClaim, ...] = ()
    uncertainties: tuple[CitedClaim, ...] = ()
    reason: str | None = None


class PresignReport(FrozenModel):
    verdict: Severity
    headline: str
    chain: str
    source: Literal["transaction", "signature"]
    function: str | None
    intents: tuple[Intent, ...]
    reasons: tuple[Reason, ...]
    claims: tuple[CitedClaim, ...]
    evidence: tuple[Evidence, ...]
    coverage_gaps: tuple[str, ...]
    block: BlockRef | None
    checks: tuple[CheckStep, ...]
    explanation: Explanation | None = None
    duration_ms: int
    note: str = "Read-only check. Nothing was signed or sent."

    def to_json(self) -> dict[str, Any]:
        """JSON for agents: evidence data as objects rather than encoded strings."""
        data = self.model_dump(mode="json")
        data["evidence"] = [
            {"id": e.id, "source": e.source, "description": e.description, "data": e.data()}
            for e in self.evidence
        ]
        return data


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _date(timestamp: int | None) -> str:
    if not timestamp:
        return "no expiry set"
    if timestamp >= 2**47:
        return "never"
    try:
        return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return "never"


def intent_claims(facts: Facts, input_id: str, state_id: str | None) -> list[CitedClaim]:
    """Sentences about one intent, written by code. Token labels pass the same filter as
    the main app, so attacker-chosen names never reach a model."""
    pid, intent, state = facts.pid, facts.intent, facts.state or State()
    label = safe_label(state.symbol) or f"token {short(intent.token)}"
    owner, spender = short(intent.owner), short(intent.spender)
    cited = (input_id, state_id) if state_id else (input_id,)

    def amt(raw: int | None, wide: bool | None = False) -> str:
        if raw is None:
            return "an unknown amount"
        return f"{amount(str(raw), state.decimals, bool(wide))} {label}"

    granted = amt(
        int(intent.amount_raw) if intent.amount_raw is not None else None,
        intent.unlimited,
    )
    bits = 160 if intent.target != intent.token else 256
    now = (
        f" (now: {amt(state.allowance, unlimited(state.allowance, bits))})"
        if state.allowance is not None
        else ""
    )
    text = {
        "erc20_approve": f"This transaction would set {owner}'s allowance for spender {spender} "
        f"to {granted}{now}.",
        "erc20_increase": f"This transaction would raise {owner}'s allowance for spender "
        f"{spender} by {granted}{now}; the new total would be "
        f"{amt(facts.effective_amount, facts.effective_unlimited)}.",
        "erc20_decrease": f"This transaction would lower {owner}'s allowance for spender "
        f"{spender} by {granted}{now}.",
        "erc20_permit": f"Signing this would let spender {spender} use up to {granted} of "
        f"{owner}'s balance without a transaction from {owner}; the signature can be used until "
        f"{_date(intent.expiration)}.",
        "permit2_approve": f"This transaction would let spender {spender} move up to {granted} "
        f"from {owner} through Permit2, until {_date(intent.expiration)}.",
        "permit2_permit": f"Signing this would let spender {spender} move up to {granted} from "
        f"{owner} through Permit2, until {_date(intent.expiration)}.",
        "permit2_transfer": f"Signing this would let spender {spender} pull up to {granted} "
        f"from {owner} once, until {_date(intent.expiration)}.",
        "nft_operator": (
            f"This transaction would let operator {spender} transfer every NFT {owner} holds "
            f"in collection {short(intent.token)}, now and in future."
            if intent.grants
            else f"This transaction would remove operator {spender}'s access to {owner}'s NFTs "
            f"in collection {short(intent.token)}."
        ),
    }[intent.kind]
    claims = [CitedClaim(id=pid, text=text, evidence_ids=cited)]
    if not state_id:
        return claims
    if state.target_has_code is False:
        claims.append(
            CitedClaim(
                id=f"{pid}:target",
                text=f"{short(intent.target)} has no contract code, so it is not a token, "
                "NFT collection or Permit2 contract.",
                evidence_ids=(state_id,),
            )
        )
    if intent.kind == "nft_operator":
        if intent.grants and state.operator_approved:
            claims.append(
                CitedClaim(
                    id=f"{pid}:reach",
                    text=f"Operator {spender} is already approved for this collection.",
                    evidence_ids=(state_id,),
                )
            )
        return claims
    if state.balance is not None and intent.grants:
        wide = facts.effective_unlimited
        reach = facts.effective_amount
        limit = state.token_to_permit2 if intent.target != intent.token else None
        caps = [x for x in (reach, limit) if x is not None]
        reachable = min([state.balance, *caps])
        text = f"{owner} holds {amt(state.balance)} at the checked block, so {spender} could " + (
            f"move all of it, and any {label} received later."
            if wide and (limit is None or limit >= state.balance)
            else f"move up to {amt(reachable)}."
        )
        if limit == 0:
            text += " Permit2 has no allowance from this owner for the token yet."
        claims.append(CitedClaim(id=f"{pid}:reach", text=text, evidence_ids=(state_id,)))
    return claims


def baseline_explanation(catalog: Catalog, reasons: int) -> ReportDraft:
    claims = catalog.by_id()
    verdicts = [f"v{i}" for i in range(reasons) if f"v{i}" in claims]
    support = [c for c in claims if c.startswith("p") and ":" not in c] + [
        c for c in claims if c.startswith("p") and c.endswith((":reach", ":spender", ":control"))
    ]
    gaps = [c for c in claims if c.startswith("gap:")]
    return ReportDraft(
        summary=verdicts[:2] or [c for c in support[:1]] or ["input"],
        findings=support[:4],
        uncertainties=gaps[:3],
    )


def expand(ids: list[str], catalog: Catalog) -> tuple[CitedClaim, ...]:
    claims = catalog.by_id()
    return tuple(claims[i] for i in dict.fromkeys(ids) if i in claims)


def tool_context(
    rpc: RpcClient, chain: Chain, items: list[Facts], tag: Any, block: BlockRef
) -> ToolContext:
    """The shared spender tools take permission IDs. Each intent becomes a target whose
    only field the tools read is the spender."""
    targets = {}
    now = datetime.now(UTC)
    for facts in items:
        i = facts.intent
        targets[facts.pid] = PersistentExposure(
            id=facts.pid,
            historical=HistoricalPermission(
                token=i.token,
                owner=i.owner,
                spender=i.spender,
                allowance_raw=i.amount_raw or "1",
                unlimited=i.unlimited,
                block_number=block.number,
                timestamp=block.timestamp,
                evidence_ids=("input",),
                owner_role="sender",
            ),
            current=CurrentPermissionState(checked_at=now),
            status="ACTIVE",
            permission_active=True,
            summary="Proposed permission (not signed).",
            evidence_ids=("input",),
        )
    return ToolContext(
        rpc=rpc,
        chain_id=chain.chain_id,
        chain_name=chain.name,
        prefix="presign",
        targets=targets,
        contracts={},
        evidence={},
        tag=tag,
        compare_history=False,
    )


async def run_tool(
    ctx: ToolContext, tool: ToolName, pid: str
) -> tuple[ToolName, str, ToolResult | None, int]:
    started = time.monotonic()
    try:
        async with asyncio.timeout(10):
            return tool, pid, await TOOLS[tool](ctx, pid), _ms(started)
    except (RpcError, ValueError, TypeError, KeyError, TimeoutError):
        return tool, pid, None, _ms(started)


async def check(
    chain: Chain,
    rpc: RpcClient,
    decoded: Decoded,
    payload: dict[str, Any],
    explain: bool = False,
    llm: Any = None,
    settings: Any = None,
) -> PresignReport:
    started = time.monotonic()
    catalog = Catalog()
    evidence: list[Evidence] = [
        Evidence(
            id="input",
            source="transaction" if decoded.source == "transaction" else "EIP-712 typed data",
            description="The unsigned payload as submitted",
            data_json=json.dumps(payload, default=str)[:20_000],
        )
    ]
    catalog.add(
        CitedClaim(
            id="input",
            text=(
                f"The payload calls {decoded.function}."
                if decoded.function
                else "The payload was not decoded as a known approval format."
            ),
            evidence_ids=("input",),
        )
    )
    items = [Facts(pid=f"p{i}", intent=intent) for i, intent in enumerate(decoded.intents)]
    granting = [f for f in items if f.intent.grants]
    checks: list[CheckStep] = []
    gaps: list[str] = []
    block: BlockRef | None = None
    state_ids: dict[str, str] = {}
    if granting:
        try:
            async with asyncio.timeout(CHECK_TIMEOUT):
                latest = await rpc.call("eth_getBlockByNumber", ["latest", False])
                block = BlockRef(
                    number=int(latest["number"], 16),
                    hash=latest["hash"],
                    timestamp=int(latest["timestamp"], 16),
                )
                tag = {"blockHash": block.hash, "requireCanonical": True}
                evidence.append(
                    Evidence(
                        id="presign:block",
                        source="eth_getBlockByNumber",
                        description="Pinned block for every read, revalidated afterwards",
                        data_json=block.model_dump_json(),
                    )
                )
                read = await asyncio.gather(
                    *(read_state(rpc, f.intent, tag, f"presign:state:{f.pid}") for f in granting)
                )
                for facts, (state, item) in zip(granting, read, strict=True):
                    facts.state = state
                    state_ids[facts.pid] = item.id
                    evidence.append(item)
                ctx = tool_context(rpc, chain, granting, tag, block)
                tool_evidence: list[Evidence] = []
                tool_claims: list[CitedClaim] = []
                first: tuple[ToolName, ...] = ("spender_profile", "known_spender")
                pending: list[tuple[ToolName, str]] = [
                    (tool, f.pid) for f in granting for tool in first
                ]
                by_pid = {f.pid: f for f in granting}
                while pending:
                    results = await asyncio.gather(*(run_tool(ctx, t, p) for t, p in pending))
                    pending = []
                    for tool, pid, result, duration in results:
                        facts = by_pid[pid]
                        checks.append(
                            CheckStep(
                                name=tool,
                                permission_id=pid,
                                status="ok" if result else "error",
                                duration_ms=duration,
                            )
                        )
                        if result is None:
                            facts.failed_tools.append(tool)
                            gaps.append(f"{tool} for {pid} could not complete.")
                            continue
                        facts.spender.update(result.facts)
                        tool_claims += result.claims
                        tool_evidence += result.evidence
                        if tool == "spender_profile" and result.facts.get("proxy"):
                            pending.append(("upgrade_control", pid))
                after = await rpc.call("eth_getBlockByNumber", [hex(block.number), False])
                if not after or after.get("hash") != block.hash:
                    raise ValueError("block changed during reads")
                evidence += tool_evidence
                for claim in tool_claims:
                    catalog.add(claim)
        except (RpcError, ValueError, TypeError, KeyError, TimeoutError) as exc:
            # Inconsistent or partial state is not evidence. Every granting intent becomes
            # unverifiable, which the rules turn into warn (or block on other grounds).
            gaps.append(
                "Chain state could not be read consistently"
                + (" (the block changed during reads)." if "block changed" in str(exc) else ".")
            )
            block = None
            evidence = evidence[:1]
            state_ids.clear()
            checks.clear()
            catalog = Catalog(claims=[catalog.by_id()["input"]])
            for facts in granting:
                facts.state, facts.spender, facts.failed_tools = None, {}, ["spender_profile"]
    for facts in items:
        for claim in intent_claims(facts, "input", state_ids.get(facts.pid)):
            catalog.add(claim)
        if facts.state:
            gaps += [f"{facts.pid}: {e}" for e in facts.state.errors]
    for index, gap in enumerate(dict.fromkeys(gaps)):
        catalog.add(CitedClaim(id=f"gap:{index}", text=gap, evidence_ids=()))
    decision, reasons = evaluate(
        decoded,
        chain.chain_id,
        items,
        set(catalog.by_id()),
        block.timestamp if block else None,
    )
    for index, reason in enumerate(reasons):
        support = [catalog.by_id()[c] for c in reason.claim_ids if c in catalog.by_id()]
        catalog.add(
            CitedClaim(
                id=f"v{index}",
                text=reason.text,
                evidence_ids=tuple(dict.fromkeys(e for c in support for e in c.evidence_ids)),
            )
        )
    headline = (
        f"{decision.upper()}: {reasons[0].text}"
        if reasons
        else "ALLOW: no rule fired for this approval."
    )
    explanation = None
    if explain:
        try:
            from app.presign.explain import explain_verdict  # loads NOOA only when asked
        except ImportError:  # NOOA needs fcntl/SIGUSR2 (Linux or macOS)
            draft = baseline_explanation(catalog, len(reasons))
            explanation = Explanation(
                author="baseline",
                summary=expand(draft.summary, catalog),
                findings=expand(draft.findings, catalog),
                uncertainties=expand(draft.uncertainties, catalog),
                reason="Model explanations need Linux or macOS. Showing rule-based explanation.",
            )
        else:
            explanation = await explain_verdict(catalog, decision, len(reasons), settings, llm)
    return PresignReport(
        verdict=decision,
        headline=headline,
        chain=chain.slug,
        source=decoded.source,
        function=decoded.function,
        intents=decoded.intents,
        reasons=tuple(reasons),
        claims=tuple(catalog.claims),
        evidence=tuple(evidence),
        coverage_gaps=tuple(dict.fromkeys(gaps)),
        block=block,
        checks=tuple(checks),
        explanation=explanation,
        duration_ms=_ms(started),
    )
