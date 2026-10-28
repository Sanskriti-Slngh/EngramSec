from __future__ import annotations

from pathlib import Path

import pytest

from agent1.explorer import Explorer
from agent1.schema import FunctionalStatus, RunConfig
from tests.fixtures.search_adversarial_app import start_adversarial_search_server
from tests.fixtures.search_adversarial_ground_truth import SEARCH_CASES


@pytest.fixture(scope="module")
def adversarial_search_url():
    server, thread, base_url = start_adversarial_search_server()
    try:
        yield base_url
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("case_name", SEARCH_CASES)
def test_paired_search_matches_independent_ground_truth(
    adversarial_search_url: str,
    tmp_path: Path,
    case_name: str,
) -> None:
    truth = SEARCH_CASES[case_name]
    artifact = Explorer(
        RunConfig(
            start_url=adversarial_search_url + truth["path"],
            output_dir=tmp_path / case_name,
            policy="grouped",
            max_seconds=12,
            max_transitions=1,
            max_browser_actions=60,
            settle_ms=20,
            replay_reserve_fraction=0.55,
            search_probe_primary="alpha",
            search_probe_contrast="beta",
            context_label=f"fixture:{case_name}",
        ),
        Path(__file__).resolve().parents[1],
    ).run()
    paired_transition_ids = {
        replay.transition_id
        for replay in artifact.replays
        if replay.verification_kind == "paired_search"
    }
    workflows = [
        item
        for item in artifact.functional_workflows
        if item.transition_id in paired_transition_ids
    ]

    assert len(workflows) == 1
    expected = (
        FunctionalStatus.VERIFIED
        if truth["functional"]
        else FunctionalStatus.UNRESOLVED
    )
    assert workflows[0].status == expected
    assert all(workflows[0].verification_checks.values())
    assert artifact.metrics.functional_workflows_verified == int(truth["functional"])
    paired_replays = [
        replay for replay in artifact.replays if replay.verification_kind == "paired_search"
    ]
    assert len(paired_replays) == 2
    assert all(
        len(replay.verification_observation_ids) == 4 for replay in paired_replays
    )
    assert all(
        replay.verification_evidence.get("evidence_rule")
        == "introduced-link-target-delta-v2"
        for replay in paired_replays
    )
