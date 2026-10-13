"""Agent orchestration: investigate live permissions, then brief the owner.

The model is optional at every step. With no model, a failed model, or an invalid
answer, the deterministic baseline produces the investigation and the advice, and
the report says why.
"""

import asyncio
import time
from typing import Any, Literal

from nooa.unifiedllm.registry import get_llm_client
from nooa.unifiedllm.retry_config import RetryConfig
from pydantic import ValidationError

from app.agents.catalog import Catalog
from app.agents.investigator import Budget, elapsed_ms, investigate
from app.agents.planner import BaselinePlanner, Investigator, ModelPlanner, Planner
from app.agents.reporter import Reporter, baseline_brief
from app.agents.tools import ToolContext
from app.agents.validation import SelectionRejected, validate_draft
from app.config import Settings
from app.models.interpretation import AgentSelection, Interpretation, TraceStep

LLM_CALL_TIMEOUT = 30
REPORT_TIMEOUT = 75
MODEL_BUDGET = Budget(max_rounds=2, max_calls=8, per_round=4)
BASELINE_BUDGET = Budget(max_rounds=3, max_calls=8, per_round=4)

_PROVIDER_FAILURES = {
    "AuthenticationError": "the provider rejected the API key",
    "PermissionDeniedError": "the provider denied access to the model",
    "NotFoundError": "the configured model was not found",
    "RateLimitError": "the provider rate-limited the request",
    "BadRequestError": "the provider rejected the request",
    "UnprocessableEntityError": "the provider rejected the request",
    "ContextWindowExceededError": "the request exceeded the model's context window",
    "APIConnectionError": "the provider was unreachable",
    "ServiceUnavailableError": "the provider was unavailable",
    "InternalServerError": "the provider failed",
    "GenerationError": "the model's answer did not match the required format",
}


def describe_failure(exc: BaseException) -> str:
    """A safe, specific reason. Never includes provider messages, which may echo secrets."""
    name = type(exc).__name__
    if isinstance(exc, TimeoutError):
        detail = "the model did not answer in time"
    elif isinstance(exc, ValidationError):
        detail = "the model's answer did not match the required format"
    else:
        detail = _PROVIDER_FAILURES.get(name, "the model step failed")
    return f"Model unavailable: {detail} ({name})."


def model_client(settings: Settings) -> Any:
    return get_llm_client(
        "openrouter/" + settings.openrouter_model,
        api_key=settings.openrouter_api_key.get_secret_value(),
        timeout=LLM_CALL_TIMEOUT,
        num_retries=0,
        retry_config=RetryConfig(max_retries=0, rate_limit_extra_retries=0),
    )


async def interpret(
    catalog: Catalog,
    ctx: ToolContext,
    settings: Settings,
    use_model: bool,
    llm: Any = None,
    always_plan_with_model: bool = False,
) -> Interpretation:
    started = time.monotonic()
    trace: list[TraceStep] = []
    reason: str | None = None
    owned = llm is None and use_model
    try:
        if owned:
            try:
                llm = model_client(settings)
            except Exception as exc:
                reason = describe_failure(exc)
                llm = None
        model_name = (settings.openrouter_model or getattr(llm, "model", None)) if llm else None

        # A model plan only adds value when there is something to prioritise.
        planner: Planner = BaselinePlanner()
        if llm is not None and (always_plan_with_model or len(catalog.actionable_targets()) >= 2):
            planner = ModelPlanner(Investigator(llm=llm))
        investigation, state = await investigate(
            catalog, ctx, planner, MODEL_BUDGET if planner.kind == "model" else BASELINE_BUDGET
        )
        trace += state.trace
        llm_calls = sum(1 for t in state.trace if t.actor == "planner" and t.name == "model")

        selection: AgentSelection | None = None
        if llm is not None:
            feedback = ""
            for attempt in (1, 2):
                step_started = time.monotonic()
                try:
                    async with asyncio.timeout(REPORT_TIMEOUT / 2):
                        draft = await Reporter(llm=llm).brief(
                            tuple(catalog.claims), catalog.actionable_targets(), feedback
                        )
                    llm_calls += 1
                    selection = validate_draft(draft, catalog)
                    trace.append(
                        TraceStep(
                            actor="reporter",
                            name="model",
                            detail="Briefing validated against the catalog."
                            if attempt == 1
                            else "Repaired briefing validated against the catalog.",
                            status="ok",
                            duration_ms=elapsed_ms(step_started),
                            claim_ids=tuple(c.id for c in selection.summary),
                        )
                    )
                    break
                except SelectionRejected as exc:
                    feedback = "; ".join(exc.problems)
                    trace.append(
                        TraceStep(
                            actor="validator",
                            name="briefing",
                            detail=f"Rejected: {exc.problems[0]}"
                            + (
                                f" (+{len(exc.problems) - 1} more)" if len(exc.problems) > 1 else ""
                            ),
                            status="rejected",
                            duration_ms=elapsed_ms(step_started),
                        )
                    )
                    reason = "The model's briefing failed validation twice."
                except Exception as exc:
                    reason = describe_failure(exc)
                    trace.append(
                        TraceStep(
                            actor="reporter",
                            name="model",
                            detail=reason,
                            status="error",
                            duration_ms=elapsed_ms(step_started),
                        )
                    )
                    break
        elif not use_model:
            reason = "No model configured."

        author: Literal["model", "baseline"] = "model" if selection is not None else "baseline"
        if selection is None:
            step_started = time.monotonic()
            selection = validate_draft(baseline_brief(catalog, state.facts), catalog)
            trace.append(
                TraceStep(
                    actor="reporter",
                    name="baseline",
                    detail="Rule-based briefing validated against the catalog.",
                    status="ok",
                    duration_ms=elapsed_ms(step_started),
                    claim_ids=tuple(c.id for c in selection.summary),
                )
            )
            if reason:
                reason += " Showing rule-based advice."
        return Interpretation(
            status="available",
            model=model_name if author == "model" else None,
            author=author,
            result=selection,
            reason=None if author == "model" else reason,
            investigation=investigation,
            trace=tuple(trace),
            llm_calls=llm_calls,
            duration_ms=elapsed_ms(started),
        )
    finally:
        if owned and llm is not None:
            await llm.aclose()
