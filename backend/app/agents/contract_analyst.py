from nooa import Agent, PredictStrategy, strategy
from nooa.config import PredictConfig

from app.models.interpretation import AgentSelection, CitedClaim


class ContractAnalyst(Agent):
    """Select contract-specific context relevant to verifying this transaction."""

    @strategy(PredictStrategy(config=PredictConfig(max_retries=1, max_tokens=2400)))
    async def explain(self, catalog: tuple[CitedClaim, ...]) -> AgentSelection:
        """Prioritize contract/proxy evidence and coverage limitations.
        Copy claims verbatim from the catalog with their original IDs and references.
        Do not infer maliciousness from proxy use, missing source, or missing data.
        Choose verification steps from the allowed codes. Never invent facts.
        """
        ...
