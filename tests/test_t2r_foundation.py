"""Phase 1b-R evaluation foundation: frozen before the Capability Tour Scheduler."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import evaluation.sim_eval as se
from evaluation import t2r_eval
from evaluation.sim_diagnostics import build, solve_search, solve_snapshot, verified_classes
from evaluation.sim_scenarios import SEEDS as T2_SEEDS
from evaluation.sim_scenarios import STRESS_SEEDS as T2_STRESS_SEEDS

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("seed", t2r_eval.DIAG_SEEDS)
def test_diagnostic_outcomes_are_reachable_by_scripted_plans(seed: int) -> None:
    assert "collection_query" in verified_classes(solve_search(seed))
    records, _ = solve_snapshot(seed)
    assert "instance_creation" in verified_classes(records)
    records, result = solve_snapshot(seed, "diag_snapshot_drift")
    assert result.abort_reason == "unverified_start_state" and not verified_classes(records)
    _, result = solve_snapshot(seed, "diag_snapshot_absent")
    assert result.refused == ["snapshot_unavailable"]


def test_t2r_seeds_are_fresh() -> None:
    assert not set(t2r_eval.SEEDS) & set(T2_SEEDS)
    assert not set(t2r_eval.STRESS_SEEDS) & set(T2_STRESS_SEEDS)
    assert len(t2r_eval.SEEDS) == 50


def test_original_t2_experiment_is_untouched() -> None:
    assert t2r_eval.fingerprint() == "c77ff701232815d1"     # appsim.py, sim_eval.py, sim_scenarios.py at 60985f3
    tests = json.loads((ROOT / "evaluation" / "results" / "t2_tests.json").read_text())
    assert {k: v["pass"] for k, v in tests.items()} == {"T2a": False, "T2b": True, "T2c": False, "T2d": False,
                                                       "T2e": True, "T2f": False}


def test_observer_never_changes_decisions() -> None:
    plain = se.run("legacy_frontier", "mixed", 1003, 80)
    t2r_eval.install()
    observed = t2r_eval.job(("legacy_frontier", "mixed", 1003, 80))
    assert plain["decision_hash"] == observed["decision_hash"] and plain["final"] == observed["final"]


def test_diagnostic_apps_are_deterministic_and_separate_from_t2() -> None:
    for arch in ("diag_search", "diag_snapshot"):
        assert build(arch, 2000).summary() == build(arch, 2000).summary()
    assert all(not k.startswith("diag") for k in se.SCENARIOS)
