from app.models.interpretation import AgentSelection, CitedClaim


def validate_selection(
    selection: AgentSelection, catalog: tuple[CitedClaim, ...]
) -> AgentSelection:
    allowed = {claim.id: claim for claim in catalog}
    for claim in selection.summary + selection.important_findings + selection.uncertainties:
        if allowed.get(claim.id) != claim:
            raise ValueError("Unsupported claim or changed evidence citation.")
    if not selection.summary:
        raise ValueError("Interpretation has no cited summary.")
    return selection
