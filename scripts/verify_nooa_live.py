"""Opt-in live agent evaluation against a real model (charges apply).

Runs every labelled scenario with the configured OpenRouter model as planner and
reporter. The on-chain world is scripted, so only the model varies between runs.
Reports advice accuracy against the labels next to the rule-based baseline, plus
grounding, repairs, model calls and latency. Results are written to evals/results/.

    OPENROUTER_API_KEY=... OPENROUTER_MODEL=... \\
        PYTHONPATH=backend uv run python scripts/verify_nooa_live.py
"""

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from app.agents.service import interpret, model_client
from app.config import Settings
from app.evaluation.scenarios import SCENARIOS, Scenario, build, grounded


async def run(scenario: Scenario, settings: Settings, use_model: bool) -> dict[str, object]:
    built = build(scenario.world)
    llm = model_client(settings) if use_model else None
    started = time.monotonic()
    try:
        async with built.client:
            result = await interpret(
                built.catalog,
                built.ctx,
                settings,
                use_model,
                llm=llm,
                always_plan_with_model=use_model,
            )
    finally:
        if llm is not None:
            await llm.aclose()
    selection = result.result
    actions = {a.permission_id: a.action for a in selection.actions} if selection else {}
    return {
        "scenario": scenario.name,
        "author": result.author,
        "advice_matches_label": actions == scenario.actions,
        "grounded": grounded(result, built),
        "repairs": sum(1 for t in result.trace if t.actor == "validator" and t.name == "briefing"),
        "planner_rejections": sum(
            1 for t in result.trace if t.actor == "validator" and t.name != "briefing"
        ),
        "llm_calls": result.llm_calls,
        "seconds": round(time.monotonic() - started, 1),
        "reason": result.reason,
    }


def summarise(rows: list[dict[str, object]]) -> dict[str, object]:
    count = len(rows)
    return {
        "advice_accuracy": sum(bool(r["advice_matches_label"]) for r in rows) / count,
        "grounded_rate": sum(bool(r["grounded"]) for r in rows) / count,
        "model_authored_rate": sum(r["author"] == "model" for r in rows) / count,
        "repairs": sum(int(r["repairs"]) for r in rows),  # type: ignore[call-overload]
        "llm_calls": sum(int(r["llm_calls"]) for r in rows),  # type: ignore[call-overload]
        "median_seconds": sorted(float(r["seconds"]) for r in rows)[count // 2],  # type: ignore[arg-type]
    }


async def evaluate() -> dict[str, object]:
    settings = Settings()
    if not settings.openrouter_api_key.get_secret_value() or not settings.openrouter_model:
        raise SystemExit("Set OPENROUTER_API_KEY and OPENROUTER_MODEL to run the live evaluation.")
    baseline = [await run(s, settings, use_model=False) for s in SCENARIOS]
    model = [await run(s, settings, use_model=True) for s in SCENARIOS]
    return {
        "model": settings.openrouter_model,
        "ran_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "baseline": summarise(baseline),
        "model_summary": summarise(model),
        "cases": model,
    }


if __name__ == "__main__":
    report = asyncio.run(evaluate())
    out = Path("evals/results")
    out.mkdir(parents=True, exist_ok=True)
    name = str(report["model"]).replace("/", "_")
    (out / f"live-{name}.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))
