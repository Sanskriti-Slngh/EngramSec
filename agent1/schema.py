from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

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
    policy: Literal[
        "exact",
        "grouped",
        "coverage",
        "breadth",
        "multidimensional",
        "hierarchical",
        "selective_model",
        "model_all",
    ] = "grouped"
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
    robust_readiness: bool = False
    readiness_timeout_ms: int = Field(default=2_500, ge=250, le=15_000)
    readiness_poll_ms: int = Field(default=100, ge=25, le=1_000)
    origin_aliases: list[str] = Field(default_factory=list)
    exploration_mode: Literal["fresh", "persistent"] = "fresh"
    interaction_profile: Literal["basic", "extended"] = "basic"
    hybrid_link_discovery: bool = False
    idle_page_wait_ms: int = Field(default=1_600, ge=250, le=5_000)
    passive_page_wait_ms: int = Field(default=200, ge=50, le=5_000)
    readiness_strategy: Literal["fixed", "adaptive"] = "fixed"
    typed_resource_spider: bool = False
    max_resource_fetches: int = Field(default=100, ge=0, le=2_000)
    max_resource_fetches_per_observation: int = Field(default=10, ge=1, le=200)
    max_resource_document_fetches: int | None = Field(default=None, ge=0, le=2_000)
    max_resource_script_fetches: int | None = Field(default=None, ge=0, le=2_000)
    max_resource_stylesheet_fetches: int | None = Field(default=None, ge=0, le=2_000)
    max_resource_asset_fetches: int | None = Field(default=None, ge=0, le=2_000)
    max_resource_depth: int = Field(default=3, ge=0, le=10)
    max_resource_body_bytes: int = Field(default=1_000_000, ge=16_384, le=4_000_000)
    resource_frontier_policy: Literal["fifo", "route_diverse", "marginal_value", "random"] = "fifo"
    resource_random_seed: int = Field(default=0, ge=0, le=2_147_483_647)
    javascript_reference_parser: Literal["legacy_regex", "ast"] = "ast"
    share_resource_frontier: bool = True
    budget_allocation_strategy: Literal["fixed", "adaptive"] = "fixed"
    replay_policy: Literal["shallow", "diverse"] = "shallow"
    state_reuse: Literal["root", "prefix"] = "root"
    # Optional discovery changes (defaults keep the frozen baseline behavior).
    resource_allocation: Literal["class_caps", "shared_http"] = "class_caps"
    passive_document_http_reserve: int | None = Field(default=None, ge=0, le=100_000)
    max_passive_document_fetches: int | None = Field(default=None, ge=0, le=100_000)
    html_extraction: Literal["baseline", "extended", "standards"] = "baseline"
    max_speculative_fetches: int = Field(default=0, ge=0, le=10_000)
    response_body_reader: Literal["content_length", "bounded_stream"] = "content_length"
    resource_frontier_model: Literal["legacy", "persistent"] = "legacy"
    passive_document_max_depth: int | None = Field(default=None, ge=1, le=12)
    budget_aware_deepening: bool = False
    hard_max_resource_depth: int = Field(default=8, ge=1, le=12)
    zap_evidence_path: Path | None = None
    zap_source_origin: str | None = None
    max_total_http_requests: int | None = Field(default=None, ge=1, le=100_000)
    # Passive (bounded-reader) fetches apply Set-Cookie to the browser context.
    # False reproduces the b4a9a40 semantics (cookies sent, updates dropped).
    passive_cookie_sync: bool = True
    # Share of the total HTTP budget held back for independent replay
    # (0 reproduces the earlier behavior, where exploration could spend it all).
    http_verification_reserve_fraction: float = Field(default=0.0, ge=0.0, le=0.8)
    # Opt-in Chromium DevTools listener observation (agent1/listeners.py):
    #   observe: listener-bearing elements become candidate controls; handler
    #            revisions are recorded as evidence only;
    #   revisit: additionally, a control whose handler changed is re-explored.
    runtime_listener_observation: Literal["off", "observe", "revisit"] = "off"
    max_listener_nodes: int = Field(default=300, ge=1, le=5_000)
    max_listener_candidates: int = Field(default=12, ge=0, le=200)
    listener_family_limit: int = Field(default=2, ge=1, le=50)

    @model_validator(mode="after")
    def paired_search_probes(self) -> "RunConfig":
        if (self.zap_evidence_path is None) != (self.zap_source_origin is None):
            raise ValueError("ZAP evidence and explicit source origin must be supplied together")
        if self.resource_allocation == "shared_http" and (
                self.max_total_http_requests is None or not self.typed_resource_spider):
            raise ValueError("shared_http allocation requires the typed-resource spider and a total HTTP budget")
        if (self.passive_document_max_depth is not None or self.budget_aware_deepening) \
                and self.resource_frontier_model != "persistent":
            raise ValueError("depth alternatives require the persistent resource frontier")
        if self.max_speculative_fetches and self.max_total_http_requests is None:
            raise ValueError("speculative fetches require a total HTTP budget")
        if self.zap_evidence_path and (not self.typed_resource_spider or not self.share_resource_frontier):
            raise ValueError("ZAP seeds require the shared typed-resource spider")
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
        normalized_aliases: list[str] = []
        for value in self.origin_aliases:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
            ):
                raise ValueError(
                    "origin aliases must be explicit HTTP(S) loopback origins without credentials or paths"
                )
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            host = f"[{parsed.hostname}]" if ":" in (parsed.hostname or "") else parsed.hostname
            normalized_aliases.append(f"{parsed.scheme.lower()}://{host}:{port}")
        self.origin_aliases = sorted(set(normalized_aliases))
        return self


class ReadinessSample(BaseModel):
    elapsed_ms: int
    document_state: str
    aria_busy_count: int
    enabled_control_count: int
    disabled_control_count: int
    control_fingerprint: str
    main_enabled_control_count: int = 0
    mutation_count: int = 0
    script_count: int = 0
    meta_refresh_delay_ms: int | None = None


class ReadinessEvidence(BaseModel):
    status: Literal["not_recorded", "initializing", "usable", "blocked", "timeout"] = (
        "not_recorded"
    )
    duration_ms: int = 0
    http_status: int | None = None
    samples: list[ReadinessSample] = Field(default_factory=list)


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
    frame_index: int = 0
    frame_url: str = ""


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
    interaction: Literal[
        "click",
        "navigate",
        "hover",
        "focus",
        "key_enter",
        "double_click",
        "context_menu",
        "press_hold",
        "scroll_viewport",
        "scroll_container",
        "toggle",
        "select_option",
    ] = "click"
    component: str = "document"
    frame_index: int = 0
    frame_url: str = ""
    # "snapshot": recognized by DOM semantics; "observed_listener": a direct
    # click-family listener reported by Chromium DevTools.
    provenance: Literal["snapshot", "observed_listener"] = "snapshot"
    # Evidence-derived behavior revision: set only when a handler change on this
    # element was observed within the same document (revisit mode).
    behavior_revision: str | None = None
    listener_evidence: dict[str, Any] | None = None


class ListenerEvidence(BaseModel):
    """Bounded DevTools listener observation attached to one browser observation."""
    supported: bool = True
    document_token: str = ""
    caused_by_action: str | None = None
    listener_nodes: int = 0
    described_nodes: int = 0
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    revisions: list[dict[str, Any]] = Field(default_factory=list)
    active_revisions: list[dict[str, str]] = Field(default_factory=list)
    skipped: dict[str, int] = Field(default_factory=dict)
    skipped_examples: list[dict[str, Any]] = Field(default_factory=list)
    delegation_hosts: int = 0
    window_click_listeners: int = 0
    elapsed_ms: float = 0.0
    cdp_calls: int = 0
    error: str | None = None


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
    session_markers: dict[str, list[str]] = Field(default_factory=dict)
    route_pattern: str
    instance_facts: dict[str, Any] = Field(default_factory=dict)
    readiness: ReadinessEvidence = Field(default_factory=ReadinessEvidence)
    listener_evidence: ListenerEvidence | None = None
    # Equal to group_signature unless evidence shows a changed handler behind
    # the same visible DOM; then it also names the active behavior revisions.
    behavior_signature: str = ""


class NetworkEvent(BaseModel):
    method: str
    url: str
    status: int | None = None
    resource_type: str | None = None
    failure: str | None = None
    parameter_names: list[str] = Field(default_factory=list)
    body_encoding: str | None = None
    elapsed_ms: int | None = None


class ResourceEvidence(BaseModel):
    evidence_id: str = ""
    url: str | None
    kind: Literal["navigation", "asset", "api", "form_action", "ping", "security_report"]
    source_type: str
    source_url: str
    source: str
    relation: str = ""
    depth: int = 0
    status: Literal["discovered", "fetched", "failed", "out_of_scope", "budget_limited", "class_budget_limited", "depth_limited", "sensitive_reference", "unresolved_candidate"] = "discovered"
    queue_decision: str = "admitted"
    confidence: str = "observed_literal"
    expression_fingerprint: str | None = None
    candidate_prefix: str | None = None
    elapsed_ms: int | None = None
    http_status: int | None = None
    content_type: str | None = None
    new_references: int | None = None
    candidate_class: str | None = None
    response_reference_count: int | None = None
    queued_references: int | None = None
    excluded_references: int | None = None
    redirected_to: str | None = None
    error: str | None = None
    channel: str | None = None
    method: str | None = None
    body_status: str | None = None
    body_bytes: int | None = None
    wire_bytes: int | None = None
    # Names only (never values) of the cookies sent and set on a passive fetch.
    session_cookie_names: list[str] | None = None
    set_cookie_names: list[str] | None = None
    cookie_updates: dict[str, int] | None = None


class ExternalDiscoveryEvidence(BaseModel):
    id: str
    engine: str
    run_id: str
    source_origin: str
    source_record_id: str
    export_digest: str
    mapped_url: str
    method: str
    http_status: int | None = None
    parameter_names: list[str] = Field(default_factory=list)
    status: Literal["external_response", "external_candidate"]
    session_context: str = "unknown"


class NavigationEvidence(BaseModel):
    id: str
    reason: Literal["initial", "frontier_restore", "persistent_restore", "replay", "history_return"]
    url: str
    readiness: ReadinessEvidence = Field(default_factory=ReadinessEvidence)
    network: list[NetworkEvent] = Field(default_factory=list)
    recorded_at: str = Field(default_factory=utc_now)


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
    interaction: str = "click"
    component: str = "document"
    frame_index: int = 0
    frame_url: str = ""
    provenance: str = "snapshot"
    behavior_revision: str | None = None


class FormAttempt(BaseModel):
    attempt_index: int
    input_references: list[InputReference] = Field(default_factory=list)
    outcome_signals: list[OutcomeSignal] = Field(default_factory=list)
    status: FunctionalStatus
    input_plan_ref: str | None = None


class PrerequisiteStepEvidence(BaseModel):
    step_index: int = Field(ge=0)
    action_signature: str
    action_label: str
    network: list[NetworkEvent] = Field(default_factory=list)


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
    restoration_attempted: bool = False
    reused_prefix_steps: int = Field(default=0, ge=0)
    prerequisite_network: list[PrerequisiteStepEvidence] = Field(default_factory=list)
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
    network: list[NetworkEvent] = Field(default_factory=list)
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
    verification_checks: dict[str, bool] = Field(default_factory=dict)
    path_length: int
    action_label: str
    status: FunctionalStatus
    outcome_signal_fingerprints: list[str] = Field(default_factory=list)
    source_observation_id: str
    result_observation_id: str | None = None


class ConnectionEvidence(BaseModel):
    id: str
    claim_type: Literal[
        "advertised_control", "source_action", "action_result", "replay",
        "prerequisite_network", "resource_reference", "external_observation",
        "listener_candidate", "handler_revision",
    ]
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
    root_reloads: int = 0
    restoration_actions: int = 0
    live_state_reuses: int = 0
    live_state_stale: int = 0
    startup_readiness_failures: int = 0
    navigation_network_events_recorded: int = 0
    ineffective_transitions: int = 0
    duplicate_controls_suppressed: int = 0
    static_navigation_actions: int = 0
    dynamic_interaction_actions: int = 0
    frame_observations: int = 0
    popup_navigations: int = 0
    resource_references_discovered: int = 0
    resource_fetches_attempted: int = 0
    resource_fetches_succeeded: int = 0
    resource_fetch_failures: int = 0
    resource_fetch_budget_exhausted: int = 0
    resource_fetch_class_budget_exhausted: int = 0
    resource_new_references: int = 0
    resource_responses_with_body: int = 0
    resource_references_extracted: int = 0
    resource_references_queued: int = 0
    resource_references_excluded: int = 0
    resource_unresolved_candidates: int = 0
    passive_readiness_wait_ms: int = 0
    interactive_readiness_wait_ms: int = 0
    observed_http_requests: int = 0
    external_discovery_records: int = 0
    external_discovery_rejected: int = 0
    external_request_upper_bound: int = 0
    external_elapsed_seconds: float = 0.0
    total_http_budget_used: int = 0
    total_http_budget_blocked: int = 0
    http_redirect_budget_overrun: int = 0
    http_redirect_scope_violations: int = 0
    http_budget_by_source: dict[str, int] = Field(default_factory=dict)
    discovery_root_reloads: int = 0
    verification_root_reloads: int = 0
    prefix_state_reuses: int = 0
    root_reloads_avoided: int = 0
    history_returns: int = 0
    history_return_attempts: int = 0
    history_return_rejected: int = 0
    passive_document_fetches: int = 0
    speculative_fetches: int = 0
    observed_only_request_surfaces: int = 0
    effective_resource_budgets: dict[str, int | float | str | None] = Field(default_factory=dict)
    browser_body_status: dict[str, int] = Field(default_factory=dict)
    spider_body_status: dict[str, int] = Field(default_factory=dict)
    passive_wire_bytes: int = 0
    replays_untested_http_budget: int = 0
    passive_cookie_updates: dict[str, int] = Field(default_factory=dict)
    python_peak_rss_mb: float = 0.0
    listener_observations: int = 0
    listener_observation_errors: int = 0
    listener_observation_ms: float = 0.0
    listener_cdp_calls: int = 0
    listener_candidates_distinct: int = 0
    listener_candidates_executed: int = 0
    listener_skipped: dict[str, int] = Field(default_factory=dict)
    handler_revisions_observed: int = 0
    handler_revisits_executed: int = 0
    behavior_divergent_groups: int = 0


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
    navigation_evidence: list[NavigationEvidence] = Field(default_factory=list)
    resource_evidence: list[ResourceEvidence] = Field(default_factory=list)
    external_discoveries: list[ExternalDiscoveryEvidence] = Field(default_factory=list)
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
