import asyncio

from nooa.unifiedllm.registry import get_llm_client

from app.agents.contract_analyst import ContractAnalyst
from app.agents.report_synthesizer import ReportSynthesizer
from app.agents.transaction_analyst import TransactionAnalyst
from app.agents.validation import validate_selection
from app.config import Settings
from app.models.interpretation import CitedClaim, Interpretation


async def interpret(
    catalog: tuple[CitedClaim, ...], settings: Settings, has_contracts: bool
) -> Interpretation:
    if not settings.openrouter_api_key.get_secret_value() or not settings.openrouter_model:
        return Interpretation(status="unavailable", reason="NOOA model/key is not configured.")
    try:
        llm = get_llm_client(
            "openrouter/" + settings.openrouter_model.removeprefix("openrouter/"),
            api_key=settings.openrouter_api_key.get_secret_value(),
            timeout=25,
            num_retries=0,
        )
        async with asyncio.timeout(90):
            transaction = validate_selection(
                await TransactionAnalyst(llm=llm).explain(catalog), catalog
            )
            contracts = None
            if has_contracts:
                contracts = validate_selection(
                    await ContractAnalyst(llm=llm).explain(catalog), catalog
                )
            result = validate_selection(
                await ReportSynthesizer(llm=llm).synthesize(catalog, transaction, contracts),
                catalog,
            )
        return Interpretation(status="available", model=settings.openrouter_model, result=result)
    except ValueError:
        return Interpretation(
            status="rejected", reason="Agent returned an unsupported claim or citation."
        )
    except Exception:
        # Keep provider credentials and raw provider exception bodies out of public reports.
        return Interpretation(
            status="unavailable", reason="NOOA interpretation failed or timed out."
        )
