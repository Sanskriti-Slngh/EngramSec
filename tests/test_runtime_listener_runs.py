"""Explorer-level Phase 3 tests: the frontier, replay and Graph A treatment of
listener candidates and handler revisions (separate module: each run owns its
Playwright instance)."""
from __future__ import annotations

from pathlib import Path

from agent1.exporter import build_graph_a
from agent1.schema import EvidenceStatus, RunConfig
from agent1.explorer import Explorer
from tests.test_runtime_listeners import base  # noqa: F401  (shared localhost fixture)


def run(base, path, tmp_path, mode, seconds=25):
    config = RunConfig(start_url=base + path, output_dir=tmp_path / mode, policy="multidimensional",
                       exploration_mode="persistent", interaction_profile="extended", settle_ms=150,
                       max_seconds=seconds, max_transitions=12, max_browser_actions=60,
                       runtime_listener_observation=mode)
    return Explorer(config, Path(__file__).resolve().parents[1]).run()


def structures(artifact):
    return {(t.action.label, t.action.behavior_revision is not None, e.url.rsplit("/", 1)[-1])
            for t in artifact.transitions if t.status != EvidenceStatus.FAILED for e in t.network
            if e.resource_type == "fetch"}


def test_state_identity_suppressed_the_changed_handler_and_revisit_recovers_it(base, tmp_path):
    """Reproduction: the second behavior shares the visible DOM, so the
    group-signature frontier marked the control as tried."""
    off = run(base, "/redefine", tmp_path, "off")
    assert ("Step", False, "first") in structures(off)
    assert not any(s[2] == "second" for s in structures(off))
    revisit = run(base, "/redefine", tmp_path, "revisit")
    assert ("Step", True, "second") in structures(revisit)
    revised = [t for t in revisit.transitions if t.action.behavior_revision]
    assert revised and all(t.status == EvidenceStatus.REPLAY_VALIDATED for t in revised)
    replay = next(r for r in revisit.replays if r.transition_id == revised[0].id)
    assert replay.outcome_checks.get("request_structures") is True  # same DOM: the request is the evidence
    claims = [c for c in revisit.connection_evidence if c.claim_type == "handler_revision"]
    assert claims and all(c.complete for c in claims)
    assert revisit.metrics.graph_connections_missing_evidence == 0
    behavior = build_graph_a(revisit)["behavior_evidence"]
    assert behavior["summary"]["replay_validated_listener_or_revision_actions"] >= 1
    assert any(not e["visible_dom_changed"] and e["behavior_revision"] for e in behavior["behavior_executions"])


def test_listener_candidate_is_executed_replayed_and_evidenced(base, tmp_path):
    observe = run(base, "/div", tmp_path, "observe")
    executed = [t for t in observe.transitions if t.action.provenance == "observed_listener"
                and t.status != EvidenceStatus.FAILED]
    assert executed and any(e.url.endswith("/api/details") for t in executed for e in t.network)
    assert any(t.status == EvidenceStatus.REPLAY_VALIDATED for t in executed)
    claims = [c for c in observe.connection_evidence if c.claim_type == "listener_candidate"]
    assert claims and all(c.complete for c in claims)
    assert observe.metrics.listener_candidates_executed >= 1 and observe.metrics.incorrect_state_merges == 0


def test_exploration_stops_cleanly_at_the_http_discovery_cap_and_replay_uses_the_reserve(base, tmp_path):
    """Reproduction (transfer fixture): with a verification reserve, exploration
    reached the discovery cap and the persistent restore raised, aborting the run."""
    config = RunConfig(start_url=base + "/", output_dir=tmp_path / "cap", policy="multidimensional",
                       exploration_mode="persistent", settle_ms=100, max_seconds=30, max_transitions=12,
                       max_browser_actions=60, max_total_http_requests=8, http_verification_reserve_fraction=0.5)
    artifact = Explorer(config, Path(__file__).resolve().parents[1]).run()
    assert "HTTP discovery budget exhausted; exploration stopped before replay." in artifact.notes
    assert artifact.metrics.http_budget_by_source.get("browser", 0) <= 4
    assert artifact.metrics.http_budget_by_source.get("browser_verification", 0) > 0
    assert artifact.metrics.replay_success_numerator >= 1
    # Budget exhaustion leaves transitions untested; it is never a failed replay.
    assert not any("ERR_BLOCKED_BY_CLIENT" in (r.error or "") for r in artifact.replays)
