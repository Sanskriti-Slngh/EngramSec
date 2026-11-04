"""Evaluation-harness tests for the comprehensive Agent 1 evaluation (preregistration revision 1).

Synthetic inputs only: no browser, no Docker, no benchmark target.
"""
from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from evaluation import comprehensive_eval as E
from evaluation import comprehensive_metrics as M
from evaluation.comprehensive_config import FROZEN
from evaluation.ground_truth import GroundTruth


def _gt() -> GroundTruth:
    ep = lambda **k: k  # noqa: E731
    return GroundTruth.model_validate({
        "application": "synthetic",
        "annotation": {"annotator": "test", "independent": False, "method": "synthetic", "sources": [],
                       "frozen_at": "2026-11-04"},
        "roles": [{"id": "anonymous"}], "templates": ["/"],
        "capabilities": [
            {"id": "add_to_cart", "behavioral_class": None, "class_observable_to_role": False, "roles": ["anonymous"],
             "operations": [{"method": "POST", "route": "/cart/items"}], "effect_risk": "server_write",
             "entry_points": [ep(kind="form_submit", label="Add")]},
            {"id": "wipe", "behavioral_class": None, "class_observable_to_role": False, "roles": ["anonymous"],
             "operations": [{"method": "POST", "route": "/api/wipe"}], "effect_risk": "destructive",
             "entry_points": [ep(kind="button", label="Delete everything")]},
            {"id": "remove_filter", "behavioral_class": None, "class_observable_to_role": False, "roles": ["anonymous"],
             "operations": [{"method": "GET", "route": "/list"}], "effect_risk": "none",
             "entry_points": [ep(kind="button", label="Delete filter")]},
            {"id": "about", "behavioral_class": None, "class_observable_to_role": False, "roles": ["anonymous"],
             "operations": [{"method": "GET", "route": "/about"}], "entry_points": [ep(kind="link", target_route="/about")]},
            {"id": "hidden", "behavioral_class": None, "class_observable_to_role": False, "roles": ["anonymous"],
             "operations": [{"method": "GET", "route": "/hidden"}], "entry_points": [ep(kind="link", target_route="/hidden")]},
            {"id": "partner", "behavioral_class": None, "class_observable_to_role": False, "roles": ["anonymous"],
             "operations": [{"method": "GET", "route": "/partner"}], "entry_points": [ep(kind="link", label="Partner")]},
        ],
    })


def _adv(kind, label, skip, target=None, method=None):
    return {"source_observation_id": "o1",
            "control": {"kind": kind, "label": label, "target": target, "method": method, "skip_reason": skip}}


RUN = {"observations": [{"id": "o1", "url": "http://127.0.0.1:1/"}]}
GRAPH = {"advertised_unexecuted": [
    _adv("form_submit", "Add", "post_forms_disabled", "http://127.0.0.1:1/cart/items", "POST"),
    _adv("button", "Delete everything", "dangerous_label_or_target"),
    _adv("button", "Delete filter", "dangerous_label_or_target"),
    _adv("link", "About", None, "http://127.0.0.1:1/about"),
    _adv("link", "Partner", "cross_origin", "http://other.example/partner"),
]}


def test_safety_attribution_separates_legitimate_refusals_from_technical_misses():
    out = M.safety_attribution(_gt(), RUN, GRAPH, {"add_to_cart", "wipe", "remove_filter", "about", "hidden", "partner"})
    assert out["add_to_cart"]["class"] == "legitimate_safety_refusal"        # POST disabled by frozen default
    assert out["add_to_cart"]["skip_reasons"] == ["post_forms_disabled"]
    assert out["wipe"]["class"] == "legitimate_safety_refusal"               # destructive, dangerous-label filter
    assert out["remove_filter"]["class"] == "over_conservative_safety_refusal"   # benign capability refused
    assert out["about"]["class"] == "not_safety_limited"                     # advertised, never selected
    assert out["hidden"]["class"] == "no_matching_advertised_control"        # never observed
    assert out["partner"]["class"] == "scope_refusal"


def test_safety_attribution_mixed_when_an_unrefused_matching_control_exists():
    graph = {"advertised_unexecuted": GRAPH["advertised_unexecuted"] + [
        _adv("form_submit", "Add", None, "http://127.0.0.1:1/cart/items", "POST")]}
    assert M.safety_attribution(_gt(), RUN, graph, {"add_to_cart"})["add_to_cart"]["class"] == \
        "mixed_safety_and_unrefused_controls"


def test_safety_attribution_ignores_matched_capabilities():
    assert M.safety_attribution(_gt(), RUN, GRAPH, set()) == {}


def test_refusal_breakdown_splits_by_cause():
    skip = Counter({"post_forms_disabled": 3, "dangerous_label_or_target": 2, "cross_origin": 4,
                    "frame_not_observable": 1, "unexecuted_not_selected": 7})
    r = M.refusal_breakdown(skip)
    assert r["safety_refusals_total"] == 5 and r["safety_refusals_by_configuration"]["post_forms_disabled"] == 3
    assert (r["scope_refusals"], r["technical_unobservable"], r["not_selected"], r["other"]) == (4, 1, 7, 0)


def _export(roles=("anonymous", "anonymous+member")):
    caps = [{"id": f"c{i}", "role": r, "status": "observed", "operation_ids": ["op1"] if i == 0 else [],
             "bindings": [], "effects": [], "unidentified": True} for i, r in enumerate(roles)]
    return {"capabilities": caps, "operations": [{"id": "op1", "channel": "http", "method": "GET", "route": "/"},
                                                 {"id": "op2", "channel": "http", "method": "GET", "route": "/x"}],
            "affordances": [], "learned_predicates": [], "claims": [], "gaps": [], "templates": [],
            "view_states": [], "entity_types": [], "entity_instances": []}


def test_capability_metrics_use_session_terminology_not_roles():
    c = M.capabilities(_export(), {"advertised_unexecuted": []})
    assert "role_conditioned" not in c
    assert c["session_conditioned"] == {"session_contexts": 2, "capabilities_in_cookie_session_contexts": 1}
    assert c["operations_without_capability"] == 1


def test_frozen_configuration_unchanged_and_diagnostic_override_separate():
    assert FROZEN["policy"] == "coverage" and FROZEN["max_seconds"] == 180.0
    assert FROZEN["max_browser_actions"] == 500 and FROZEN["max_transitions"] == 100
    assert FROZEN["allow_post_forms"] is False and FROZEN["model_provider"] == "none"
    assert E.POST_DIAGNOSTIC_OVERRIDE == {"allow_post_forms": True}


def test_post_diagnostic_refuses_docker_and_external_targets(tmp_path):
    with pytest.raises(SystemExit):
        E.child("prestashop", tmp_path, "http://127.0.0.1:1/", True, post_diagnostic=True)


def test_post_diagnostic_selection_rule(tmp_path):
    for env, n in (("coverage_lab", 5), ("stateful_lab", 0), ("prestashop", 9)):
        d = tmp_path / env / "trial_0"; d.mkdir(parents=True)
        (d / "trial.json").write_text(json.dumps(
            {"capabilities": {"evidence_status": {"advertised_by_skip_reason": {"post_forms_disabled": n}}}}))
    assert E.select_post_diagnostic_envs(tmp_path) == ["coverage_lab"]      # in-process only, rule-based


# ------------------------------------------------------------------ reset integrity (fake Docker)
def _inspect(service, tmpfs=(), volume=None):
    mounts = [{"Type": "volume", "Name": volume, "Destination": "/data", "RW": True}] if volume else []
    return {"Name": "/" + service, "Config": {"Labels": {"com.docker.compose.service": service}},
            "HostConfig": {"Tmpfs": {t: "" for t in tmpfs}}, "Mounts": mounts}


class FakeDocker:
    def __init__(self):
        self.containers: list[str] = []
        self.named_volumes: list[str] = []
        self.inspect: list[dict] = []
        self.down_exit = 0

    def __call__(self, cmd, timeout=120, cwd=None, check=True):
        out = ""
        rc = 0
        if cmd[:2] == ["docker", "ps"]:
            out = "\n".join(self.containers)
        elif cmd[:3] == ["docker", "volume", "ls"]:
            out = "\n".join(f"{v}\t{v}" for v in self.named_volumes) if "--filter" in cmd else ""
        elif cmd[:2] == ["docker", "inspect"]:
            out = json.dumps(self.inspect)
        elif cmd[0].endswith("targetctl") and cmd[1] == "down":
            rc = self.down_exit
        return subprocess.CompletedProcess(cmd, rc, out, "")


@pytest.fixture
def docker(monkeypatch, tmp_path):
    fake = FakeDocker()
    monkeypatch.setattr(E, "_sh", fake)
    monkeypatch.setattr(E, "RESET_PROFILES", tmp_path / "profiles.json")
    return fake


def test_reset_fails_when_previous_containers_remain(docker):
    ext = E.External("siyucms")
    docker.containers = ["abc"]
    docker.down_exit = 1
    with pytest.raises(E.ResetFailure, match="remain before startup"):
        ext._pre_start(1)
    assert ext.reset["pre_start_down_exit"] == 1 and ext.reset["residual_containers_before_start"] == 1


def test_reset_fails_when_named_project_volume_exists(docker):
    docker.named_volumes = ["web_siyucms_db"]
    with pytest.raises(E.ResetFailure, match="named project volumes"):
        E.External("siyucms")._pre_start(0)


def test_post_start_records_ids_and_checks_frozen_profile(docker, tmp_path):
    docker.inspect = [_inspect("db", tmpfs=["/var/lib/mysql"]), _inspect("web")]
    profile, _ = E._mount_profile(docker.inspect)
    (tmp_path / "profiles.json").write_text(json.dumps({"siyucms": {"mount_profile": profile}}))
    ext = E.External("siyucms")
    ext._pre_start(0)                               # nothing left from a previous run
    docker.containers = ["id1", "id2"]              # `targetctl up` created the project
    ext._post_start()
    assert ext.reset["container_ids"] == ["id1", "id2"] and ext.reset["tmpfs_mounts"] == 1
    assert ext.reset["mount_profile_matches_frozen"] is True
    # next trial: same container IDs would mean the environment was not recreated
    with pytest.raises(E.ResetFailure, match="container IDs reused"):
        ext._post_start()


def test_post_start_rejects_profile_change_reused_volume_and_missing_profile(docker, tmp_path):
    docker.containers = ["id1"]
    docker.inspect = [_inspect("db", tmpfs=["/var/lib/mysql"])]
    with pytest.raises(E.ResetFailure, match="no frozen mount profile"):
        E.External("siyucms")._post_start()
    (tmp_path / "profiles.json").write_text(json.dumps({"siyucms": {"mount_profile": E._mount_profile(docker.inspect)[0]}}))
    docker.inspect = [_inspect("db", volume="v1")]                      # tmpfs replaced by a volume
    with pytest.raises(E.ResetFailure, match="differs from the frozen profile"):
        E.External("siyucms")._post_start()
    ext = E.External("siyucms", require_profile=False)
    ext.seen_volumes = {"v1"}
    docker.containers = ["id9"]
    with pytest.raises(E.ResetFailure, match="volumes reused"):
        ext._post_start()


def test_teardown_records_exit_and_residuals(docker):
    ext = E.External("siyucms")
    ext.reset = {"volume_names": []}
    docker.down_exit = 3
    docker.containers = ["left"]
    ext.teardown()
    assert ext.reset["teardown_exit"] == 3 and ext.reset["residual_containers_after_teardown"] == 1


# ------------------------------------------------------------------ Track B summary: no coverage percentages
def test_track_b_summary_reports_sections_and_no_coverage_percentage(tmp_path):
    from evaluation.comprehensive_summary import TRACK_B_SECTIONS, summarize
    d = tmp_path / "prestashop" / "trial_0"; d.mkdir(parents=True)
    row = {"trial": 0, "status": "ok", "track": "B",
           "efficiency": {"browser_actions": 10, "failed_action_error_classes": {}},
           "capabilities": {"distinct_capabilities_observed_or_better": 4, "unidentified": 3,
                            "operations_without_capability": 2,
                            "evidence_status": {"verified": 0, "observed": 4},
                            "refusals": {"safety_refusals_total": 1, "scope_refusals": 2}},
           "discovery": {"entity_types": 1}, "acg_comparison": {}, "capability_keys": ["a"],
           "reset": {"container_ids": ["x"], "volume_names": [], "teardown_exit": 0,
                     "residual_containers_after_teardown": 0, "mount_profile_matches_frozen": True}}
    (d / "trial.json").write_text(json.dumps(row))
    out = summarize(tmp_path, out_path=tmp_path / "s.json")
    entry = out["environments"]["prestashop"]
    assert entry["functional_coverage_percentage"].startswith("NOT MEASURABLE")
    assert set(entry["report_sections"]) == set(TRACK_B_SECTIONS)
    assert entry["report_sections"]["unidentified_operations"]["capabilities.operations_without_capability"]["median"] == 2
    assert not any("recall" in k or "precision" in k for k in entry["metrics"])
    assert entry["reset_integrity"]["container_ids_disjoint_across_trials"] is True
    assert "reference_kind" in entry and "gt" not in entry
