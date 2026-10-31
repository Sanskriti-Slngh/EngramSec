"""End-to-end runtime listener discovery on the Larkspur Library reading-room
fixture (development_apps/transfer_library.py): discovered elements must become
usable controls that the ordinary Explorer pipeline executes, records and
replays, under the existing safety and scope policy. Own module: each Explorer
run owns its Playwright instance."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent1.exporter import build_graph_a
from agent1.explorer import Explorer
from agent1.schema import EvidenceStatus, RunConfig
from development_apps.transfer_library import STATE, start_transfer_library


@pytest.fixture(scope="module")
def library():
    servers, threads, url = start_transfer_library()
    try:
        yield url.rstrip("/")
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


def run(url: str, path: str, tmp_path: Path, mode: str, seconds: float = 20):
    config = RunConfig(start_url=url + path, output_dir=tmp_path / (mode + path.replace("/", "_")),
                       policy="multidimensional", exploration_mode="persistent", interaction_profile="extended",
                       settle_ms=150, max_seconds=seconds, max_transitions=10, max_browser_actions=40,
                       runtime_listener_observation=mode)
    return Explorer(config, Path(__file__).resolve().parents[1]).run()


def requested(artifact, prefix: str, *, listener_only: bool = False, revision_only: bool = False) -> list:
    return [t for t in artifact.transitions if t.status != EvidenceStatus.FAILED
            and (not listener_only or t.action.provenance == "observed_listener")
            and (not revision_only or t.action.behavior_revision)
            and any(e.url.split("://", 1)[-1].split("/", 1)[-1].startswith(prefix.lstrip("/")) for e in t.network)]


def test_created_listener_divs_become_executed_and_evidenced_controls(library, tmp_path):
    off = run(library, "/desk/reserve", tmp_path, "off")
    assert requested(off, "/api/slots/reserve") == []          # invisible to the DOM snapshot
    on = run(library, "/desk/reserve", tmp_path, "revisit")
    hits = requested(on, "/api/slots/reserve", listener_only=True)
    assert hits, "a created study-slot <div> was not executed"
    assert all(t.action.label.startswith("Room ") for t in hits)
    metrics = on.metrics
    assert metrics.listener_candidates_new >= 1 and metrics.listener_actions_executed >= 1
    assert metrics.listener_transitions_with_effect >= 1
    assert metrics.listener_changes.get("created_after_action", 0) >= 1
    assert metrics.graph_connections_missing_evidence == 0 and metrics.incorrect_state_merges == 0
    behavior = build_graph_a(on)["behavior_evidence"]
    executed = [c for c in behavior["listener_candidates"] if c["executed_transition_ids"]]
    # First sighting after the creating click, later sightings of the same element as unchanged.
    assert any(c["provenance"] == "created_after_action" and c["caused_by_action"] for c in executed)
    assert {c["provenance"] for c in executed} <= {"created_after_action", "unchanged"}


def test_replaced_handler_is_reconsidered_on_the_same_unchanged_button(library, tmp_path):
    off = run(library, "/desk/loans", tmp_path, "off")
    assert requested(off, "/api/loans/status") and not requested(off, "/api/loans/eligibility")
    on = run(library, "/desk/loans", tmp_path, "revisit")
    second = requested(on, "/api/loans/eligibility", revision_only=True)
    assert second and second[0].action.label == "Check loan status"
    assert second[0].source_group_signature == second[0].result_group_signature  # visible DOM unchanged
    assert on.metrics.handler_revisions_observed >= 1 and on.metrics.handler_revisits_executed >= 1
    # The unchanged first handler is not executed again under the same revision.
    first_runs = [t for t in requested(on, "/api/loans/status") if not t.action.behavior_revision]
    assert len({t.source_group_signature for t in first_runs}) == len(first_runs)


def test_dangerous_and_off_scope_listeners_are_still_refused(library, tmp_path):
    STATE.reset()
    on = run(library, "/desk/tools", tmp_path, "revisit", seconds=12)
    log = STATE.snapshot()
    assert not any(e["method"] == "POST" and e["path"].startswith("/api/reading-list/clear") for e in log["log"])
    assert log["sentinel_hits"] == []
    unsafe = {c.label: c.skip_reason for o in on.observations for c in o.controls
              if c.provenance == "observed_listener" and not c.safe}
    assert unsafe.get("Delete my reading list") == "dangerous_label_or_target"
    assert on.metrics.listener_candidates_rejected >= 1
