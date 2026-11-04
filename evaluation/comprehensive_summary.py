"""Aggregate comprehensive-evaluation trials into evaluation/results/agent1_comprehensive_summary.json.

Per environment: every trial's status (failed/incomplete trials are listed, never dropped),
median/min/max of the preregistered metrics, cross-trial capability-set overlap (Jaccard),
determinism (identical executed-action sequences), initial-state and configuration
equivalence, trial-reset integrity. Track B (WebExploitBench) entries contain aggregate
numbers only, grouped into separate report sections, and never a coverage percentage: without
independent capability ground truth the fraction of an application's functionality captured
cannot be established.
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
    "discovery.entity_types", "discovery.entity_instances", "discovery.session_contexts",
    "capabilities.distinct_capabilities_observed_or_better", "capabilities.unidentified",
    "capabilities.equivalent_interfaces_multi_entry", "capabilities.operations_without_capability",
    "capabilities.session_conditioned.capabilities_in_cookie_session_contexts",
    "capabilities.evidence_status.advertised_unexecuted_controls", "capabilities.evidence_status.hypothesized",
    "capabilities.evidence_status.executed_no_effect_affordances", "capabilities.evidence_status.refuted",
    "capabilities.evidence_status.blocked_capabilities",
    "capabilities.refusals.safety_refusals_total", "capabilities.refusals.scope_refusals",
    "capabilities.refusals.technical_unobservable", "capabilities.refusals.not_selected",
    "capabilities.refusals.safety_refusals_by_configuration.post_forms_disabled",
    "capabilities.refusals.safety_refusals_by_configuration.dangerous_label_or_target",
    "capabilities.refusals.safety_refusals_by_configuration.requires_protected_or_file_input",
    "capabilities.evidence_status.observed", "capabilities.evidence_status.reproduced",
    "capabilities.evidence_status.verified", "capabilities.evidence_status.attempted_failed_affordances",
    "capabilities.evidence_status.blocked_affordances",
    "safety.state_changing_requests_issued", "safety.state_changing_requests_in_replay",
    "safety.dangerous_controls_skipped", "safety.destructive_endpoint_hits", "safety.repeated_write_endpoint_hits",
    "safety.unsupported_functional_claims", "safety.ws_out_of_scope_refused",
    "reference.annotation_recall", "reference.annotation_precision", "reference.auc_actions",
    "reference.auc_seconds", "reference.false_positives",
    "reference.incorrect_capability_merges", "reference.capability_splits", "reference.incorrect_record_merges",
    "reference.session_conditioned.recall", "reference.session_aware_precision_alt",
    "reference.annotation_recall_excluding_safety_refusals.value",
    "reference.live_acg.recall", "reference.live_acg.precision",
    "reference.graph_a_features.action_based_recall", "reference.gt_redundant_transitions",
    "reference.observed_transitions", "reference.recall", "reference.markers_scored",
    "setup_seconds", "teardown_seconds", "child_seconds", "mem_mb_after_setup", "mem_mb_peak_during_run",
]


# Track B: no reference data. Each section is reported on its own; none is a coverage percentage.
TRACK_B_SECTIONS: dict[str, list[str]] = {
    "functional_inventory": [
        "capabilities.distinct_capabilities_observed_or_better", "discovery.acg_operations",
        "discovery.websocket_operations", "discovery.client_only_capabilities", "discovery.affordances",
        "discovery.affordance_families", "discovery.request_structures_browser", "discovery.route_templates",
        "discovery.acg_templates", "discovery.grouped_states", "discovery.areas_route_title",
        "discovery.unique_controls_observed", "discovery.unique_controls_executed",
        "capabilities.equivalent_interfaces_multi_entry", "discovery.session_contexts"],
    "evidence_quality": [
        "capabilities.evidence_status.observed", "capabilities.evidence_status.reproduced",
        "capabilities.evidence_status.hypothesized", "capabilities.evidence_status.executed_no_effect_affordances",
        "capabilities.evidence_status.attempted_failed_affordances", "capabilities.evidence_status.refuted",
        "efficiency.replays.attempts", "efficiency.replays.validated", "efficiency.replays.failures",
        "efficiency.actions_failed"],
    "unidentified_operations": ["capabilities.unidentified", "capabilities.operations_without_capability"],
    "blocked_functionality": [
        "capabilities.evidence_status.advertised_unexecuted_controls",
        "capabilities.refusals.safety_refusals_total",
        "capabilities.refusals.safety_refusals_by_configuration.post_forms_disabled",
        "capabilities.refusals.safety_refusals_by_configuration.dangerous_label_or_target",
        "capabilities.refusals.safety_refusals_by_configuration.requires_protected_or_file_input",
        "capabilities.refusals.scope_refusals", "capabilities.refusals.technical_unobservable",
        "capabilities.refusals.not_selected", "capabilities.evidence_status.blocked_capabilities",
        "capabilities.evidence_status.blocked_affordances", "efficiency.http_by_source.blocked_out_of_scope",
        "safety.ws_out_of_scope_refused"],
    "entity_identity": ["discovery.entity_types", "discovery.entity_instances"],
    "verification_status": ["capabilities.evidence_status.verified", "safety.unsupported_functional_claims"],
}
TRACK_B_NOT_MEASURABLE = ("NOT MEASURABLE: without independent capability ground truth, the percentage of this "
                          "application's functionality that Agent 1 captured cannot be established. Discovery counts "
                          "are inventories, not coverage percentages.")


def _reset_integrity(rows: list[dict]) -> dict[str, Any]:
    resets = [r.get("reset") or {} for r in rows]
    ids = [set(x.get("container_ids") or []) for x in resets]
    vols = [set(x.get("volume_names") or []) for x in resets]
    out: dict[str, Any] = {
        "reset_failures": sum(r["status"] == "reset_failure" for r in rows),
        "teardown_exit": [x.get("teardown_exit") for x in resets],
        "residual_containers_after_teardown": [x.get("residual_containers_after_teardown") for x in resets],
        "mount_profile_matches_frozen": [x.get("mount_profile_matches_frozen") for x in resets],
    }
    if any(ids):
        out["container_ids_disjoint_across_trials"] = all(not (a & b) for a, b in combinations(ids, 2))
        out["volume_names_disjoint_across_trials"] = all(not (a & b) for a, b in combinations(vols, 2))
        out["tmpfs_mounts"] = [x.get("tmpfs_mounts") for x in resets]
        out["writable_bind_mounts"] = [x.get("writable_bind_mounts") for x in resets]
    if any("initial_state_digest" in x for x in resets):
        out["inproc_initial_state_identical"] = len({x.get("initial_state_digest") for x in resets}) == 1
        out["inproc_initial_server_log_empty"] = all(x.get("initial_server_log_len") == 0 for x in resets)
        out["inproc_fixture_gone_after_trial"] = [x.get("fixture_server_gone_after_trial") for x in resets]
    return out


def _jaccard(a: list, b: list) -> float | None:
    sa, sb = set(a), set(b)
    return round(len(sa & sb) / len(sa | sb), 4) if sa | sb else None


def summarize(base: Path, post_diagnostic: bool = False, out_path: Path | None = None) -> dict:
    from evaluation.comprehensive_eval import POST_DIAGNOSTIC_OVERRIDE
    out: dict[str, Any] = {
        "milestone": "Agent 1 comprehensive benchmark evaluation"
                     + (" — supplementary safe-isolated write diagnostic (Track S, not primary)" if post_diagnostic else ""),
        "evaluated_revision": git_revision(),
        "frozen_config": FROZEN, "instrumentation": INSTRUMENTATION,
        **({"diagnostic_override": POST_DIAGNOSTIC_OVERRIDE} if post_diagnostic else {}),
        "terminology": {
            "annotation_recall/precision": "computed against frozen author-curated development annotations; "
                                           "not independently established application ground truth",
            "session_conditioned": "ACG roles are cookie-name session contexts, not semantic authorization roles",
            "track_b": TRACK_B_NOT_MEASURABLE},
        "not_evaluated": {"webexploitbench_gated_targets": GATED, "reason": "NOT EVALUATED — ACCESS RESTRICTED"},
        "environments": {},
    }
    for env, spec in ENVS.items():
        rows = [json.loads(p.read_text()) for p in sorted((base / env).glob("trial_*/trial.json"))]
        if post_diagnostic and not rows:
            continue
        entry: dict[str, Any] = {k: spec[k] for k in ("track", "category", "exposure")}
        entry["reference_kind"] = spec["gt"] or "none"
        entry["trials"] = [{"trial": r["trial"], "status": r["status"],
                            **({"setup_error": r["setup_error"]} if r.get("setup_error") else {}),
                            **({"error_tail": r["error_tail"]} if r.get("error_tail") and spec["track"] == "A" else {}),
                            **({"metric_errors": r["metric_errors"]} if r.get("metric_errors") else {})} for r in rows]
        ok = [r for r in rows if r["status"] == "ok" and "efficiency" in r]
        entry["reset_integrity"] = _reset_integrity(rows)
        if spec["track"] == "B":
            entry["functional_coverage_percentage"] = TRACK_B_NOT_MEASURABLE
            entry["report_sections"] = {sec: {k: s for k in keys if (s := _stats([_get(r, k) for r in ok]))}
                                        for sec, keys in TRACK_B_SECTIONS.items()}
            entry["report_sections"]["blocked_functionality"]["failed_action_error_classes_per_trial"] = [
                _get(r, "efficiency.failed_action_error_classes") for r in ok]
            entry["report_sections"]["functional_inventory"]["by_behavioral_class_per_trial"] = [
                _get(r, "capabilities.by_behavioral_class") for r in ok]
            entry["report_sections"]["verification_status"]["claims_by_status_per_trial"] = [
                _get(r, "capabilities.claims_by_status") for r in ok]
            entry["report_sections"]["evidence_quality"]["capture_gaps_per_trial"] = [
                _get(r, "capabilities.capture_gaps") for r in ok]
            listed = {k for keys in TRACK_B_SECTIONS.values() for k in keys}
            entry["metrics"] = {k: s for k in SCALARS if k not in listed and not k.startswith("reference.")
                                and (s := _stats([_get(r, k) for r in ok]))}
        else:
            entry["metrics"] = {k: s for k in SCALARS if (s := _stats([_get(r, k) for r in ok]))}
        if ok:
            keys = [r.get("capability_keys", []) for r in ok]
            entry["capability_overlap_jaccard_pairwise"] = [_jaccard(a, b) for a, b in combinations(keys, 2)]
            entry["deterministic_action_sequences"] = len({r.get("action_sequence_digest") for r in ok}) == 1
            entry["identical_initial_state_group"] = len({r.get("first_state_group") for r in ok}) == 1
            entry["identical_config"] = len({r.get("config_digest") for r in ok}) == 1
            entry["terminated_by"] = sorted({_get(r, "efficiency.terminated_by") for r in ok})
            entry["model_calls_total"] = sum(r.get("model_calls") or 0 for r in ok)
            curves = [_get(r, "reference.curves") for r in ok]
            if all(curves):
                entry["annotation_recall_curve_actions_median"] = [
                    round(median(c["actions"]["recall"][i] for c in curves), 4) for i in range(11)]
                entry["annotation_recall_curve_seconds_median"] = [
                    round(median(c["seconds"]["recall"][i] for c in curves), 4) for i in range(11)]
                entry["annotation_precision_curve_actions_median"] = [
                    (round(median(v), 4) if (v := [c["actions"]["precision"][i] for c in curves
                                                  if c["actions"]["precision"][i] is not None]) else None)
                    for i in range(11)]
            if spec["track"] == "A":
                entry["reference_basis"] = ok[0].get("reference_basis")
                unmatched = [set(_get(r, "reference.unmatched_annotated") or []) for r in ok]
                if any(unmatched):
                    entry["annotated_missed_in_all_trials"] = sorted(set.intersection(*unmatched))
                    entry["annotated_missed_in_some_trials"] = sorted(set.union(*unmatched) - set.intersection(*unmatched))
                    entry["missed_attribution_per_trial"] = [_get(r, "reference.missed_attribution") for r in ok]
                    entry["missed_by_class_per_trial"] = [_get(r, "reference.missed_by_class") for r in ok]
                if ENVS[env]["gt"] in {"surface", "transfer", "crawl_maze", "crawlground", "server_state", "identity"}:
                    entry["reference_detail_per_trial"] = [r.get("reference") for r in ok]
            ac = [r.get("acg_comparison") for r in ok]
            entry["acg_comparison_median"] = {
                rep: {k: _stats([(a.get(rep) or {}).get(k) for a in ac])["median"]
                      for k in (ac[0].get(rep) or {}) if _stats([(a.get(rep) or {}).get(k) for a in ac])}
                for rep in ("graph_a", "offline_acg", "live_acg") if ac[0].get(rep)}
        out["environments"][env] = entry
    target = out_path or (RESULTS / ("agent1_post_diagnostic_summary.json" if post_diagnostic
                                     else "agent1_comprehensive_summary.json"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=1, default=str) + "\n")
    return out
