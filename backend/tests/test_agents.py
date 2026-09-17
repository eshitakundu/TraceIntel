import pytest
from app.agents.transaction_analyst import TransactionAnalyst
from app.agents.validation import validate_selection
from app.models.interpretation import AgentSelection, CitedClaim
from nooa.unifiedllm.fake import FakeLLMClient


@pytest.mark.asyncio
async def test_real_predict_strategy_with_scripted_transport() -> None:
    claim = CitedClaim(id="tx:status", text="Transaction success.", evidence_ids=("receipt:1",))
    expected = AgentSelection(
        summary=(claim,),
        important_findings=(),
        uncertainties=(),
        recommended_checks=("compare_explorer",),
        confidence=0.8,
    )
    llm = FakeLLMClient.simple_message(expected.model_dump_json())
    result = await TransactionAnalyst(llm=llm).explain((claim,))
    assert validate_selection(result, (claim,)) == expected
    assert llm.call_count == 1
    assert not llm.last_tools


@pytest.mark.parametrize("change", ["text", "evidence_ids", "id"])
def test_rejects_unsupported_claim_and_citation(change: str) -> None:
    claim = CitedClaim(id="tx:status", text="Transaction success.", evidence_ids=("receipt:1",))
    bad = claim.model_copy(
        update={change: ("invented",) if change == "evidence_ids" else "invented"}
    )
    result = AgentSelection(
        summary=(bad,), important_findings=(), uncertainties=(), recommended_checks=(), confidence=1
    )
    with pytest.raises(ValueError, match="Unsupported"):
        validate_selection(result, (claim,))
