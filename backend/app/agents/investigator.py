"""The investigation loop: plan → validate → run tools in parallel → observe → repeat.

Budgets are enforced here, not in prompts. Every requested call is validated against
the tool registry and the catalog's permission IDs before anything runs, and every
decision is recorded in the trace.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from app.agents.catalog import Catalog
from app.agents.planner import BaselinePlanner, Planner
from app.agents.tools import TOOLS, ToolContext, ToolResult
from app.blockchain.rpc_client import RpcError
from app.models.blockchain import Coverage, Evidence
from app.models.interpretation import CitedClaim, Investigation, ToolCall, TraceStep


@dataclass(frozen=True)
class Budget:
    max_rounds: int = 3
    max_calls: int = 8
    per_round: int = 4


DEFAULT_BUDGET = Budget()


@dataclass
class InvestigationState:
    catalog: Catalog
    calls_left: int
    rounds_left: int
    per_round: int
    findings: list[CitedClaim] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    coverage: list[Coverage] = field(default_factory=list)
    done: set[tuple[str, str]] = field(default_factory=set)
    facts: dict[str, dict[str, Any]] = field(default_factory=dict)
    trace: list[TraceStep] = field(default_factory=list)


def elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def screen(call: ToolCall, state: InvestigationState, accepted: list[ToolCall]) -> str | None:
    """Why a requested call must not run, or None when it may."""
    if call.permission_id not in state.catalog.targets:
        return "unknown permission id"
    if call.permission_id not in state.catalog.actionable_targets():
        return "permission is not live or not the sender's"
    if (call.tool, call.permission_id) in state.done or any(
        (a.tool, a.permission_id) == (call.tool, call.permission_id) for a in accepted
    ):
        return "duplicate call"
    if len(accepted) >= min(state.per_round, state.calls_left):
        return "over budget"
    return None


async def run_tool(call: ToolCall, ctx: ToolContext) -> tuple[ToolResult | None, int]:
    started = time.monotonic()
    try:
        async with asyncio.timeout(20):
            return await TOOLS[call.tool](ctx, call.permission_id), elapsed_ms(started)
    except (RpcError, ValueError, TypeError, KeyError, TimeoutError):
        return None, elapsed_ms(started)


async def investigate(
    catalog: Catalog, ctx: ToolContext, planner: Planner, budget: Budget = DEFAULT_BUDGET
) -> tuple[Investigation, InvestigationState]:
    state = InvestigationState(
        catalog=catalog,
        calls_left=budget.max_calls,
        rounds_left=budget.max_rounds,
        per_round=budget.per_round,
    )
    kind = planner.kind
    if not catalog.actionable_targets():
        state.trace.append(
            TraceStep(
                actor="planner",
                name="skip",
                detail="No live permissions held by the sender to investigate.",
                status="skipped",
            )
        )
        return Investigation(planner=kind), state
    fallback = BaselinePlanner()
    while state.rounds_left and state.calls_left:
        started = time.monotonic()
        try:
            step = await planner.next(state)
        except Exception as exc:  # A failed model planner degrades to the baseline policy.
            state.trace.append(
                TraceStep(
                    actor="planner",
                    name=planner.kind,
                    detail=f"Planner failed ({type(exc).__name__}); continuing with baseline.",
                    status="error",
                    duration_ms=elapsed_ms(started),
                )
            )
            planner = fallback
            continue
        state.rounds_left -= 1
        accepted: list[ToolCall] = []
        for call in step.calls:
            problem = screen(call, state, accepted)
            if problem:
                state.trace.append(
                    TraceStep(
                        actor="validator",
                        name=call.tool,
                        detail=f"Rejected {call.tool}({call.permission_id}): {problem}.",
                        status="rejected",
                    )
                )
            else:
                accepted.append(call)
        state.trace.append(
            TraceStep(
                actor="planner",
                name=planner.kind,
                detail=(
                    "Requested " + ", ".join(f"{c.tool}({c.permission_id})" for c in accepted)
                    if accepted
                    else "Finished: no further checks needed."
                ),
                status="ok",
                duration_ms=elapsed_ms(started),
            )
        )
        if not accepted:
            break
        results = await asyncio.gather(*(run_tool(call, ctx) for call in accepted))
        for call, (result, duration) in zip(accepted, results, strict=True):
            state.done.add((call.tool, call.permission_id))
            state.calls_left -= 1
            if result is None:
                state.coverage.append(
                    Coverage(
                        area=f"investigation:{call.permission_id}",
                        status="unavailable",
                        reason=f"{call.tool} could not complete; the provider failed or timed out.",
                    )
                )
                state.trace.append(
                    TraceStep(
                        actor="tool",
                        name=call.tool,
                        detail=f"{call.tool}({call.permission_id}) failed.",
                        status="error",
                        duration_ms=duration,
                    )
                )
                continue
            state.facts.setdefault(call.permission_id, {}).update(result.facts)
            state.findings += result.claims
            state.evidence += result.evidence
            state.coverage += result.coverage
            for claim in result.claims:
                catalog.add(claim)
            state.trace.append(
                TraceStep(
                    actor="tool",
                    name=call.tool,
                    detail=f"{call.tool}({call.permission_id})",
                    status="ok",
                    duration_ms=duration,
                    claim_ids=tuple(c.id for c in result.claims),
                )
            )
        if step.done:
            break
    if planner.kind == "baseline" and kind == "model":
        kind = "baseline"
    return (
        Investigation(
            planner=kind,
            claims=tuple(state.findings),
            evidence=tuple(state.evidence),
            coverage=tuple(state.coverage),
            rounds=len([t for t in state.trace if t.actor == "planner" and t.status == "ok"]),
            tool_calls=len(state.done),
        ),
        state,
    )
