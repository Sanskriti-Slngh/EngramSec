from __future__ import annotations

from pathlib import Path

import pytest

from agent1.costs import BudgetError, SpendingLedger
from agent1.providers import DecisionProvider
from agent1.schema import (
    ActionDescriptor,
    Control,
    EvidenceStatus,
    FormField,
    FormObservation,
    Transition,
    Observation,
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
