from typing import Literal

from pydantic import Field

from app.models.base import FrozenModel


class CitedClaim(FrozenModel):
    id: str
    text: str
    evidence_ids: tuple[str, ...]


class AgentSelection(FrozenModel):
    summary: tuple[CitedClaim, ...] = Field(max_length=5)
    important_findings: tuple[CitedClaim, ...] = Field(max_length=12)
    uncertainties: tuple[CitedClaim, ...] = Field(max_length=12)
    recommended_checks: tuple[
        Literal[
            "verify_spender",
            "review_allowance",
            "review_implementation",
            "compare_explorer",
            "check_missing_data",
        ],
        ...,
    ] = Field(max_length=5)
    confidence: float = Field(ge=0, le=1)


class Interpretation(FrozenModel):
    status: Literal["available", "unavailable", "rejected"]
    model: str | None = None
    result: AgentSelection | None = None
    reason: str | None = None
