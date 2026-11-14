"""Frozen Phase 1b scenarios, seeds, budgets and T2 thresholds.

Committed before any planner decision policy exists. Thresholds are the ones
preregistered in EXPLORATION_PLANNER_DESIGN.md §10.3; where the design left a
measurement detail open, the choice is fixed here, before results exist.
"""
from __future__ import annotations

from evaluation.appsim import ARCHITECTURES

SEEDS = list(range(50))                      # §10.3: 50 seeds per test scenario
POLICIES = ["bfs", "legacy_frontier", "acg_uniform", "acg_no_unlock", "acg_full"]
CHECKPOINT = 10                              # discovery curve sampled every 10 actions

SCENARIOS = {
    # T2a / T2e: mixed applications, one of the ten architectures per seed.
    "mixed": {"arch": None, "kw": {}, "budgets": [150]},
    # T2b: one template with 200 similar instances plus ~10 other capabilities.
    "instances": {"arch": "large_list", "kw": {"instances": 200, "other_pages": 1, "other_controls": 3},
                  "budgets": [150]},
    # T2c: capabilities behind 3-step prerequisite chains, among distractors.
    "prerequisites": {"arch": "workflow", "kw": {"chains": 3, "distractor_areas": 3, "distractor_pages": 2,
                                                 "distractor_controls": 3, "collection": 40},
                      "budgets": [100, 200, 400]},
    # T2d: flat application; every control a distinct capability.
    "flat": {"arch": "flat", "kw": {"pages": 12, "controls": 5}, "budgets": [100]},
}


def arch_for(scenario: str, seed: int) -> str:
    arch = SCENARIOS[scenario]["arch"] if scenario in SCENARIOS else STRESS[scenario]["arch"]
    return arch or ARCHITECTURES[seed % len(ARCHITECTURES)]


T2 = {
    "T2a": {"scenario": "mixed", "policy": "acg_full", "bin_width": 0.10, "min_bin": 30, "tolerance": 0.10,
            "outcome": "an executed bind_affordance produced a capability id absent from the ACG before it"},
    "T2b": {"scenario": "instances", "policy": "acg_full", "max_sampled_instances": 3,
            "metric": "distinct instances of the 200-instance template first visited by a plan that is not a "
                      "split_test; must be <= 3 in every seed"},
    "T2c": {"scenario": "prerequisites", "policy": "acg_full", "comparator": "legacy_frontier",
            "budgets": [100, 200, 400], "min_seed_fraction": 0.80,
            "metric": "recall of observable gated capabilities (controls initially disabled)"},
    "T2d": {"scenario": "flat", "policy": "acg_full", "comparator": "bfs", "min_ratio": 0.95,
            "metric": "mean over seeds of discovery AUC (mean recall at every 10 actions)"},
    "T2e": {"scenario": "mixed", "policy": "acg_full", "repeats": 2,
            "metric": "identical decision-log hash for every seed"},
    "T2f": {"scenarios": ["instances", "prerequisites"], "policy": "acg_full", "comparator": "acg_uniform",
            "alpha": 0.05,
            "metric": "instances: discovery AUC; prerequisites: gated recall averaged over budgets 100/200/400. "
                      "PASS on each scenario iff the mean paired difference is > 0 and a one-sided sign test "
                      "over seeds (ties dropped) has p < 0.05"},
}

# Phase 5 diagnostics: out-of-assumption environments. Reported, never used to
# change a T2 threshold.
STRESS_SEEDS = list(range(20))
STRESS = {
    "rare_in_repetition": {"arch": "state_variants", "kw": {}, "budget": 150},
    "misleading_novelty": {"arch": "duplicate_pages", "kw": {"duplicates": 30}, "budget": 150},
    "role_specific": {"arch": "roles", "kw": {}, "budget": 150},
    "missing_identifiers": {"arch": "hidden_ids", "kw": {}, "budget": 150},
    "client_only_unobservable": {"arch": "client_only", "kw": {}, "budget": 80},
    "noisy_outcomes": {"arch": "flaky", "kw": {"flaky": 0.25}, "budget": 150},
    "false_prerequisite_signals": {"arch": "workflow", "kw": {"chains": 2, "decoys": True, "distractor_areas": 2},
                                   "budget": 150},
    "long_restoration": {"arch": "workflow", "kw": {"chains": 1, "distractor_areas": 1, "deep_areas": 3,
                                                    "depth": 6}, "budget": 150},
    "writes_without_snapshots": {"arch": "crud", "kw": {}, "budget": 150},
    "writes_with_snapshots": {"arch": "flaky", "kw": {"flaky": 0.0}, "budget": 150},
    "unverifiable_snapshot": {"arch": "flaky", "kw": {"flaky": 0.0, "snapshot_drift": True}, "budget": 150},
}
