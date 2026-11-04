"""Aggregate comprehensive-evaluation trials into evaluation/results/agent1_comprehensive_summary.json.

Per environment: every trial's status (failed/incomplete trials are listed, never dropped),
median/min/max of the preregistered metrics, cross-trial capability-set overlap (Jaccard),
determinism (identical executed-action sequences), initial-state and configuration
equivalence. Track B (WebExploitBench) entries contain aggregate numbers only.
"""
from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from statistics import median
from typing import Any

from evaluation.comprehensive_config import FROZEN, INSTRUMENTATION, git_revision
from evaluation.comprehensive_eval import ENVS, GATED, RESULTS


def _get(row: dict, path: str):
    cur: Any = row
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _stats(values: list) -> dict | None:
    vals = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not vals:
        return None
    return {"median": round(median(vals), 4), "min": round(min(vals), 4), "max": round(max(vals), 4), "n": len(vals)}


SCALARS = [
    "efficiency.browser_actions", "efficiency.elapsed_seconds", "efficiency.transitions_attempted",
    "efficiency.actions_unique_discovery", "efficiency.actions_redundant", "efficiency.actions_failed",
    "efficiency.restoration_actions", "efficiency.root_reloads", "efficiency.verification_actions",
    "efficiency.readiness_wait_ms", "efficiency.capabilities_per_100_actions", "efficiency.capabilities_per_minute",
    "efficiency.replays.attempts", "efficiency.replays.validated", "efficiency.replays.failures",
    "efficiency.http_by_source.navigation", "efficiency.http_by_source.action", "efficiency.http_by_source.replay",
    "efficiency.http_by_source.passive_resource_fetches", "efficiency.http_by_source.budget_used",
    "efficiency.http_by_source.blocked_out_of_scope",
    "discovery.route_templates", "discovery.grouped_states", "discovery.areas_route_title", "discovery.acg_templates",
    "discovery.unique_controls_observed", "discovery.unique_controls_executed", "discovery.advertised_unexecuted",
    "discovery.affordances", "discovery.affordance_families", "discovery.request_structures_browser",
    "discovery.acg_operations", "discovery.websocket_operations", "discovery.client_only_capabilities",
    "discovery.entity_types", "discovery.entity_instances", "discovery.roles",
    "capabilities.distinct_capabilities_observed_or_better", "capabilities.unidentified",
    "capabilities.equivalent_interfaces_multi_entry",
    "capabilities.evidence_status.observed", "capabilities.evidence_status.reproduced",
    "capabilities.evidence_status.verified", "capabilities.evidence_status.attempted_failed_affordances",
    "capabilities.evidence_status.blocked_affordances",
    "safety.state_changing_requests_issued", "safety.state_changing_requests_in_replay",
    "safety.dangerous_controls_skipped", "safety.destructive_endpoint_hits", "safety.repeated_write_endpoint_hits",
    "safety.unsupported_functional_claims", "safety.ws_out_of_scope_refused",
    "gt.final_recall", "gt.final_precision", "gt.auc_actions", "gt.auc_seconds", "gt.false_positives",
    "gt.incorrect_capability_merges", "gt.capability_splits", "gt.incorrect_record_merges",
    "gt.role_conditioned.recall", "gt.role_aware_precision_alt", "gt.live_acg.recall", "gt.live_acg.precision",
    "gt.graph_a_features.action_based_recall", "gt.gt_redundant_transitions", "gt.observed_transitions",
    "gt.recall", "gt.markers_scored",
    "setup_seconds", "teardown_seconds", "child_seconds", "mem_mb_after_setup", "mem_mb_peak_during_run",
]


def _jaccard(a: list, b: list) -> float | None:
    sa, sb = set(a), set(b)
    return round(len(sa & sb) / len(sa | sb), 4) if sa | sb else None


def summarize(base: Path) -> dict:
    out: dict[str, Any] = {
        "milestone": "Agent 1 comprehensive benchmark evaluation",
        "evaluated_revision": git_revision(),
        "frozen_config": FROZEN, "instrumentation": INSTRUMENTATION,
        "not_evaluated": {"webexploitbench_gated_targets": GATED, "reason": "NOT EVALUATED — ACCESS RESTRICTED"},
        "environments": {},
    }
    for env, spec in ENVS.items():
        rows = [json.loads(p.read_text()) for p in sorted((base / env).glob("trial_*/trial.json"))]
        entry: dict[str, Any] = {k: spec[k] for k in ("track", "category", "exposure", "gt")}
        entry["trials"] = [{"trial": r["trial"], "status": r["status"],
                            **({"setup_error": r["setup_error"]} if r.get("setup_error") else {}),
                            **({"error_tail": r["error_tail"]} if r.get("error_tail") and spec["track"] == "A" else {}),
                            **({"metric_errors": r["metric_errors"]} if r.get("metric_errors") else {})} for r in rows]
        ok = [r for r in rows if r["status"] == "ok" and "efficiency" in r]
        entry["metrics"] = {k: s for k in SCALARS if (s := _stats([_get(r, k) for r in ok]))}
        if ok:
            keys = [r.get("capability_keys", []) for r in ok]
            entry["capability_overlap_jaccard_pairwise"] = [_jaccard(a, b) for a, b in combinations(keys, 2)]
            entry["deterministic_action_sequences"] = len({r.get("action_sequence_digest") for r in ok}) == 1
            entry["identical_initial_state_group"] = len({r.get("first_state_group") for r in ok}) == 1
            entry["identical_config"] = len({r.get("config_digest") for r in ok}) == 1
            entry["terminated_by"] = sorted({_get(r, "efficiency.terminated_by") for r in ok})
            entry["model_calls_total"] = sum(r.get("model_calls") or 0 for r in ok)
            curves = [_get(r, "gt.curves") for r in ok]
            if all(curves):
                entry["recall_curve_actions_median"] = [round(median(c["actions"]["recall"][i] for c in curves), 4)
                                                        for i in range(11)]
                entry["recall_curve_seconds_median"] = [round(median(c["seconds"]["recall"][i] for c in curves), 4)
                                                        for i in range(11)]
                entry["precision_curve_actions_median"] = [
                    (round(median(v), 4) if (v := [c["actions"]["precision"][i] for c in curves
                                                  if c["actions"]["precision"][i] is not None]) else None)
                    for i in range(11)]
            if spec["track"] == "A":
                unmatched = [set(_get(r, "gt.unmatched_gt") or []) for r in ok]
                if any(unmatched):
                    entry["gt_missed_in_all_trials"] = sorted(set.intersection(*unmatched))
                    entry["gt_missed_in_some_trials"] = sorted(set.union(*unmatched) - set.intersection(*unmatched))
                if ENVS[env]["gt"] in {"surface", "transfer", "crawl_maze", "crawlground", "server_state", "identity"}:
                    entry["gt_detail_per_trial"] = [r.get("gt") for r in ok]
            ac = [r.get("acg_comparison") for r in ok]
            entry["acg_comparison_median"] = {
                rep: {k: _stats([(a.get(rep) or {}).get(k) for a in ac])["median"]
                      for k in (ac[0].get(rep) or {}) if _stats([(a.get(rep) or {}).get(k) for a in ac])}
                for rep in ("graph_a", "offline_acg", "live_acg") if ac[0].get(rep)}
        out["environments"][env] = entry
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "agent1_comprehensive_summary.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    return out
