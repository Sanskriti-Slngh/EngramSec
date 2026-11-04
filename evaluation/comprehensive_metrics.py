"""Phase 4 metrics for the comprehensive Agent 1 evaluation (evaluator-side only).

Agent 1 never imports this module. Every quantity is computed from the frozen agent's
own outputs (run.json, graph_a.json, action ledger, evidence sink) after the run ends.
Ground truth is touched only by the `gt_*` functions, and only for environments that
have it. Outputs are aggregate numbers: no URLs, labels, payloads or identifiers.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from agent1.model.importer import import_run_artifact
from agent1.model.materialize import materialize
from agent1.model.schema import STATUS_RANK, Status

FRACTIONS = [round(i / 10, 1) for i in range(11)]          # 0%, 10%, ..., 100% of budget


# ------------------------------------------------------------------ helpers
def _route_template(url: str) -> str:
    from urllib.parse import urlsplit

    from agent1.model.routes import path_route
    return path_route(urlsplit(url or "").path or "/")


def _structure(method: str, url: str) -> str:
    from urllib.parse import parse_qsl, urlsplit
    params = sorted({k for k, _ in parse_qsl(urlsplit(url or "").query, keep_blank_values=True)})
    return f"{method.upper()} {_route_template(url)} ?{','.join(params)}"


def trapezoid(ys: list[float]) -> float:
    """Normalized trapezoidal AUC for y sampled at FRACTIONS (x in [0, 1])."""
    return round(sum((ys[i] + ys[i + 1]) / 2 * 0.1 for i in range(len(ys) - 1)), 4)


def cap_key(cap: dict, ops: dict[str, dict]) -> str:
    """Role-free identity of a capability for cross-trial overlap (no merge/split decisions implied)."""
    sig = sorted(f"{ops[o]['channel']}:{ops[o]['method']} {ops[o]['route']}" for o in cap["operation_ids"] if o in ops)
    if not sig:
        sig = sorted(f"effect:{e['kind']}" for e in cap["effects"]) + sorted(f"label:{l['text']}" for l in cap.get("labels", []))
    return hashlib.sha256("|".join(sig).encode()).hexdigest()[:16]


# ------------------------------------------------------------------ discovery (4A)
def discovery(run: dict, graph: dict, export: dict) -> dict[str, Any]:
    obs = run.get("observations", []) + run.get("replay_observations", [])
    controls = {c.get("signature") for o in obs for c in o.get("controls", [])}
    executed = {t["action"].get("signature") or t["action"].get("css_path") for t in run.get("transitions", [])}
    structures = set()
    for t in run.get("transitions", []):
        for e in t.get("network", []):
            structures.add(_structure(e.get("method", "GET"), e.get("url", "")))
    for n in run.get("navigation_evidence", []) or []:
        for e in n.get("network", []):
            structures.add(_structure(e.get("method", "GET"), e.get("url", "")))
    ops = export["operations"]
    caps = export["capabilities"]
    states = graph["nodes"]["states"]
    return {
        "route_templates": len({s.get("route_pattern") for s in states}),
        "grouped_states": len(states),
        "raw_states": run["metrics"].get("raw_states"),
        "areas_route_title": len({(s.get("route_pattern"), s.get("title")) for s in states}),
        "acg_templates": len(export["templates"]),
        "acg_view_states": len(export["view_states"]),
        "unique_controls_observed": len(controls - {None}),
        "unique_controls_executed": len(executed - {None}),
        "advertised_unexecuted": len(graph.get("advertised_unexecuted", [])),
        "affordances": len(export["affordances"]),
        "affordance_families": len({json.dumps(a["family"], sort_keys=True) for a in export["affordances"]}),
        "request_structures_browser": len(structures),
        "acg_operations": len(ops),
        "acg_operations_http": sum(o["channel"] == "http" for o in ops),
        "websocket_operations": sum(o["channel"].startswith("websocket") for o in ops),
        "client_only_capabilities": sum(1 for c in caps if not c["operation_ids"]
                                        and STATUS_RANK.get(c["status"], -1) >= STATUS_RANK[Status.OBSERVED]),
        "entity_types": len(export["entity_types"]),
        "entity_instances": len(export["entity_instances"]),
        "roles": len({c["role"] for c in caps} | {t["role"] for t in export["templates"]}),
        "resource_references": run["metrics"].get("resource_references_discovered"),
    }


# ------------------------------------------------------------------ capabilities (4B) and evidence status (4C)
def capabilities(export: dict, graph: dict) -> dict[str, Any]:
    caps = export["capabilities"]
    at_least_observed = [c for c in caps if STATUS_RANK.get(c["status"], -1) >= STATUS_RANK[Status.OBSERVED]]
    roles = Counter(c["role"] for c in at_least_observed)
    preds = Counter(p["kind"] for p in export["learned_predicates"])
    multi_entry = sum(1 for c in at_least_observed if len({b["affordance_id"] for b in c["bindings"]}) > 1)
    status = Counter(str(c["status"]) for c in caps)
    aff_status = Counter(a["status"] for a in export["affordances"])
    skip = Counter((a.get("control") or {}).get("skip_reason") or "unexecuted_not_selected"
                   for a in graph.get("advertised_unexecuted", []))
    return {
        "distinct_capabilities_observed_or_better": len(at_least_observed),
        "by_behavioral_class": dict(Counter((c.get("behavioral_class") or {}).get("name", "unidentified")
                                            for c in at_least_observed)),
        "unidentified": sum(1 for c in at_least_observed if c.get("unidentified", True)),
        "equivalent_interfaces_multi_entry": multi_entry,
        "role_conditioned": {"roles": len(roles), "capabilities_in_non_primary_roles":
                             sum(n for r, n in roles.items() if "+" in r)},
        "dependencies_learned_predicates": dict(preds),
        "evidence_status": {
            "advertised_unexecuted_controls": len(graph.get("advertised_unexecuted", [])),
            "hypothesized": status.get("hypothesized", 0),
            "attempted_failed_affordances": aff_status.get("failed", 0),
            "executed_no_effect_affordances": aff_status.get("executed_no_effect", 0),
            "observed": status.get("observed", 0), "reproduced": status.get("reproduced", 0),
            "verified": status.get("verified", 0), "refuted": status.get("refuted", 0),
            "blocked_capabilities": status.get("blocked", 0),
            "blocked_affordances": aff_status.get("blocked", 0),
            "advertised_by_skip_reason": dict(skip),
        },
        "claims_by_status": dict(Counter(str(c["status"]) for c in export["claims"])),
        "capture_gaps": sorted({g["kind"] for g in export["gaps"]}),
    }


# ------------------------------------------------------------------ efficiency (4E, ground-truth free)
def efficiency(run: dict, explorer_http: dict[str, Any], cfg: dict) -> dict[str, Any]:
    m = run["metrics"]
    seen_states: set[str] = set()
    seen_structs: set[str] = set()
    unique = redundant = failed = 0
    errors: Counter = Counter()
    for t in run.get("transitions", []):
        if t.get("error") or not t.get("result_observation_id"):
            failed += 1
            errors[(t.get("error") or "no_result").split(":", 1)[0][:40]] += 1
            continue
        structs = {_structure(e.get("method", "GET"), e.get("url", "")) for e in t.get("network", [])}
        new = (t.get("result_group_signature") not in seen_states) or bool(structs - seen_structs)
        seen_states.add(t.get("result_group_signature"))
        seen_structs |= structs
        unique += new
        redundant += not new
    replay_actions = sum(r.get("browser_actions", 0) for r in run.get("replays", []))
    actions = m.get("browser_actions", 0)
    elapsed = m.get("elapsed_seconds") or 0.0
    readiness_ms = (m.get("passive_readiness_wait_ms") or 0) + (m.get("interactive_readiness_wait_ms") or 0)
    settle_ms = cfg.get("settle_ms", 350) * actions
    return {
        "browser_actions": actions, "elapsed_seconds": round(elapsed, 2),
        "transitions_attempted": m.get("transitions_attempted"),
        "actions_unique_discovery": unique, "actions_redundant": redundant, "actions_failed": failed,
        "failed_action_error_classes": dict(errors),
        "restoration_actions": m.get("restoration_actions"), "root_reloads": m.get("root_reloads"),
        "verification_actions": replay_actions,
        "replays": {"attempts": m.get("replay_attempts"), "validated": m.get("replay_success_numerator"),
                    "failures": m.get("replay_failures"), "untested_paths": m.get("replay_untested_paths")},
        "failed_restorations": {"live_state_stale": m.get("live_state_stale"),
                                "startup_readiness_failures": m.get("startup_readiness_failures"),
                                "unsafe_restorations_suppressed": m.get("unsafe_restorations_suppressed")},
        "readiness_wait_ms": readiness_ms,
        "waiting_vs_executing_seconds_estimate": {
            "waiting": round((readiness_ms + settle_ms) / 1000, 1),
            "executing_and_overhead": round(max(0.0, elapsed - (readiness_ms + settle_ms) / 1000), 1),
            "note": "waiting = recorded readiness waits + configured settle_ms x browser actions (estimate)"},
        "http_by_source": {
            "navigation": m.get("navigation_network_events_recorded"),
            "action": sum(len(t.get("network", [])) for t in run.get("transitions", [])),
            "replay": sum(len(r.get("network", [])) for r in run.get("replays", [])),
            "passive_resource_fetches": m.get("resource_fetches_attempted"),
            "observed_total": m.get("observed_http_requests"),
            "budget_used": m.get("total_http_budget_used"), "budget_blocked": m.get("total_http_budget_blocked"),
            **explorer_http},
        "terminated_by": ("action_budget" if actions >= cfg["max_browser_actions"] else
                          "transition_budget" if (m.get("transitions_attempted") or 0) >= cfg["max_transitions"] else
                          "time_budget" if elapsed >= cfg["max_seconds"] - 1 else "frontier_exhausted_or_other"),
    }


# ------------------------------------------------------------------ prefixes for curves
def _stamps(run: dict, ledger: dict[str, list]) -> dict[str, list]:
    stamp = {}
    for collection, prefix in (("observations", "ev:observations:"), ("replay_observations", "ev:replay_observations:"),
                               ("transitions", "ev:transitions:"), ("replays", "ev:replays:")):
        for item in run.get(collection) or []:
            stamp[prefix + item["id"]] = ledger.get(item["id"], [10**9, 10**9])
    return stamp


def prefix_exports(run: dict, ledger: dict[str, list], app: str, cfg: dict):
    """(axis, fraction, records, export) at 0..100% of the action and wall-time budgets."""
    records = import_run_artifact(run, "run.json", app)
    stamp = _stamps(run, ledger)
    for axis, limit, index in (("actions", cfg["max_browser_actions"], 0), ("seconds", cfg["max_seconds"], 1)):
        for f in FRACTIONS:
            x = f * limit
            prefix = [r for r in records if r.kind == "capture_manifest" or stamp.get(r.id, [0, 0])[index] <= x]
            yield axis, f, prefix, materialize(prefix).model_dump(mode="json")


def discovery_curves(run: dict, ledger: dict, app: str, cfg: dict) -> dict[str, Any]:
    """Ground-truth-free growth curves (counts; no AUC: no defensible denominator)."""
    out: dict[str, Any] = {"actions": {"capabilities": [], "operations": [], "templates": []},
                           "seconds": {"capabilities": [], "operations": [], "templates": []}}
    for axis, _, _, exp in prefix_exports(run, ledger, app, cfg):
        out[axis]["capabilities"].append(sum(STATUS_RANK.get(c["status"], -1) >= 1 for c in exp["capabilities"]))
        out[axis]["operations"].append(len(exp["operations"]))
        out[axis]["templates"].append(len(exp["templates"]))
    return out


# ------------------------------------------------------------------ ground truth (4D, 4E, 4G)
def gt_capability(gt, run: dict, ledger: dict, app: str, cfg: dict, offline_export: dict, live_export: dict | None,
                  graph: dict) -> dict[str, Any]:
    from evaluation.score_acg import (map_actions, observation_paths, role_aware_precision, score_capabilities,
                                      score_identity, score_legacy_features)
    records = import_run_artifact(run, "run.json", app)
    final = score_capabilities(gt, offline_export, records)
    curves: dict[str, dict[str, list]] = {"actions": {"recall": [], "precision": [], "false_positives": []},
                                          "seconds": {"recall": [], "precision": [], "false_positives": []}}
    for axis, f, prefix, exp in prefix_exports(run, ledger, app, cfg):
        if f == 0:
            curves[axis]["recall"].append(0.0); curves[axis]["precision"].append(None)
            curves[axis]["false_positives"].append(0)
            continue
        s = score_capabilities(gt, exp, prefix)
        curves[axis]["recall"].append(round(s["m1a_recall"]["value"] or 0.0, 4))
        curves[axis]["precision"].append(None if s["m1a_precision"]["value"] is None else round(s["m1a_precision"]["value"], 4))
        curves[axis]["false_positives"].append(len(s["unmatched_acg"]))
    ident = score_identity(gt, offline_export, observation_paths(records))
    # GT-redundant observed transitions (same ground-truth capability already reached)
    mapping = map_actions(gt, records)
    seen: set[str] = set(); gt_redundant = observed = 0
    for t in run.get("transitions", []):
        if t.get("result_observation_id") is None or t.get("error"):
            continue
        observed += 1
        truth = mapping.get(t["id"])
        if truth and not str(truth).startswith(("ambiguous", "non:")):
            gt_redundant += truth in seen
            seen.add(truth)
    # 4G: role-conditioned coverage (author-defined; canonical M1a above is the frozen measure)
    role_cookies = {r.id: set(r.cookie_names) for r in gt.roles}
    ops = {o["id"]: o for o in offline_export["operations"]}
    from evaluation.score_acg import _op_matches
    pairs = [(c.id, r) for c in gt.capabilities if c.in_scope for r in c.roles]
    by_cid = {c["id"]: c for c in offline_export["capabilities"]}
    hit = 0
    for cid, role in pairs:
        if cid not in final["matches"]:          # never above canonical: requires the frozen one-to-one match
            continue
        g = next(c for c in gt.capabilities if c.id == cid)
        want = role_cookies.get(role, set())
        for c in offline_export["capabilities"]:
            if STATUS_RANK.get(c["status"], -1) < 1:
                continue
            acg_cookies = set(c["role"].split("+", 1)[1].split(",")) if "+" in c["role"] else set()
            role_ok = (acg_cookies >= want) if want else not acg_cookies
            same = (c["id"] == final["matches"][cid] or
                    (g.operations and any(_op_matches(o, ops[x]) for o in g.operations for x in c["operation_ids"])))
            if role_ok and same:
                hit += 1
                break
    del by_cid
    live = score_capabilities(gt, live_export, records) if live_export else None
    graph_a = score_legacy_features(gt, graph["nodes"].get("features", []), records)
    return {
        "denominator": final["m1a_recall"]["denominator"],
        "final_recall": final["m1a_recall"]["value"], "final_precision": final["m1a_precision"]["value"],
        "matched": final["m1a_recall"]["matched"], "acg_capabilities_scored": final["m1a_precision"]["denominator"],
        "false_positives": len(final["unmatched_acg"]),
        "unmatched_gt": final["unmatched_gt"],                      # development annotations only (Track A)
        "m1b": {"precision": final["m1b_precision"]["value"], "recall": final["m1b_recall"]["value"]},
        "incorrect_capability_merges": len(final["capability_merges"].get("incorrect_merges") or []),
        "capability_splits": len(final["capability_merges"].get("splits") or final["capability_merges"].get("incorrect_splits") or []),
        "incorrect_record_merges": len(ident.get("incorrect_entity_merges") or []),
        "curves": curves,
        "auc_actions": trapezoid(curves["actions"]["recall"]), "auc_seconds": trapezoid(curves["seconds"]["recall"]),
        "gt_redundant_transitions": gt_redundant, "observed_transitions": observed,
        "role_conditioned": {"pairs": len(pairs), "covered": hit, "recall": round(hit / len(pairs), 4) if pairs else None,
                             "definition": "GT (capability, role) pair covered if the GT capability is matched by the frozen "
                                           "one-to-one M1a AND the matched (or an operation-equivalent) observed ACG "
                                           "capability exists in an ACG role whose cookie names include the GT role's "
                                           "(anonymous = no session cookies). Author-defined; never exceeds canonical."},
        "role_aware_precision_alt": role_aware_precision(gt, offline_export, final)["value"],
        "live_acg": {"recall": live["m1a_recall"]["value"], "precision": live["m1a_precision"]["value"]} if live else None,
        "graph_a_features": {"features": graph_a["features"], "action_based_recall": graph_a["action_based_recall"]},
    }


def gt_surface(graph: dict, truth: dict) -> dict[str, Any]:
    import importlib.util
    spec = importlib.util.spec_from_file_location("evaluate_coverage", Path(__file__).resolve().parents[1] /
                                                  "experiments" / "evaluate_coverage.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.evaluate(graph, truth)


def acg_comparison(graph: dict, offline: dict, live: dict | None) -> dict[str, Any]:
    """Phase 7: what each representation contains (counts only)."""
    def acg(e: dict) -> dict:
        return {"templates": len(e["templates"]), "view_states": len(e["view_states"]),
                "operations": len(e["operations"]), "affordances": len(e["affordances"]),
                "capabilities_observed_or_better": sum(STATUS_RANK.get(c["status"], -1) >= 1 for c in e["capabilities"]),
                "capabilities_reproduced_or_better": sum(STATUS_RANK.get(c["status"], -1) >= 2 for c in e["capabilities"]),
                "capabilities_verified": sum(str(c["status"]) == "verified" for c in e["capabilities"]),
                "behavioral_classes": sum(1 for c in e["capabilities"] if c.get("behavioral_class")),
                "entity_types": len(e["entity_types"]), "entity_instances": len(e["entity_instances"]),
                "learned_predicates": len(e["learned_predicates"]), "claims": len(e["claims"]),
                "websocket_operations": sum(o["channel"].startswith("websocket") for o in e["operations"]),
                "gaps": sorted({g["kind"] for g in e["gaps"]})}
    n = graph["nodes"]
    return {"graph_a": {"states": len(n["states"]), "actions_evidence": len(n["actions_evidence"]),
                        "functional_workflows": len(n.get("functional_workflows", [])),
                        "features": len(n.get("features", [])), "record_instances": len(n.get("record_instances", [])),
                        "edges": len(graph["edges"]), "advertised_unexecuted": len(graph.get("advertised_unexecuted", []))},
            "offline_acg": acg(offline), "live_acg": acg(live) if live else None}
