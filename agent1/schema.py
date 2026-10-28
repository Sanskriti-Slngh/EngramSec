from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvidenceStatus(StrEnum):
    ADVERTISED = "advertised"
    OBSERVED = "observed"
    REPLAY_VALIDATED = "replay_validated"
    FAILED = "failed"
    UNRESOLVED = "unresolved"
    NOT_TESTED = "not_tested"


class FunctionalStatus(StrEnum):
    VERIFIED = "functional_verified"
    VALIDATION_FAILURE = "validation_failure"
    NAVIGATION_ONLY = "navigation_only"
    UNRESOLVED = "unresolved"
    NOT_TESTED = "not_tested"
    FAILED = "failed"


class RunConfig(BaseModel):
    start_url: str
    output_dir: Path
    policy: Literal["exact", "grouped", "selective_model", "model_all"] = "grouped"
    max_seconds: float = Field(default=60.0, gt=0)
    max_transitions: int = Field(default=20, ge=1)
    max_browser_actions: int = Field(default=80, ge=1)
    headless: bool = True
    action_timeout_ms: int = Field(default=5_000, ge=250)
    settle_ms: int = Field(default=350, ge=0)
    context_label: str = "anonymous"
    allow_post_forms: bool = False
    model_provider: Literal["none", "ollama", "groq", "openai"] = "none"
    model_name: str | None = None
    paid_calls_enabled: bool = False
    paid_budget_usd: float = Field(default=20.0, ge=0, le=20.0)
    paid_stop_usd: float = Field(default=18.0, ge=0, le=18.0)
    replay_reserve_fraction: float = Field(default=0.30, ge=0, le=0.8)
    run_id: str | None = None
    resume_from: Path | None = None
    focus_query: str | None = None
    model_form_assistance: bool = False
    max_form_retries: int = Field(default=1, ge=0, le=2)
    search_probe_primary: str | None = Field(default=None, max_length=80)
    search_probe_contrast: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def paired_search_probes(self) -> "RunConfig":
        probes = (self.search_probe_primary, self.search_probe_contrast)
        if (probes[0] is None) != (probes[1] is None):
            raise ValueError("search probes must be configured as a pair")
        if probes[0] is not None:
            cleaned = tuple(item.strip() for item in probes if item is not None)
            if not all(cleaned) or cleaned[0].casefold() == cleaned[1].casefold():
                raise ValueError("search probes must be non-empty and distinct")
            if any(any(ord(char) < 32 for char in item) for item in cleaned):
                raise ValueError("search probes cannot contain control characters")
            self.search_probe_primary, self.search_probe_contrast = cleaned
        return self


class InputReference(BaseModel):
    field_name: str
    input_type: str
    value_ref: str
    protected: bool = True


class FormField(BaseModel):
    id: str = ""
    name: str
    input_type: str
    label: str = ""
    required: bool = False
    css_path: str = ""
    placeholder: str = ""
    pattern: str = ""
    min_length: int | None = None
    max_length: int | None = None
    min_value: str | None = None
    max_value: str | None = None
    step: str | None = None
    description: str = ""
    options: list[dict[str, str]] = Field(default_factory=list)


class OutcomeSignal(BaseModel):
    kind: Literal["success", "validation_error", "result", "status", "setup", "unknown"]
    text_excerpt: str
    fingerprint: str
    source: str


class FormObservation(BaseModel):
    index: int
    method: str
    action: str
    fields: list[FormField] = Field(default_factory=list)
    submit_labels: list[str] = Field(default_factory=list)


class Control(BaseModel):
    id: str
    kind: Literal["link", "button", "form_submit"]
    label: str
    css_path: str
    role: str
    target: str | None = None
    method: str | None = None
    form_index: int | None = None
    fields: list[FormField] = Field(default_factory=list)
    safe: bool = True
    skip_reason: str | None = None
    signature: str


class Observation(BaseModel):
    id: str
    sequence: int
    recorded_at: str = Field(default_factory=utc_now)
    url: str
    title: str
    text_excerpt: str
    meaningful_text: str = ""
    content_fingerprint: str = ""
    outcome_signals: list[OutcomeSignal] = Field(default_factory=list)
    controls: list[Control]
    forms: list[FormObservation]
    state_signature: str
    group_signature: str
    session_context: str
    route_pattern: str
    instance_facts: dict[str, Any] = Field(default_factory=dict)


class NetworkEvent(BaseModel):
    method: str
    url: str
    status: int | None = None
    resource_type: str | None = None
    failure: str | None = None


class ActionDescriptor(BaseModel):
    control_id: str
    kind: str
    label: str
    role: str
    css_path: str
    target: str | None = None
    method: str | None = None
    form_index: int | None = None
    fields: list[FormField] = Field(default_factory=list)
    signature: str
    input_plan_ref: str | None = None


class FormAttempt(BaseModel):
    attempt_index: int
    input_references: list[InputReference] = Field(default_factory=list)
    outcome_signals: list[OutcomeSignal] = Field(default_factory=list)
    status: FunctionalStatus
    input_plan_ref: str | None = None


class Transition(BaseModel):
    id: str
    source_observation_id: str
    source_state_signature: str
    source_group_signature: str
    action: ActionDescriptor
    workflow_path: list[ActionDescriptor] = Field(default_factory=list)
    input_references: list[InputReference] = Field(default_factory=list)
    form_attempts: list[FormAttempt] = Field(default_factory=list)
    result_observation_id: str | None = None
    result_state_signature: str | None = None
    result_group_signature: str | None = None
    status: EvidenceStatus
    network: list[NetworkEvent] = Field(default_factory=list)
    dialogs: list[dict[str, str]] = Field(default_factory=list)
    error: str | None = None
    started_at: str = Field(default_factory=utc_now)
    ended_at: str | None = None
    run_id: str

    @model_validator(mode="after")
    def evidence_is_complete(self) -> "Transition":
        if self.status in {EvidenceStatus.OBSERVED, EvidenceStatus.REPLAY_VALIDATED}:
            required = (
                self.source_observation_id,
                self.result_observation_id,
                self.result_state_signature,
                self.ended_at,
            )
            if not all(required):
                raise ValueError("observed transitions require source, action, result, and end evidence")
        if self.status == EvidenceStatus.FAILED and not self.error:
            raise ValueError("failed transitions require an error")
        return self


class Advertisement(BaseModel):
    source_observation_id: str
    source_group_signature: str
    control: Control
    status: EvidenceStatus = EvidenceStatus.ADVERTISED


class ReplayResult(BaseModel):
    id: str
    transition_id: str
    path_length: int
    status: EvidenceStatus
    expected_group_signature: str
    actual_group_signature: str | None = None
    actual_observation_id: str | None = None
    outcome_checks: dict[str, bool] = Field(default_factory=dict)
    functional_checks: dict[str, bool] = Field(default_factory=dict)
    verification_kind: Literal["standard", "paired_search"] = "standard"
    verification_observation_ids: list[str] = Field(default_factory=list)
    verification_evidence: dict[str, Any] = Field(default_factory=dict)
    input_plan_refs: list[str] = Field(default_factory=list)
    functional_status: FunctionalStatus = FunctionalStatus.NOT_TESTED
    browser_actions: int = 0
    error: str | None = None
    started_at: str = Field(default_factory=utc_now)
    ended_at: str = Field(default_factory=utc_now)


class Feature(BaseModel):
    id: str
    description: str
    action_signature: str
    source_group_signature: str
    source_group_signatures: list[str] = Field(default_factory=list)
    target_group_signature: str
    target_group_signatures: list[str] = Field(default_factory=list)
    evidence_transition_ids: list[str]
    replay_ids: list[str] = Field(default_factory=list)
    status: EvidenceStatus
    validated_transition_ids: list[str] = Field(default_factory=list)
    failed_transition_ids: list[str] = Field(default_factory=list)
    untested_transition_ids: list[str] = Field(default_factory=list)


class FunctionalWorkflow(BaseModel):
    id: str
    transition_id: str
    replay_id: str | None = None
    replay_ids: list[str] = Field(default_factory=list)
    path_length: int
    action_label: str
    status: FunctionalStatus
    outcome_signal_fingerprints: list[str] = Field(default_factory=list)
    source_observation_id: str
    result_observation_id: str | None = None


class ConnectionEvidence(BaseModel):
    id: str
    claim_type: Literal["advertised_control", "source_action", "action_result", "replay"]
    subject_id: str
    complete: bool
    evidence_ids: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class FrontierItem(BaseModel):
    source_observation_id: str
    expected_source_signature: str
    expected_source_group: str
    path: list[ActionDescriptor]
    action: ActionDescriptor
    priority: float = 0.0


class RunMetrics(BaseModel):
    elapsed_seconds: float = 0.0
    browser_actions: int = 0
    navigation_requests: int = 0
    network_events_recorded: int = 0
    transitions_attempted: int = 0
    transitions_observed: int = 0
    transitions_failed: int = 0
    advertised_unexecuted: int = 0
    raw_states: int = 0
    grouped_states: int = 0
    redundant_states: int = 0
    incorrect_state_merges: int = 0
    distinct_validated_feature_workflows: int = 0
    replay_success_numerator: int = 0
    replay_success_denominator: int = 0
    unsupported_connections: int = 0
    replay_attempts: int = 0
    replay_navigation_successes: int = 0
    replay_failures: int = 0
    replay_untested_paths: int = 0
    navigation_categories_replay_validated: int = 0
    functional_workflows_verified: int = 0
    functional_validation_failures: int = 0
    functional_unresolved: int = 0
    graph_connections_total: int = 0
    graph_connections_complete: int = 0
    graph_connections_missing_evidence: int = 0
    model_calls: int = 0
    model_failures: int = 0
    model_input_tokens: int = 0
    model_output_tokens: int = 0
    monetary_cost_usd: float = 0.0
    progress: list[dict[str, float | int]] = Field(default_factory=list)


class RunArtifact(BaseModel):
    schema_version: str = "1.1"
    run_id: str
    code_revision: str
    config: dict[str, Any]
    started_at: str
    ended_at: str | None = None
    observations: list[Observation] = Field(default_factory=list)
    advertisements: list[Advertisement] = Field(default_factory=list)
    transitions: list[Transition] = Field(default_factory=list)
    replays: list[ReplayResult] = Field(default_factory=list)
    replay_observations: list[Observation] = Field(default_factory=list)
    features: list[Feature] = Field(default_factory=list)
    functional_workflows: list[FunctionalWorkflow] = Field(default_factory=list)
    connection_evidence: list[ConnectionEvidence] = Field(default_factory=list)
    state_groups: dict[str, list[str]] = Field(default_factory=dict)
    return_paths: dict[str, list[ActionDescriptor]] = Field(default_factory=dict)
    metrics: RunMetrics = Field(default_factory=RunMetrics)
    notes: list[str] = Field(default_factory=list)


class Checkpoint(BaseModel):
    schema_version: str = "1.0"
    artifact: RunArtifact
    frontier: list[FrontierItem]
    tried: list[str]
    saved_at: str = Field(default_factory=utc_now)
