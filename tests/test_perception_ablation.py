"""Contract tests for the perception ablation harness (synthetic inputs; no browser)."""
from __future__ import annotations

import pytest

from evaluation import perception_ablation as P
from evaluation.comprehensive_config import FROZEN, INSTRUMENTATION


def test_arms_differ_from_production_defaults_only_in_the_intended_fields():
    base = P.arm_fields("A")
    assert base == {**FROZEN, **INSTRUMENTATION}           # A is exactly the comprehensive primary configuration
    intended = {"B": {"robust_readiness"}, "C": {"runtime_listener_observation"},
                "D": {"robust_readiness", "runtime_listener_observation"}}
    for arm, keys in intended.items():
        f = P.arm_fields(arm)
        assert {k for k in set(f) | set(base) if f.get(k) != base.get(k)} == keys
    assert P.arm_fields("D")["runtime_listener_observation"] == "revisit" and P.arm_fields("D")["robust_readiness"] is True


def test_every_arm_builds_a_valid_config_with_equal_budgets(tmp_path):
    from agent1.schema import RunConfig
    configs = [RunConfig(start_url="http://127.0.0.1:1/", output_dir=tmp_path, context_label="t", **P.arm_fields(a))
               for a in P.ARMS]
    for field in ("policy", "max_seconds", "max_browser_actions", "max_transitions", "allow_post_forms",
                  "exploration_mode", "interaction_profile", "settle_ms", "readiness_timeout_ms", "model_provider"):
        assert len({getattr(c, field) for c in configs}) == 1, field


def test_rotating_arm_order_puts_each_arm_in_each_position():
    orders = [P.arm_order(t) for t in range(4)]
    assert all(sorted(o) == sorted(P.ARMS) for o in orders)
    for position in range(4):
        assert sorted(o[position] for o in orders) == sorted(P.ARMS)


def test_only_preregistered_development_environments_are_accepted(monkeypatch):
    monkeypatch.setattr(P, "tree_clean", lambda paths: True)
    for env in ("siyucms", "prestashop", "comfyui", "jetlinks", "white-jotter", "coverage_lab"):
        with pytest.raises(SystemExit):
            P.run("diagnostic", 1, [env])


def _obs(oid, controls, readiness=None, listener=None):
    return {"id": oid, "url": "http://127.0.0.1:1/", "controls": controls,
            "readiness": readiness or {"status": "not_recorded", "samples": []}, "listener_evidence": listener}


def _ctl(sig, prov="snapshot"):
    return {"signature": sig, "id": sig, "provenance": prov}


def _tr(tid, sig, prov="snapshot", status="observed", error=None, src="g1", res="g2", network=(), revision=None):
    return {"id": tid, "status": status, "error": error, "source_group_signature": src, "result_group_signature": res,
            "network": list(network), "action": {"signature": sig, "provenance": prov, "behavior_revision": revision}}


def test_perception_metrics_separate_listener_readiness_revision_and_restoration_evidence():
    run = {
        "observations": [
            _obs("o1", [_ctl("a"), _ctl("L1", "observed_listener"), _ctl("L2", "observed_listener")],
                 readiness={"status": "usable", "duration_ms": 900, "samples": [
                     {"enabled_control_count": 2}, {"enabled_control_count": 5}]},
                 listener={"elapsed_ms": 12.5, "cdp_calls": 4, "skipped": {"delegation_host": 1},
                           "candidates": [{"css_path": "div#x", "label": "Open"}, {"css_path": "div#y", "label": "Save"}]}),
        ],
        "replay_observations": [],
        "transitions": [
            _tr("t1", "L1", "observed_listener", network=[{"method": "GET", "url": "http://127.0.0.1:1/api"}]),
            _tr("t2", "L2", "observed_listener", src="g1", res="g1"),                  # no observable effect
            _tr("t3", "a", revision="r1"),
            _tr("t4", "a", status="failed", error="RuntimeError: saved return path restored x, expected y"),
            _tr("t5", "a", status="not_tested", error="UnsafeRestoration: return path contains a write"),
        ],
        "metrics": {"browser_actions": 9, "elapsed_seconds": 10.0},
        "config": {"start_url": "http://127.0.0.1:1/", "origin_aliases": []},
        "replays": [{"network": [{"url": "http://elsewhere.test/x", "failure": "net::ERR_BLOCKED_BY_CLIENT"}]}],
        "navigation_evidence": [{"network": [{"url": "http://other.test/y", "status": 200}]}],
    }
    graph = {"advertised_unexecuted": [{"control": {"signature": "L3", "provenance": "observed_listener"}}]}
    export = {"affordances": [{"id": "f1", "family": {"provenance": "observed_listener"}},
                              {"id": "f2", "family": {"provenance": "snapshot"}}],
              "capabilities": [{"status": "observed", "bindings": [{"affordance_id": "f1"}]},
                               {"status": "reproduced", "bindings": [{"affordance_id": "f1"}, {"affordance_id": "f2"}]},
                               {"status": "observed", "bindings": [{"affordance_id": "f2"}]},
                               {"status": "hypothesized", "bindings": [{"affordance_id": "f1"}]}]}
    m = P.perception_metrics(run, graph, export)
    assert m["controls_observed_by_provenance"] == {"snapshot": 1, "observed_listener": 2}
    assert m["listener_transitions"] == 2 and m["listener_transitions_ok"] == 2
    assert m["listener_transitions_no_effect"] == 1
    assert m["listener_controls_executed_distinct"] == 2 and m["listener_controls_advertised_unexecuted_distinct"] == 1
    assert m["revision_transitions"] == 1 and m["revision_transitions_ok"] == 1
    assert m["controls_gained_during_readiness"] == 3 and m["readiness_wait_ms"] == 900
    assert m["restoration_failures"] == {"restore_group_mismatch": 1, "unsafe_restoration_refused": 1}
    assert m["listener_observer_ms"] == 12.5 and m["listener_observer_cdp_calls"] == 4
    assert m["listener_candidate_skips"] == {"delegation_host": 1} and m["listener_candidates_distinct"] == 2
    assert m["capabilities_by_provenance"] == {"listener_only": 1, "mixed": 1, "snapshot_or_unbound": 1}
    assert m["out_of_scope_requests_recorded"] == 2 and m["out_of_scope_requests_completed"] == 1


def test_listener_controls_still_pass_the_dangerous_label_filter():
    """Dynamically discovered controls get the same label safety filter as snapshot controls."""
    from types import SimpleNamespace

    from agent1.explorer import BrowserSession
    fake = SimpleNamespace(config=SimpleNamespace(start_url="http://127.0.0.1:1/", origin_aliases=[], allow_post_forms=False))
    assert BrowserSession._unsafe_reason(fake, "Delete all records", None, None, []) == "dangerous_label_or_target"
    assert BrowserSession._unsafe_reason(fake, "Open details", None, None, []) is None
