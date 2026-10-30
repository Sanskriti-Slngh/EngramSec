from __future__ import annotations

from pathlib import Path

import pytest

from agent1.costs import BudgetError, SpendingLedger
from agent1.explorer import Explorer, request_structure
from agent1.providers import DecisionProvider
from agent1.schema import (
    ActionDescriptor,
    Control,
    EvidenceStatus,
    FormField,
    FormObservation,
    Transition,
    Observation,
    RunConfig,
    utc_now,
)
from agent1.state import (
    content_fingerprint,
    control_signature,
    feature_action_signature,
    feature_key,
    signatures,
)


def control(label: str = "Open", target: str = "http://127.0.0.1:8000/item/1") -> Control:
    signature = control_signature("link", "link", label, target, None)
    return Control(
        id="ctl_test",
        kind="link",
        label=label,
        css_path="a",
        role="link",
        target=target,
        signature=signature,
    )


def test_observed_transition_requires_result_evidence() -> None:
    item = control()
    action = ActionDescriptor(control_id=item.id, **item.model_dump(exclude={"id", "safe", "skip_reason"}))
    with pytest.raises(ValueError, match="observed transitions require"):
        Transition(
            id="tr_missing",
            source_observation_id="obs_source",
            source_state_signature="raw",
            source_group_signature="group",
            action=action,
            status=EvidenceStatus.OBSERVED,
            run_id="run",
        )


def test_failed_transition_requires_error() -> None:
    item = control()
    action = ActionDescriptor(control_id=item.id, **item.model_dump(exclude={"id", "safe", "skip_reason"}))
    with pytest.raises(ValueError, match="failed transitions require"):
        Transition(
            id="tr_missing_error",
            source_observation_id="obs_source",
            source_state_signature="raw",
            source_group_signature="group",
            action=action,
            status=EvidenceStatus.FAILED,
            run_id="run",
        )


def test_state_grouping_keeps_session_and_form_differences() -> None:
    base_control = control()
    form_a = FormObservation(
        index=0,
        method="GET",
        action="http://127.0.0.1:8000/search",
        fields=[FormField(name="q", input_type="search")],
    )
    form_b = FormObservation(
        index=0,
        method="GET",
        action="http://127.0.0.1:8000/search",
        fields=[FormField(name="category", input_type="select")],
    )
    _, group_a, _ = signatures(
        url="http://127.0.0.1:8000/item/1",
        title="Item 1",
        controls=[base_control],
        forms=[form_a],
        session_context="anonymous",
    )
    _, group_same_shape, _ = signatures(
        url="http://127.0.0.1:8000/item/2",
        title="Item 2",
        controls=[base_control],
        forms=[form_a],
        session_context="anonymous",
    )
    _, group_different_form, _ = signatures(
        url="http://127.0.0.1:8000/item/2",
        title="Item 2",
        controls=[base_control],
        forms=[form_b],
        session_context="anonymous",
    )
    _, group_different_session, _ = signatures(
        url="http://127.0.0.1:8000/item/2",
        title="Item 2",
        controls=[base_control],
        forms=[form_a],
        session_context="account:demo",
    )
    assert group_a == group_same_shape
    assert group_a != group_different_form
    assert group_a != group_different_session


def test_spending_ledger_reserves_retries_and_outstanding_requests(tmp_path: Path) -> None:
    ledger = SpendingLedger(tmp_path / "ledger.json")
    ledger.reserve("request-1-attempt-1", 10.0)
    ledger.reserve("request-1-attempt-2", 7.5)
    snapshot = ledger.snapshot()
    assert snapshot["reserved_usd"] == 17.5
    assert snapshot["outstanding_requests"] == 2
    with pytest.raises(BudgetError, match=r"\$18"):
        ledger.reserve("request-2", 0.6)
    ledger.commit("request-1-attempt-1", 4.0)
    ledger.release("request-1-attempt-2")
    snapshot = ledger.snapshot()
    assert snapshot["spent_usd"] == 4.0
    assert snapshot["outstanding_requests"] == 0


def test_spending_ledger_rejects_unreserved_or_over_actual(tmp_path: Path) -> None:
    ledger = SpendingLedger(tmp_path / "ledger.json")
    with pytest.raises(BudgetError, match="not reserved"):
        ledger.commit("unknown", 0.1)
    ledger.reserve("request", 0.5)
    with pytest.raises(BudgetError, match="exceeds"):
        ledger.commit("request", 0.6)


def test_model_decision_ids_are_limited_to_current_compact_observation() -> None:
    controls = [
        control(label=f"Item {index}", target=f"http://127.0.0.1:8000/item/{index}").model_copy(
            update={"id": f"ctl_{index}"}
        )
        for index in range(20)
    ]
    raw, group, route = signatures(
        url="http://127.0.0.1:8000/",
        title="Home",
        controls=controls,
        forms=[],
        session_context="anonymous",
    )
    observation = Observation(
        id="obs",
        sequence=1,
        url="http://127.0.0.1:8000/",
        title="Home",
        text_excerpt="",
        controls=controls,
        forms=[],
        state_signature=raw,
        group_signature=group,
        session_context="anonymous",
        route_pattern=route,
    )
    payload = DecisionProvider.compact_payload(observation)
    allowed = {item["id"] for item in payload["controls"]}
    assert len(allowed) == 12
    decision = DecisionProvider.validate(
        {"ordered_control_ids": [next(iter(allowed)), "ctl_not_current"]},
        observation,
        allowed,
    )
    assert decision.ordered_control_ids == [next(iter(allowed))]


def test_repeated_navigation_feature_identity_is_source_independent() -> None:
    home = control(label="Home", target="http://127.0.0.1:8000/")
    logo = control(label="Site logo", target="http://127.0.0.1:8000/")
    assert feature_key(feature_action_signature(home)) == feature_key(feature_action_signature(logo))


def test_form_feature_identity_includes_field_shape() -> None:
    item = control().model_copy(
        update={
            "kind": "form_submit",
            "role": "button",
            "method": "POST",
            "fields": [FormField(name="email", input_type="email", required=True)],
        }
    )
    other = item.model_copy(
        update={"fields": [FormField(name="query", input_type="search", required=True)]}
    )
    assert feature_action_signature(item) != feature_action_signature(other)


def test_content_fingerprint_ignores_runtime_duration_but_not_result_content() -> None:
    assert content_fingerprint("Result Alpha 0.301827s") == content_fingerprint(
        "Result Alpha 0.182605s"
    )
    assert content_fingerprint("Result Alpha") != content_fingerprint("Result Beta")


def test_model_form_values_are_limited_to_observed_field_ids() -> None:
    proposal = DecisionProvider.validate_form(
        {"values": {"fld_current": "ordinary", "fld_invented": "ignored"}},
        {"fld_current"},
    )
    assert proposal.values == {"fld_current": "ordinary"}
    assert proposal.rejected_field_ids == ["fld_invented"]


def test_coverage_policy_prioritizes_new_branch_over_repeated_chrome(tmp_path: Path) -> None:
    explorer = Explorer(
        RunConfig(
            start_url="http://127.0.0.1:8000/",
            output_dir=tmp_path,
            policy="coverage",
        ),
        Path(__file__).resolve().parents[1],
    )
    shared = control(label="Home", target="http://127.0.0.1:8000/")
    first_raw, first_group, first_route = signatures(
        url="http://127.0.0.1:8000/one",
        title="One",
        controls=[shared],
        forms=[],
        session_context="anonymous",
    )
    first = Observation(
        id="obs_one", sequence=1, url="http://127.0.0.1:8000/one", title="One",
        text_excerpt="", controls=[shared], forms=[], state_signature=first_raw,
        group_signature=first_group, session_context="anonymous", route_pattern=first_route,
    )
    explorer._enqueue(first, [])
    explorer.frontier.clear()  # Simulate the first advertised action having been consumed.
    repeated = shared.model_copy(update={"id": "ctl_home_again", "css_path": "#home"})
    branch = control(label="Open reports", target="http://127.0.0.1:8000/reports").model_copy(
        update={"id": "ctl_reports", "css_path": "#reports"}
    )
    second_raw, second_group, second_route = signatures(
        url="http://127.0.0.1:8000/two", title="Two", controls=[repeated, branch], forms=[],
        session_context="anonymous",
    )
    second = Observation(
        id="obs_two", sequence=2, url="http://127.0.0.1:8000/two", title="Two",
        text_excerpt="", controls=[repeated, branch], forms=[], state_signature=second_raw,
        group_signature=second_group, session_context="anonymous", route_pattern=second_route,
    )
    explorer._enqueue(second, [])

    assert explorer.frontier[0].action.label == "Open reports"
    assert explorer.frontier[0].priority > next(
        item.priority for item in explorer.frontier if item.action.label == "Home"
    )


@pytest.mark.parametrize(
    ("method", "content_type", "body", "expected", "encoding"),
    [
        ("POST", "application/x-www-form-urlencoded", "member_code=do-not-store", ["member_code", "view"], "form"),
        ("POST", "application/json", '{"query":"do-not-store","limit":5}', ["limit", "query", "view"], "json"),
    ],
)
def test_request_structure_records_names_without_values(
    method: str, content_type: str, body: str, expected: list[str], encoding: str
) -> None:
    names, actual_encoding = request_structure(
        method,
        "http://127.0.0.1/api?view=private-value",
        {"content-type": content_type},
        body,
    )
    assert names == expected
    assert actual_encoding == encoding
    assert "do-not-store" not in repr((names, actual_encoding))
    assert "private-value" not in repr((names, actual_encoding))


def test_adaptive_budget_reserves_actions_for_distinct_replays(tmp_path: Path) -> None:
    config = RunConfig(
        start_url="http://127.0.0.1:8000/",
        output_dir=tmp_path / "adaptive-budget",
        max_seconds=100,
        max_browser_actions=100,
        replay_reserve_fraction=0.3,
        budget_allocation_strategy="adaptive",
    )
    explorer = Explorer(config, Path(__file__).resolve().parents[1])
    assert explorer._current_replay_reserve() == (0.0, 0)

    action = ActionDescriptor.model_construct(
        control_id="ctl", kind="link", label="Open", role="link", css_path="a",
        signature="sig", interaction="click",
    )
    observation = Observation.model_construct(
        id="obs", url="http://127.0.0.1:8000/record/1", group_signature="group",
    )
    transition = Transition.model_construct(
        id="tr", result_observation_id="obs", status=EvidenceStatus.OBSERVED,
        action=action, workflow_path=[action],
    )
    explorer.artifact.observations.append(observation)
    explorer.artifact.transitions.append(transition)
    reserve_fraction, action_reserve = explorer._current_replay_reserve()
    assert reserve_fraction == 0.05
    assert action_reserve == 2
    assert explorer._exploration_deadline() == pytest.approx(95)
    assert not explorer._fits_exploration_action_budget(99)


def test_readiness_strategy_keeps_fixed_default_and_allows_adaptive_opt_in(tmp_path: Path) -> None:
    config = RunConfig(
        start_url="http://127.0.0.1:8000/",
        output_dir=tmp_path / "adaptive-readiness-default",
        robust_readiness=True,
    )
    assert config.readiness_strategy == "fixed"
    assert config.model_copy(update={"readiness_strategy": "adaptive"}).readiness_strategy == "adaptive"
