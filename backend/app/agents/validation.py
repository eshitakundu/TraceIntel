"""The grounding boundary between model output and the report.

A draft names claim IDs and actions. Validation checks every ID against the catalog,
checks that each action targets a live permission the sender controls and cites at
least one claim about that permission, then expands IDs back into code-written claims.
Problems are returned as feedback so the reporter can repair its answer once.
"""

from app.agents.catalog import Catalog
from app.agents.reporter import belongs
from app.models.interpretation import (
    AgentSelection,
    CitedClaim,
    PermissionAction,
    ReportDraft,
)


class SelectionRejected(ValueError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def _unique(ids: list[str]) -> list[str]:
    return list(dict.fromkeys(ids))


def validate_draft(draft: ReportDraft, catalog: Catalog) -> AgentSelection:
    claims = catalog.by_id()
    actionable = set(catalog.actionable_targets())
    problems: list[str] = []
    for section in ("summary", "findings", "uncertainties"):
        unknown = [i for i in getattr(draft, section) if i not in claims]
        if unknown:
            problems.append(f"{section} uses unknown claim IDs {unknown}")
    if not draft.summary:
        problems.append("summary must contain at least one claim ID")
    actions: list[PermissionAction] = []
    seen: set[tuple[str, str]] = set()
    for pick in draft.actions:
        label = f"action {pick.action} for {pick.permission_id}"
        if pick.permission_id not in actionable:
            problems.append(f"{label}: not a live permission the sender controls")
            continue
        unknown = [i for i in pick.because if i not in claims]
        if unknown:
            problems.append(f"{label}: unknown claim IDs {unknown}")
            continue
        because = _unique(pick.because)[:3]
        if not any(belongs(i, pick.permission_id) for i in because):
            problems.append(f"{label}: cite at least one claim about {pick.permission_id}")
            continue
        if (pick.permission_id, pick.action) in seen:
            continue
        seen.add((pick.permission_id, pick.action))
        actions.append(
            PermissionAction(
                permission_id=pick.permission_id,
                action=pick.action,
                reasons=tuple(claims[i] for i in because),
            )
        )
    if problems:
        raise SelectionRejected(problems)

    def expand(ids: list[str], limit: int) -> tuple[CitedClaim, ...]:
        return tuple(claims[i] for i in _unique(ids)[:limit])

    return AgentSelection(
        summary=expand(draft.summary, 2),
        important_findings=expand(draft.findings, 4),
        uncertainties=expand(draft.uncertainties, 3),
        recommended_checks=tuple(dict.fromkeys(draft.checks))[:5],
        actions=tuple(actions[:6]),
    )
