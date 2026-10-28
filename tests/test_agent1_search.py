from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from agent1.explorer import Explorer
from agent1.exporter import build_graph_a
from agent1.schema import ActionDescriptor, EvidenceStatus, FormField, FunctionalStatus, RunConfig
from tests.fixtures.get_search_app import start_search_server


@pytest.fixture(scope="module")
def search_server():
    server, thread = start_search_server()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def run_search(search_server, tmp_path: Path, path: str, *, transitions: int = 1):
    search_server.reset()
    artifact = Explorer(
        RunConfig(
            start_url=f"{search_server.base_url}/{path}",
            output_dir=tmp_path / path,
            policy="grouped",
            max_seconds=15,
            max_transitions=transitions,
            max_browser_actions=80,
            settle_ms=20,
            replay_reserve_fraction=0.55,
            search_probe_primary="alpha",
            search_probe_contrast="beta",
        ),
        Path(__file__).resolve().parents[1],
    ).run()
    return artifact, search_server.snapshot()


def search_workflow(artifact):
    candidates = [
        item
        for item in artifact.functional_workflows
        if any(
            replay.transition_id == item.transition_id
            and replay.verification_kind == "paired_search"
            for replay in artifact.replays
        )
    ]
    assert len(candidates) == 1
    return candidates[0]


def test_get_search_with_different_result_sets_is_verified(search_server, tmp_path: Path) -> None:
    artifact, _ = run_search(search_server, tmp_path, "search-success")
    workflow = search_workflow(artifact)
    replays = [item for item in artifact.replays if item.transition_id == workflow.transition_id]

    assert workflow.status == FunctionalStatus.VERIFIED
    assert all(workflow.verification_checks.values())
    assert artifact.metrics.functional_workflows_verified == 1
    assert len(replays) == 2
    assert all(item.status == EvidenceStatus.REPLAY_VALIDATED for item in replays)
    assert all(all(item.functional_checks.values()) for item in replays)
    assert all(len(item.verification_observation_ids) == 4 for item in replays)
    graph = build_graph_a(artifact)
    graph_workflow = next(
        item for item in graph["nodes"]["functional_workflows"] if item["id"] == workflow.id
    )
    graph_action = next(
        item
        for item in graph["nodes"]["actions_evidence"]
        if item["id"] == f"action_{workflow.transition_id}"
    )
    assert graph_workflow["status"] == FunctionalStatus.VERIFIED
    assert len(graph_workflow["replay_ids"]) == 2
    assert graph_action["workflow_path"]
    assert len(graph["replay_observations"]) == 8


def test_echo_only_search_is_navigation_valid_but_unresolved(search_server, tmp_path: Path) -> None:
    artifact, _ = run_search(search_server, tmp_path, "fake-search")
    workflow = search_workflow(artifact)
    replays = [item for item in artifact.replays if item.transition_id == workflow.transition_id]

    assert workflow.status == FunctionalStatus.UNRESOLVED
    assert artifact.metrics.functional_workflows_verified == 0
    assert len(replays) == 2
    assert all(item.status == EvidenceStatus.REPLAY_VALIDATED for item in replays)
    assert all(not item.functional_checks["primary_introduces_links"] for item in replays)


def test_hidden_search_uses_observed_toggle_and_exact_query_plans(
    search_server, tmp_path: Path
) -> None:
    artifact, events = run_search(search_server, tmp_path, "toggle-search", transitions=2)
    workflow = search_workflow(artifact)
    transition = next(item for item in artifact.transitions if item.id == workflow.transition_id)
    replays = [item for item in artifact.replays if item.transition_id == workflow.transition_id]
    counts = Counter(query.casefold() for _, query in events)

    assert workflow.status == FunctionalStatus.VERIFIED
    assert workflow.path_length == 2
    assert [item.label for item in transition.workflow_path] == ["toggle search", "Search"]
    assert transition.workflow_path[-1].input_plan_ref
    assert transition.action.label == "Search"
    assert len(replays) == 2
    assert all(len(item.input_plan_refs) == 2 for item in replays)
    assert counts["alpha"] >= 3  # exploration plus two primary replays
    assert counts["beta"] == 2
    assert "engramsec-test" not in counts


def test_missing_search_input_plan_is_not_regenerated(tmp_path: Path) -> None:
    explorer = Explorer(
        RunConfig(
            start_url="http://127.0.0.1:1/",
            output_dir=tmp_path / "missing-plan",
            search_probe_primary="alpha",
            search_probe_contrast="beta",
        ),
        Path(__file__).resolve().parents[1],
    )
    descriptor = ActionDescriptor(
        control_id="ctl_search",
        kind="form_submit",
        label="Search",
        role="button",
        css_path="button",
        target="http://127.0.0.1:1/search",
        method="GET",
        form_index=0,
        fields=[FormField(id="fld_query", name="query", input_type="search")],
        signature="search-signature",
        input_plan_ref="missing-protected-plan",
    )

    with pytest.raises(RuntimeError, match="missing from the protected cache"):
        explorer._resolve_form_plan(descriptor)
