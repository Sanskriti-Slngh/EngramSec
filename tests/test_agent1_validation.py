from __future__ import annotations

from pathlib import Path

import pytest

from agent1.explorer import Explorer
from agent1.schema import EvidenceStatus, FunctionalStatus, RunConfig
from tests.fixtures.interactive_app import start_server


@pytest.fixture(scope="module")
def interactive_server():
    server, thread = start_server()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def run_case(server, tmp_path: Path, case: str, *, transitions: int = 1):
    server.state.reset()
    artifact = Explorer(
        RunConfig(
            start_url=f"{server.base_url}/{case}",
            output_dir=tmp_path / case,
            policy="grouped",
            max_seconds=10,
            max_transitions=transitions,
            max_browser_actions=100,
            allow_post_forms=True,
            replay_reserve_fraction=0.45,
            context_label=f"fixture:{case}",
        ),
        Path(__file__).resolve().parents[1],
    ).run()
    return artifact, server.state.snapshot()


def test_same_url_result_change_fails_content_sensitive_replay(interactive_server, tmp_path: Path) -> None:
    artifact, events = run_case(interactive_server, tmp_path, "search")
    assert {item["result"] for item in events if item.get("kind") == "search_result"} == {
        "Result Alpha",
        "Result Beta",
    }
    assert len({item.group_signature for item in artifact.observations}) == 2
    assert artifact.metrics.replay_failures == 1
    assert artifact.metrics.functional_workflows_verified == 0


def test_observed_constraints_enable_verified_form_success(interactive_server, tmp_path: Path) -> None:
    artifact, events = run_case(interactive_server, tmp_path, "form")
    submissions = [item["success"] for item in events if item.get("kind") == "form_submission"]
    assert submissions and all(submissions)
    assert artifact.metrics.functional_workflows_verified == 1
    assert artifact.functional_workflows[0].status == FunctionalStatus.VERIFIED


def test_multistep_replay_reproduces_prerequisite(interactive_server, tmp_path: Path) -> None:
    artifact, events = run_case(interactive_server, tmp_path, "multi", transitions=8)
    completions = [item for item in events if item.get("kind") == "completion"]
    assert completions
    assert all(item["success"] and item["prerequisite"] for item in completions)
    assert artifact.metrics.functional_workflows_verified >= 1
    assert any(item.path_length >= 2 for item in artifact.functional_workflows)


def test_wrong_record_instance_is_not_accepted(interactive_server, tmp_path: Path) -> None:
    artifact, events = run_case(interactive_server, tmp_path, "records")
    visits = [item["record"] for item in events if item.get("kind") == "record_visit"]
    assert visits == ["2", "1"]
    assert artifact.replays[0].status == EvidenceStatus.FAILED
    assert artifact.replays[0].outcome_checks["content_fingerprint"] is False


def test_cosmetic_time_does_not_split_and_connections_are_complete(
    interactive_server, tmp_path: Path
) -> None:
    artifact, _ = run_case(interactive_server, tmp_path, "cosmetic")
    observations = [item for item in artifact.observations if item.route_pattern == "/cosmetic"]
    assert len({item.group_signature for item in observations}) == 1
    assert len({item.state_signature for item in observations}) == 1
    assert artifact.metrics.graph_connections_missing_evidence == 0
