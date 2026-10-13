from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.base import FrozenModel
from app.models.blockchain import Coverage, Evidence

RecommendedCheck = Literal[
    "verify_spender",
    "review_allowance",
    "review_implementation",
    "compare_explorer",
    "check_missing_data",
]
ActionKind = Literal["consider_revoking", "verify_spender", "review_upgrade_control"]
ToolName = Literal["spender_profile", "upgrade_control", "known_spender"]


class CitedClaim(FrozenModel):
    """A sentence written by code from evidence. Models select claims; they never write them."""

    id: str
    text: str
    evidence_ids: tuple[str, ...]


class PermissionAction(FrozenModel):
    permission_id: str
    action: ActionKind
    reasons: tuple[CitedClaim, ...] = Field(min_length=1, max_length=4)


class AgentSelection(FrozenModel):
    summary: tuple[CitedClaim, ...] = Field(max_length=5)
    important_findings: tuple[CitedClaim, ...] = Field(max_length=12)
    uncertainties: tuple[CitedClaim, ...] = Field(max_length=12)
    recommended_checks: tuple[RecommendedCheck, ...] = Field(max_length=5)
    # Reports created before 1.2.0 stored a model self-reported confidence; it is unused.
    confidence: float | None = Field(default=None, ge=0, le=1)
    actions: tuple[PermissionAction, ...] = Field(default=(), max_length=8)


# ——— Model output contracts. Models answer with claim IDs, never with prose. ———


class _Output(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ToolCall(_Output):
    tool: ToolName
    permission_id: str


class PlanStep(_Output):
    calls: list[ToolCall] = Field(default_factory=list)
    done: bool = False


class ActionPick(_Output):
    permission_id: str
    action: ActionKind
    because: list[str] = Field(default_factory=list)


class ReportDraft(_Output):
    summary: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    actions: list[ActionPick] = Field(default_factory=list)
    checks: list[RecommendedCheck] = Field(default_factory=list)


# ——— Audit trail ———


class TraceStep(FrozenModel):
    actor: Literal["planner", "tool", "reporter", "validator"]
    name: str
    detail: str
    status: Literal["ok", "rejected", "error", "skipped"]
    duration_ms: int = 0
    claim_ids: tuple[str, ...] = ()


class Investigation(FrozenModel):
    """Follow-up checks chosen by a planner and executed by deterministic tools."""

    planner: Literal["model", "baseline"]
    claims: tuple[CitedClaim, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    coverage: tuple[Coverage, ...] = ()
    rounds: int = 0
    tool_calls: int = 0


class Interpretation(FrozenModel):
    status: Literal["available", "unavailable", "rejected"]
    model: str | None = None
    # Who wrote the briefing: the model, or the rule-based baseline it is measured against.
    author: Literal["model", "baseline"] | None = None
    result: AgentSelection | None = None
    reason: str | None = None
    investigation: Investigation | None = None
    trace: tuple[TraceStep, ...] = ()
    llm_calls: int = 0
    duration_ms: int = 0
