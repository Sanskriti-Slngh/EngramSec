#!/usr/bin/env python3
"""Offline summary of the three-arm, three-seed Crawl Maze replay comparison.

Post-run only; never imported by Agent 1. Arms (experiments/run_runtime_ablation.sh):
R0 listener discovery off + shallow replay, R1 listener discovery on + shallow
replay, R2 listener discovery on + request-structure replay. Coverage uses the
historical offline strict-2xx scorer; runtime attribution and replay evidence
come from each run's own artifacts.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

from summarize_runtime_ablation import behavior, runtime_attribution  # offline helpers
from summarize_discovery_ablation import summarize as crawlmaze_summary

ARMS = ("R0", "R1", "R2")


def row(run_dir: Path, expected: list[str]) -> dict:
    run = json.loads((run_dir / "run.json").read_text())
    graph = json.loads((run_dir / "graph_a.json").read_text())
    m = run["metrics"]
    scored, detail = crawlmaze_summary(run_dir, expected)
    b = behavior(run_dir)
    attribution = runtime_attribution(run_dir, expected)
    runtime_ids = {t["id"] for t in run["transitions"]
                   if t["action"].get("provenance") == "observed_listener" or t["action"].get("behavior_revision")}
    runtime_replays = [r for r in run["replays"] if r["transition_id"] in runtime_ids]
    replay_evidence = graph.get("replay_evidence", {}).get("summary", {})
    return {
        "markers_2xx_91": scored["raw_2xx_91"],
        "hits": sorted(detail["hits"]),
        "markers_via_runtime_actions": len(attribution["via_runtime_actions"]),
        "markers_exclusive_to_runtime_actions": len(attribution["exclusive_to_runtime_actions"]),
        "runtime_behaviors_observed": m.get("runtime_behaviors_observed", 0),
        "runtime_behaviors_replay_validated": m.get("runtime_behaviors_replay_validated", 0),
        "runtime_replays_attempted": len(runtime_replays),
        "runtime_replay_failures": dict(Counter(r.get("failure_reason") for r in runtime_replays
                                                if r["status"] != "replay_validated")),
        "request_structures_observed": m.get("replay_structures_observed", 0),
        "request_structures_reproduced": m.get("replay_structures_verified", 0),
        "request_structures_failed": m.get("replay_structures_failed", 0),
        "request_structures_unattempted": m.get("replay_structures_unattempted", 0),
        "validated_workflows": m.get("replay_success_numerator"),
        "replays_attempted": m.get("replay_success_denominator"),
        "replay_failure_reasons": m.get("replay_failure_reasons", {}),
        "browser_actions": m.get("browser_actions"),
        "replay_browser_actions": m.get("replay_browser_actions"),
        "transitions_observed": m.get("transitions_observed"),
        "http_requests": m.get("total_http_budget_used"),
        "elapsed_seconds": m.get("elapsed_seconds"),
        "cdp_ms_per_observation": b["cdp_ms_per_observation"],
        "incorrect_state_merges": m.get("incorrect_state_merges"),
        "graph_connections_missing_evidence": m.get("graph_connections_missing_evidence"),
        "unsafe_listener_actions_executed": b["integrity"]["unsafe_listener_actions_executed"],
        "skipped_listener_elements_executed": b["integrity"]["skipped_listener_elements_executed"],
        "scheduler": m.get("replay_scheduler", {}),
        "graph_replay_evidence": replay_evidence,
    }


def aggregate(values: list[float]) -> dict:
    return {"mean": round(statistics.mean(values), 2), "min": min(values), "max": max(values)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--expected", type=Path,
                    default=Path("/private/tmp/security-crawl-maze/blueprints/utils/resources/expected-results.json"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    expected = json.loads(args.expected.read_text())
    rows: dict[str, dict] = {}
    for run_dir in sorted(p.parent for p in args.root.glob("*/run.json")):
        rows[run_dir.name.removeprefix("adaptive_readiness_")] = row(run_dir, expected)
    seeds = sorted({name.split("_s", 1)[1] for name in rows if "_s" in name})
    for seed in seeds:
        base = rows.get(f"R0_s{seed}")
        for arm in ARMS:
            r = rows.get(f"{arm}_s{seed}")
            if r and base:
                r["gained_vs_R0_same_seed"] = sorted(set(r["hits"]) - set(base["hits"]))
                r["lost_vs_R0_same_seed"] = sorted(set(base["hits"]) - set(r["hits"]))
    numeric = [k for k, v in next(iter(rows.values())).items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    arms = {}
    for arm in ARMS:
        members = [rows[f"{arm}_s{s}"] for s in seeds if f"{arm}_s{s}" in rows]
        if members:
            arms[arm] = {k: aggregate([m[k] for m in members if m.get(k) is not None]) for k in numeric
                         if any(m.get(k) is not None for m in members)}
            arms[arm]["runs"] = len(members)
    args.out.write_text(json.dumps({"runs": rows, "arms": arms}, indent=2, sort_keys=True) + "\n")
    keys = ("markers_2xx_91", "markers_via_runtime_actions", "runtime_behaviors_observed",
            "runtime_behaviors_replay_validated", "request_structures_observed", "request_structures_reproduced",
            "validated_workflows", "replays_attempted", "browser_actions", "replay_browser_actions", "http_requests",
            "incorrect_state_merges", "graph_connections_missing_evidence", "unsafe_listener_actions_executed")
    for name, r in rows.items():
        print(name, {k: r[k] for k in keys}, "+", len(r.get("gained_vs_R0_same_seed", [])), "-",
              len(r.get("lost_vs_R0_same_seed", [])))
    for arm, a in arms.items():
        print(arm, {k: a[k]["mean"] for k in keys if k in a})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
