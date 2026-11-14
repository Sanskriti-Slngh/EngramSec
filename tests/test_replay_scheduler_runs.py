"""End-to-end replay-scheduler tests on development_apps/replay_lab.py.
Each Explorer run owns its Playwright instance (separate module)."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent1.explorer import Explorer
from agent1.exporter import build_graph_a
from agent1.schema import EvidenceStatus, RunConfig
from development_apps.replay_lab import STATE, start_replay_lab

ROOT = Path(__file__).resolve().parents[1]


def run(tmp_path: Path, policy: str, actions: int):
    server, _thread, url = start_replay_lab()
    try:
        config = RunConfig(start_url=url, output_dir=tmp_path / f"{policy}_{actions}", policy="multidimensional",
                           exploration_mode="persistent", interaction_profile="extended", settle_ms=150,
                           max_seconds=90, max_transitions=80, max_browser_actions=actions,
                           runtime_listener_observation="revisit", replay_policy=policy,
                           max_total_http_requests=1000, http_verification_reserve_fraction=0.3)
        artifact = Explorer(config, ROOT).run()
        return artifact, list(STATE.log)
    finally:
        server.shutdown()
        server.server_close()


def structure(artifact, route: str) -> dict:
    items = build_graph_a(artifact)["replay_evidence"]["request_structures"]
    return next(item for item in items if f" {route} " in item["structure"])


@pytest.fixture(scope="module")
def structure_run(tmp_path_factory):
    return run(tmp_path_factory.mktemp("replay"), "structure", 200)


def test_runtime_behaviors_are_replayed_with_their_prerequisites(structure_run):
    artifact, _ = structure_run
    # 1. created listener <div>; 3. multi-step wizard (two prerequisite clicks after navigation).
    for route, min_steps in (("/api/details", 3), ("/api/finish", 4)):
        record = structure(artifact, route)
        assert record["status"] == "verified", record
        assert min(p["workflow_length"] for p in record["produced_by"]) >= min_steps
        assert all(p["provenance"] == "observed_listener" for p in record["produced_by"])
    # 2. replaced handler: verified on the revision, distinct from the unchanged first handler.
    second, first = structure(artifact, "/api/second"), structure(artifact, "/api/first")
    assert second["status"] == first["status"] == "verified"
    assert all(p["behavior_revision"] for p in second["produced_by"])
    assert not any(p["behavior_revision"] for p in first["produced_by"])


def test_distinct_structures_each_verified_equivalent_ones_once(structure_run):
    artifact, _ = structure_run
    # 4. two controls, two structures.
    assert structure(artifact, "/api/reviews")["status"] == structure(artifact, "/api/stock")["status"] == "verified"
    # 5. two controls with one structure: one independent replay targets it.
    save = structure(artifact, "/api/save/{instance}")
    assert save["status"] == "verified" and len(save["produced_by"]) == 2
    assert sum(1 for r in save["replays"] if r["targeted"]) == 1


def test_state_change_and_record_identity_failures_are_explained(structure_run):
    artifact, log = structure_run
    # 6. one-time voucher: the claim control no longer exists in a fresh context.
    claim = structure(artifact, "/api/claim")
    assert claim["status"] == "failed"
    assert {r["failure_reason"] for r in claim["replays"]} == {"control_missing"}
    assert all(r["failed_step"] == 2 for r in claim["replays"])
    # 7. session-scoped record identity: the record replay keeps the same
    # record in a new session; the per-session cart does not and is refused.
    history = structure(artifact, "/api/records/{instance}/history")
    assert history["status"] == "verified"
    sessions = {e["session"] for e in log if e["path"] == "/api/records/3/history"}
    assert len(sessions - {"-"}) >= 2                       # exploration and replay sessions
    cart = structure(artifact, "/api/carts/{instance}")
    assert cart["status"] == "failed" and cart["replays"][0]["failure_reason"] == "record_identity_changed"
    # A failed replay never marks its transition validated.
    failed_ids = {r["transition_id"] for item in (claim, cart) for r in item["replays"]}
    assert all(t.status != EvidenceStatus.REPLAY_VALIDATED for t in artifact.transitions if t.id in failed_ids)


def test_dangerous_listener_stays_excluded(structure_run):
    artifact, log = structure_run
    # 8. the "Delete all records" listener is never executed or replayed.
    assert not any(e["method"] == "POST" for e in log)
    assert not any("Delete" in t.action.label for t in artifact.transitions)
    assert artifact.metrics.graph_connections_missing_evidence == 0
    assert artifact.metrics.incorrect_state_merges == 0


def test_under_a_tight_budget_structure_policy_verifies_more_distinct_behavior(tmp_path):
    shallow, _ = run(tmp_path, "shallow", 90)
    struct, _ = run(tmp_path, "structure", 90)
    s, t = shallow.metrics, struct.metrics
    # Comparable replay spend, more distinct structures independently reproduced.
    assert abs(s.replay_browser_actions - t.replay_browser_actions) <= 8
    assert t.replay_structures_verified >= s.replay_structures_verified + 2
    assert t.replay_scheduler["lane_actions"]["shallow"] > 0   # navigation replay is not starved
