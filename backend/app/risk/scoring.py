from typing import Literal

from app.models.risk import RiskAssessment, RiskSignal


def aggregate(signals: tuple[RiskSignal, ...]) -> RiskAssessment:
    # One contribution per rule code avoids inflating scores for repeated emissions.
    weights: dict[str, int] = {}
    for signal in signals:
        weights[signal.code] = max(weights.get(signal.code, 0), signal.score)
    score = min(100, sum(weights.values()))
    level: Literal["minimal", "low", "moderate", "high", "critical"] = (
        "critical"
        if score >= 80
        else "high"
        if score >= 50
        else "moderate"
        if score >= 20
        else "low"
        if score
        else "minimal"
    )
    return RiskAssessment(score=score, level=level, signals=signals)
