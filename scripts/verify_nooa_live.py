"""Opt-in live NOOA evaluation: at most three calls, no provider error/key output."""

import asyncio
import hashlib
import json
from pathlib import Path

from app.agents.catalog import build_catalog
from app.agents.contract_analyst import ContractAnalyst
from app.agents.report_synthesizer import ReportSynthesizer
from app.agents.transaction_analyst import TransactionAnalyst
from app.agents.validation import validate_selection
from app.blockchain.decoder import decode_transaction
from app.config import Settings
from app.models.blockchain import RawTransaction
from app.risk.engine import evaluate
from nooa.unifiedllm.registry import get_llm_client
from nooa.unifiedllm.retry_config import RetryConfig


async def main() -> None:
    settings = Settings()
    if not settings.openrouter_api_key.get_secret_value():
        raise SystemExit("OpenRouter key is not configured.")
    raw = RawTransaction.model_validate_json(
        await asyncio.to_thread(Path("evals/cases/ethereum-recorded.json").read_text)
    )
    decoded = decode_transaction(raw)
    before = hashlib.sha256(decoded.model_dump_json().encode()).hexdigest()
    risk = evaluate(decoded, ())
    catalog = build_catalog(decoded, risk, (), decoded.coverage)
    llm = get_llm_client(
        "openrouter/" + settings.openrouter_model,
        api_key=settings.openrouter_api_key.get_secret_value(),
        timeout=30,
        num_retries=0,
        retry_config=RetryConfig(max_retries=0, rate_limit_extra_retries=0),
    )
    try:
        async with asyncio.timeout(100):
            transaction = validate_selection(
                await TransactionAnalyst(llm=llm).explain(catalog), catalog
            )
            contract = validate_selection(await ContractAnalyst(llm=llm).explain(catalog), catalog)
            final = validate_selection(
                await ReportSynthesizer(llm=llm).synthesize(catalog, transaction, contract), catalog
            )
    except Exception as exc:
        detail = str(exc).replace(settings.openrouter_api_key.get_secret_value(), "[REDACTED]")
        print(
            json.dumps(
                {"status": "failed", "error_type": type(exc).__name__, "detail": detail[:800]}
            )
        )
        raise SystemExit(1) from None
    assert before == hashlib.sha256(decoded.model_dump_json().encode()).hexdigest()
    print(
        json.dumps(
            {
                "status": "passed",
                "model": settings.openrouter_model,
                "claims": len(final.summary) + len(final.important_findings),
                "evidence_unchanged": True,
                "citations_valid": True,
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
