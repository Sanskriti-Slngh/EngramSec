#!/usr/bin/env python3
"""Offline summary of the runtime-interaction ablation (arms A/B/C).

Post-run only; never imported by Agent 1. Primary metrics are about
interaction behavior: listener candidates, handler revisions, executed and
independently replayed actions, action-triggered request structures, CDP
cost. For Crawl Maze the historical strict-2xx /91 score is a secondary
column, computed by the existing offline scorer.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from summarize_discovery_ablation import summarize as crawlmaze_summary  # offline scorer

NON_EFFECT = {"xhr", "fetch"}


def structure(event: dict) -> tuple[str, str, tuple[str, ...]] | None:
    if event.get("resource_type") in NON_EFFECT or event["method"] not in {"GET", "HEAD"}:
        return event["method"], urlsplit(event["url"]).path, tuple(event.get("parameter_names") or [])
    return None


def behavior(run_dir: Path) -> dict:
    run = json.loads((run_dir / "run.json").read_text())
    metrics = run["metrics"]
    observed = [t for t in run["transitions"] if t["status"] != "failed"]
    validated = {r["transition_id"] for r in run["replays"] if r["status"] == "replay_validated"}
    structures = {s for t in observed for e in t.get("network", []) if (s := structure(e))}
    validated_structures = {s for t in observed if t["id"] in validated for e in t.get("network", []) if (s := structure(e))}
    listener = [t for t in observed if t["action"].get("provenance") == "observed_listener"]
    revisits = [t for t in observed if t["action"].get("behavior_revision")]

    def effect(t: dict) -> bool:
        return (t["source_group_signature"] != t.get("result_group_signature") or bool(t.get("dialogs"))
                or any(structure(e) or e.get("resource_type") == "document" for e in t.get("network", [])))

    candidates = {(c["signature"], c["label"]) for o in run["observations"] for c in o["controls"]
                  if c.get("provenance") == "observed_listener"}
    unsafe = {(c["signature"], c["label"], c.get("skip_reason")) for o in run["observations"] for c in o["controls"]
              if c.get("provenance") == "observed_listener" and not c["safe"]}
    integrity = audit(run_dir, run, observed, validated, listener, revisits)
    actions = metrics.get("browser_actions") or 1
    elapsed = metrics.get("elapsed_seconds") or 1
    return {
        "browser_actions": metrics.get("browser_actions"),
        "transitions_observed": metrics.get("transitions_observed"),
        "replays": f"{metrics.get('replay_success_numerator')}/{metrics.get('replay_success_denominator')}",
        "action_request_structures": len(structures),
        "action_request_structures_replay_validated": len(validated_structures),
        "request_structures_per_100_actions": round(100 * len(structures) / actions, 2),
        "listener_candidates_recorded": len(candidates),
        "listener_candidates_unsafe": sorted(f"{label[:40]} ({reason})" for _, label, reason in unsafe),
        "listener_actions_executed": len(listener),
        "listener_actions_replay_validated": sum(t["id"] in validated for t in listener),
        "listener_actions_without_observable_effect": sorted({t["action"]["label"][:50] for t in listener if not effect(t)}),
        "listener_executed_labels": sorted({t["action"]["label"][:50] for t in listener}),
        "revisit_actions_executed": len(revisits),
        "revisit_actions_replay_validated": sum(t["id"] in validated for t in revisits),
        "revisit_labels": sorted({t["action"]["label"][:50] for t in revisits}),
        "new_structures_from_listener_or_revisit": sorted({
            f"{s[0]} {s[1]}" for t in listener + revisits for e in t.get("network", []) if (s := structure(e))}),
        "cdp_ms_total": metrics.get("listener_observation_ms"),
        "cdp_ms_per_observation": round((metrics.get("listener_observation_ms") or 0) / max(1, metrics.get("listener_observations") or 0), 2),
        "cdp_share_of_runtime": round((metrics.get("listener_observation_ms") or 0) / 1000 / elapsed, 4),
        "cdp_calls": metrics.get("listener_cdp_calls"),
        "listener_observation_errors": metrics.get("listener_observation_errors"),
        "listener_skipped": metrics.get("listener_skipped"),
        "handler_revisions_observed": metrics.get("handler_revisions_observed"),
        "behavior_divergent_groups": metrics.get("behavior_divergent_groups"),
        "incorrect_state_merges": metrics.get("incorrect_state_merges"),
        "graph_connections_missing_evidence": metrics.get("graph_connections_missing_evidence"),
        "graph_connections_total": metrics.get("graph_connections_total"),
        "elapsed_seconds": metrics.get("elapsed_seconds"),
        "python_peak_rss_mb": metrics.get("python_peak_rss_mb"),
        "http_total": metrics.get("total_http_budget_used"),
        "integrity": integrity,
    }


def audit(run_dir: Path, run: dict, observed: list, validated: set, listener: list, revisits: list) -> dict:
    """Graph A behavior-evidence integrity checks; each value should be 0 unless noted."""
    graph_text = (run_dir / "graph_a.json").read_text()
    graph = json.loads(graph_text)
    claims = [c for c in graph["connection_evidence"] if c["claim_type"] in {"listener_candidate", "handler_revision"}]
    observations = {o["id"]: o for o in run["observations"]}
    skipped_paths = {(o["id"], ex.get("css_path")) for o in run["observations"] if o.get("listener_evidence")
                     for ex in o["listener_evidence"].get("skipped_examples", [])}
    by_replay = {r["transition_id"]: r for r in run["replays"]}

    def network_only(t: dict) -> bool:
        return t["source_group_signature"] == t.get("result_group_signature") and not t.get("dialogs") and any(
            structure(e) for e in t.get("network", []))

    cookie_values = [r for r in run["resource_evidence"] if any(
        "=" in str(n) for n in (r.get("session_cookie_names") or []) + (r.get("set_cookie_names") or []))]
    return {
        "listener_or_revision_claims_incomplete": sum(not c["complete"] for c in claims),
        "listener_actions_without_candidate_claim": sum(
            1 for t in listener if not any(c["subject_id"] == t["id"] and c["claim_type"] == "listener_candidate" for c in claims)),
        "revisits_without_revision_claim": sum(
            1 for t in revisits if not any(c["subject_id"] == t["id"] and c["claim_type"] == "handler_revision" for c in claims)),
        "unsafe_listener_actions_executed": sum(
            1 for t in listener for c in observations.get(t["source_observation_id"], {}).get("controls", [])
            if c["id"] == t["action"]["control_id"] and not c["safe"]),
        "skipped_listener_elements_executed": sum(
            1 for t in listener if (t["source_observation_id"], t["action"]["css_path"]) in skipped_paths),
        "revisits_in_observe_mode": sum(1 for t in revisits if run["config"].get("runtime_listener_observation") != "revisit"),
        "validated_network_only_replays_without_request_check": sum(
            1 for t in observed if t["id"] in validated and network_only(t)
            and not by_replay.get(t["id"], {}).get("outcome_checks", {}).get("request_structures")),
        "same_dom_different_behavior_transitions (informational)": sum(
            1 for t in observed if t["source_group_signature"] == t.get("result_group_signature")
            and (observations.get(t["source_observation_id"], {}).get("behavior_signature") or t["source_group_signature"])
            != (observations.get(t.get("result_observation_id") or "", {}).get("behavior_signature") or t["source_group_signature"])),
        "observations_with_mixed_session_context": len({o["session_context"] for o in run["observations"]}) - 1,
        "cookie_values_in_resource_evidence": len(cookie_values),
        "replays_validated_in_exploration_context": sum(1 for r in run["replays"] if r["status"] == "replay_validated"
                                                       and r.get("actual_observation_id") in observations),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--crawlmaze", action="store_true", help="also compute the strict-2xx /91 secondary score")
    ap.add_argument("--expected", type=Path, default=Path("/private/tmp/security-crawl-maze/blueprints/utils/resources/expected-results.json"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    rows, hits = {}, {}
    for run_dir in sorted(p.parent for p in args.root.glob("*/run.json")):
        name = run_dir.name.removeprefix("adaptive_readiness_")
        rows[name] = behavior(run_dir)
        if args.crawlmaze:
            expected = json.loads(args.expected.read_text())
            row, detail = crawlmaze_summary(run_dir, expected)
            rows[name]["raw_2xx_91"] = row["raw_2xx_91"]
            rows[name]["supported_2xx_84"] = row["supported_2xx_84"]
            rows[name]["request_surface_any_status_91"] = row["request_surface_any_status_91"]
            rows[name]["evidence_audit"] = row["evidence_audit"]
            hits[name] = set(detail["hits"])
    baseline = next((n for n in rows if n.startswith("A")), None)
    if args.crawlmaze and baseline:
        for name in rows:
            rows[name]["gained_vs_A"] = sorted(hits[name] - hits[baseline])
            rows[name]["lost_vs_A"] = sorted(hits[baseline] - hits[name])
    args.out.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    for name, r in rows.items():
        print(name, {k: r[k] for k in ("browser_actions", "transitions_observed", "replays", "action_request_structures",
                                         "action_request_structures_replay_validated", "listener_actions_executed",
                                         "listener_actions_replay_validated", "revisit_actions_executed",
                                         "revisit_actions_replay_validated", "cdp_ms_per_observation", "cdp_share_of_runtime",
                                         "graph_connections_missing_evidence", "incorrect_state_merges")},
              *([f"raw={r['raw_2xx_91']}/91 +{len(r.get('gained_vs_A', []))} -{len(r.get('lost_vs_A', []))}"] if args.crawlmaze else []))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
