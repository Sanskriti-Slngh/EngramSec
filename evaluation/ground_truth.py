"""Typed capability ground truth (GENERALIZATION_AND_EVALUATION_PLAN.md §3.1).

Evaluator-side only: the ACG never imports this module. Business names live in
`id` and `note`; scoring uses operations, effects, entry points and the closed
behavioral-class vocabulary.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

BEHAVIORAL_CLASSES = ("navigation", "instance_creation", "instance_removal", "instance_modification",
                      "collection_query", "instance_view", "client_view_change", "server_job_submission")
EFFECT_KINDS = ("navigated", "instance_appeared", "instance_disappeared", "instance_fields_changed",
                "collection_size_changed", "collection_membership_changed", "component_state_changed",
                "client_state_changed", "visual_region_changed", "message_received")


class Annotation(BaseModel):
    annotator: str
    independent: bool
    method: str
    sources: list[str]
    frozen_at: str


class Role(BaseModel):
    id: str
    cookie_names: list[str] = Field(default_factory=list)


class EntityType(BaseModel):
    id: str
    identity: list[str]          # route patterns whose {id}/{slug} position identifies an instance


class Operation(BaseModel):
    channel: Literal["http", "websocket_send"] = "http"
    method: str
    route: str                   # identifiers written as {id}; slugs as {slug}
    dispatch: dict[str, str] = Field(default_factory=dict)


class EntryPoint(BaseModel):
    kind: str | None = None
    label: str | None = None     # evaluator-side matching only
    target_route: str | None = None
    source_route: str | None = None


class Capability(BaseModel):
    id: str
    behavioral_class: str | None
    class_target: str | None = None
    class_observable_to_role: bool
    entity: str | None = None
    roles: list[str]
    operations: list[Operation] = Field(default_factory=list)
    no_operation_effect: str | None = None    # effect kind for capabilities without operations
    entry_points: list[EntryPoint]
    effect_risk: Literal["none", "client_only", "server_write", "destructive", "external"] = "none"
    in_scope: bool = True
    note: str = ""

    @model_validator(mode="after")
    def _check(self) -> "Capability":
        if self.behavioral_class is not None and self.behavioral_class not in BEHAVIORAL_CLASSES:
            raise ValueError(f"unknown behavioral class {self.behavioral_class}")
        if not self.operations and self.no_operation_effect not in EFFECT_KINDS:
            raise ValueError(f"{self.id}: capability without operations needs an observable effect kind")
        if self.behavioral_class is None and self.class_observable_to_role:
            raise ValueError(f"{self.id}: a null class cannot be observable")
        return self


class NonCapability(BaseModel):
    id: str
    entry_points: list[EntryPoint]
    reason: str


class GroundTruth(BaseModel):
    schema_version: Literal["capability-ground-truth/1"] = "capability-ground-truth/1"
    application: str
    annotation: Annotation
    capabilities_annotated: bool = True
    roles: list[Role]
    templates: list[str]
    entity_types: list[EntityType] = Field(default_factory=list)
    capabilities: list[Capability] = Field(default_factory=list)
    non_capabilities: list[NonCapability] = Field(default_factory=list)
    indistinguishable: list[list[str]] = Field(default_factory=list)
    equivalent_interfaces: list[str] = Field(default_factory=list)   # capability ids with ≥ 2 entry points


def load_ground_truth(path: Path) -> GroundTruth:
    return GroundTruth.model_validate(json.loads(path.read_text(encoding="utf-8")))
