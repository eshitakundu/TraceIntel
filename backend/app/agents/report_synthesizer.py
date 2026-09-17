from nooa import Agent, PredictStrategy, strategy
from nooa.config import PredictConfig

from app.models.interpretation import AgentSelection, CitedClaim


class ReportSynthesizer(Agent):
    """Organize validated transaction and contract findings into a readable report."""

    @strategy(PredictStrategy(config=PredictConfig(max_retries=1, max_tokens=4000)))
    async def synthesize(
        self,
        catalog: tuple[CitedClaim, ...],
        transaction: AgentSelection,
        contracts: AgentSelection | None,
    ) -> AgentSelection:
        """Select and order the final overview, findings, limitations and checks.
        Return only the JSON object. Do not output reasoning or planning text.
        Keep summary to two claims, findings to three and uncertainties to three.
        Prioritize current exposure and historical risk separately.
        All claims must be copied exactly from the catalog. Consolidate repetition.
        Preserve important uncertainties; a low observed score is not a safety conclusion.
        Never change deterministic evidence or invent new claims.
        """
        ...
