"""ACG export contract `acg/1` (frozen in Phase 0, before any resolver).

Identity never depends on display text: labels appear only in `labels` lists,
each with the evidence id it was copied from.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

SCHEMA = "acg/1"


class Status(StrEnum):
    HYPOTHESIZED = "hypothesized"
    OBSERVED = "observed"
    REPRODUCED = "reproduced"
    VERIFIED = "verified"
    REFUTED = "refuted"
    BLOCKED = "blocked"


STATUS_RANK = {Status.HYPOTHESIZED: 0, Status.OBSERVED: 1, Status.REPRODUCED: 2, Status.VERIFIED: 3}


class Label(BaseModel):
    text: str
    evidence_id: str


class Claim(BaseModel):
    id: str
    subject: str
    predicate: str
    object: str
    status: Status
    p: float | None = None            # posterior probability; None when no channel applies
    support: int = 0
    against: int = 0
    evidence_ids: list[str]
    sources: list[str]                # evidence kinds the claim rests on
    rule: str | None = None
    reason: str | None = None         # required when blocked, refuted or underdetermined


class Template(BaseModel):
    id: str
    route: str
    role: str
    observation_ids: list[str]
    view_state_ids: list[str] = Field(default_factory=list)


class ViewState(BaseModel):
    id: str
    template_id: str
    predicates: list[dict[str, Any]] = Field(default_factory=list)
    observation_ids: list[str]


class EntityType(BaseModel):
    id: str                           # E1, E2, ...
    positions: list[str]              # "route#segment" or "route?param" identifier positions
    label_candidates: list[Label] = Field(default_factory=list)


class EntityInstance(BaseModel):
    id: str
    type_id: str
    token: str
    observation_ids: list[str]
    evidence_ids: list[str]
    observed_paths: list[str]         # concrete paths, for local evaluation only


class Affordance(BaseModel):
    id: str
    template_id: str
    family: dict[str, Any]
    labels: list[Label] = Field(default_factory=list)
    status: Literal["bound", "unbound", "executed_no_effect", "failed", "blocked"]
    capability_ids: list[str] = Field(default_factory=list)
    action_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str]
    reason: str | None = None


class Operation(BaseModel):
    id: str
    channel: str
    method: str | None
    route: str
    params: list[str]
    encoding: str | None
    dispatch: dict[str, str] = Field(default_factory=dict)
    message_class: str | None = None
    evidence_ids: list[str]


class Effect(BaseModel):
    kind: str
    target: str


class BehavioralClass(BaseModel):
    name: str
    target: str
    rule: str
    status: Status
    evidence_ids: list[str]


class Binding(BaseModel):
    affordance_id: str
    action_ids: list[str]


class Capability(BaseModel):
    id: str
    role: str
    operation_ids: list[str]
    effects: list[Effect]
    entry_template_id: str | None = None
    status: Status
    p: float | None = None
    bindings: list[Binding]
    action_ids: list[str]
    reproduction_ids: list[str] = Field(default_factory=list)
    behavioral_class: BehavioralClass | None = None
    unidentified: bool = True
    reason: str | None = None
    evidence_ids: list[str]
    labels: list[Label] = Field(default_factory=list)


class LearnedPredicate(BaseModel):
    id: str
    template_id: str
    template_route: str
    affordance_id: str
    kind: str
    evidence_ids: list[str]


class Gap(BaseModel):
    kind: str
    detail: str
    count: int = 1


class ACGExport(BaseModel):
    schema_version: Literal["acg/1"] = SCHEMA
    application: str | None
    evidence_log_digest: str
    resolver_version: str
    synthetic_evidence: bool
    capture: dict[str, bool]
    templates: list[Template]
    view_states: list[ViewState]
    entity_types: list[EntityType]
    entity_instances: list[EntityInstance]
    affordances: list[Affordance]
    operations: list[Operation]
    capabilities: list[Capability]
    learned_predicates: list[LearnedPredicate]
    claims: list[Claim]
    gaps: list[Gap]
    summary: dict[str, Any]
