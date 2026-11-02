"""Shared selector/executor contract (EXPLORATION_PLANNER_DESIGN.md §10.1).

Every exploration policy (BFS, the legacy frontier approximation, the ACG
planner and its ablations) implements `Selector` and is driven by the same
loop, executor, risk gate, budget and evidence log. A selector sees only
evidence records it was given and, if it asks for one, the ACG materialized
from those records. It never sees the environment.
"""
from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from agent1.model.evidence import AffordanceEvidence, Record
from agent1.model.schema import ACGExport

StepOp = Literal["click", "goto", "back", "fresh", "snapshot"]


class Isolation(BaseModel):
    """What the environment adapter attests (PROPOSED_APPLICATION_MODEL.md §6.1)."""
    level: int = 0                       # 0..5
    exploratory_writes: bool = False     # operator allows the first observation of an unknown write
    snapshot: bool = False               # adapter can restore a verified initial snapshot (L3+)
    roles: list[str] = Field(default_factory=lambda: ["anonymous"])
    default_role: str = "anonymous"
    start_url: str = "/"


class Costs(BaseModel):
    """Browser-action cost of each step kind, declared by the adapter."""
    click: int = 1
    goto: int = 1
    back: int = 1
    fresh: int = 1
    snapshot: int = 3


class Step(BaseModel):
    op: StepOp
    affordance: AffordanceEvidence | None = None   # click: the control as observed
    url: str | None = None                         # goto
    role: str | None = None                        # fresh / snapshot: context role
    replay_of: str | None = None                   # click: recorded action id this step re-executes
    input: str | None = None                       # click on a form: input variant ("primary", "contrast", ...)
    oracle_capture: Literal["before_after", "after"] | None = None
    purpose: Literal["restore", "experiment", "oracle"] = "experiment"


class ExperimentPlan(BaseModel):
    question_id: str | None = None
    kind: str = "explore"
    steps: list[Step]
    oracle: Literal["paired_search", "cross_view"] | None = None
    oracle_action: str | None = None


class ExperimentResult(BaseModel):
    records: list[Record]
    actions: int
    completed: bool
    abort_reason: str | None = None
    refused: list[str] = Field(default_factory=list)       # risk-gate refusals (unsafe attempts)
    live_obs: str                                          # obs_id of the live state afterwards
    action_ids: list[str] = Field(default_factory=list)    # new action records
    replay_ids: list[str] = Field(default_factory=list)
    record_actions: list[int] = Field(default_factory=list)  # actions used in this plan when each record was made
    purpose_actions: dict[str, int] = Field(default_factory=dict)


class AgentView(BaseModel):
    """Everything a selector may know when deciding."""
    model_config = {"arbitrary_types_allowed": True}
    records: list[Record]
    acg: ACGExport | None
    live_obs: str
    remaining: int
    used: int
    isolation: Isolation
    costs: Costs


class Selector(Protocol):
    name: str
    uses_acg: bool

    def next(self, view: AgentView) -> ExperimentPlan | None: ...

    def update(self, plan: ExperimentPlan, result: ExperimentResult, view: AgentView) -> None: ...

    def decisions(self) -> list[dict[str, Any]]: ...


class Executor(Protocol):
    isolation: Isolation
    costs: Costs

    def start(self) -> list[Record]: ...

    def run(self, plan: ExperimentPlan, remaining: int, gate: Any, records: list[Record]) -> ExperimentResult: ...
