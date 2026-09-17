from typing import Literal

from pydantic import Field

from app.models.base import FrozenModel


class RiskSignal(FrozenModel):
    code: str
    severity: Literal["info", "low", "medium", "high"]
    score: int = Field(ge=0, le=100)
    title: str
    description: str
    reason: str
    source: str
    evidence_ids: tuple[str, ...]


class RiskAssessment(FrozenModel):
    version: str = "1.0.0"
    score: int = Field(ge=0, le=100)
    level: Literal["minimal", "low", "moderate", "high", "critical"]
    signals: tuple[RiskSignal, ...]
    interpretation: str = "Observed indicators only; not a safety rating or probability of loss."
