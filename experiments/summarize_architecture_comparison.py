#!/usr/bin/env python3
"""Summarize the Agent 1 architecture ablation (arms A-E) on Crawl Maze.

Post-run only: expected marker paths come from the testbed's documented
evaluator endpoint after every crawl has stopped. Agent 1 never imports this.
Marker hits use the same definition as score_crawlmaze_posthoc.py (`any_fetch`:
a 2xx browser response or a 2xx typed-spider GET recorded in Graph A).
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from score_crawlmaze_posthoc import expected_paths, network_events, path_of, top_level_categories


def _ok(status: object) -> bool:
    return status is not None and 200 <= int(status) < 300


def run_sets(graph: dict) -> dict[str, set]:
    browser, replay = network_events(graph)
    browser_ok = {path_of(e["url"]) for e in browser + replay if e.get("url") and _ok(e.get("status"))}
    refs = graph.get("resource_evidence", [])
    spider_ok = {path_of(r["url"]) for r in refs if r.get("url") and r.get("status") == "fetched" and _ok(r.get("http_status"))}
    zap_fetched = {path_of(r["url"]) for r in refs if r.get("url") and r.get("source_type") == "zap_seed"
                   and r.get("status") == "fetched" and _ok(r.get("http_status"))}
    agent_referenced = {path_of(r["url"]) for r in refs if r.get("url") and r.get("source_type") != "zap_seed"}
    structures = {
        (e.get("method", "GET"), path_of(e["url"]), tuple(sorted(e.get("parameter_names") or
                                                                {k for k, _ in parse_qsl(urlsplit(e["url"]).query)})))
        for e in browser + replay if e.get("url")
    } | {("GET", path_of(r["url"]), tuple(sorted({k for k, _ in parse_qsl(urlsplit(r["url"]).query)})))
         for r in refs if r.get("url") and r.get("status") == "fetched"}
    areas = {(urlsplit(s["url"]).path.strip("/").split("/", 1)[0] or "/") for s in graph["nodes"]["states"] if s.get("url")}
    return {"hits": browser_ok | spider_ok, "browser_ok": browser_ok, "zap_fetched": zap_fetched,
            "agent_referenced": agent_referenced, "structures": structures, "areas": areas}


def integrity(graph: dict) -> dict[str, int]:
    transitions = {path_of(step.get("target") or "") for a in graph["nodes"]["actions_evidence"]
                   for step in a.get("workflow_path", [])}
    external = graph["nodes"].get("external_discoveries", [])
    return {
        "external_promoted_to_replay": sum(item.get("status") == "replay_validated" for item in external),
        "external_records_without_provenance": sum(
            not all(item.get(k) for k in ("run_id", "source_origin", "source_record_id", "export_digest")) for item in external),
        "external_paths_also_ui_targets": len({path_of(item["mapped_url"]) for item in external} & transitions),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:3460/")
    parser.add_argument("--category-graph", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    categories = top_level_categories(json.loads(args.category_graph.read_text()), args.url)
    truth = expected_paths(args.url, categories)
    expected = set().union(*truth.values())
    runs: dict[str, dict] = {}
    sets: dict[str, dict] = {}
    for graph_path in sorted(args.root.glob("*/graph_a.json")):
        name = graph_path.parent.name.removeprefix("adaptive_readiness_")
        graph = json.loads(graph_path.read_text())
        metrics = json.loads((graph_path.parent / "metrics.json").read_text())
        s = run_sets(graph)
        sets[name] = s
        hits = s["hits"] & expected
        external_only = (s["zap_fetched"] & expected) - s["browser_ok"] - s["agent_referenced"]
        minutes = (metrics["elapsed_seconds"] + metrics.get("external_elapsed_seconds", 0.0)) / 60
        http = metrics.get("total_http_budget_used") or 0
        runs[name] = {
            "arm": name.split("_")[0],
            "marker_hits": len(hits),
            "marker_hits_by_category": {c: len(v & hits) for c, v in truth.items()},
            "graph_a_functional_areas": len(s["areas"]),
            "grouped_states": metrics.get("grouped_states"),
            "distinct_request_structures": len(s["structures"]),
            "external_only_marker_hits": len(external_only),
            "replay_validated": metrics.get("replay_success_numerator"),
            "replay_attempted": metrics.get("replay_success_denominator"),
            "untested_transitions": metrics.get("replay_untested_paths"),
            "transitions_observed": metrics.get("transitions_observed"),
            "browser_actions": metrics.get("browser_actions"),
            "discovery_root_reloads": metrics.get("discovery_root_reloads"),
            "verification_root_reloads": metrics.get("verification_root_reloads"),
            "restoration_actions": metrics.get("restoration_actions"),
            "live_state_reuses": metrics.get("live_state_reuses"),
            "prefix_state_reuses": metrics.get("prefix_state_reuses", 0),
            "total_http_requests": http,
            "http_by_source": metrics.get("http_budget_by_source"),
            "http_blocked": metrics.get("total_http_budget_blocked"),
            "http_overrun": metrics.get("http_redirect_budget_overrun"),
            "elapsed_seconds": metrics["elapsed_seconds"],
            "external_elapsed_seconds": metrics.get("external_elapsed_seconds", 0.0),
            "marker_hits_per_minute": round(len(hits) / minutes, 2) if minutes else None,
            "marker_hits_per_100_requests": round(100 * len(hits) / http, 2) if http else None,
            "incorrect_state_merges": metrics.get("incorrect_state_merges"),
            "graph_connections_missing_evidence": metrics.get("graph_connections_missing_evidence"),
            "graph_connections_total": metrics.get("graph_connections_total"),
            **integrity(graph),
        }
    # Paths a non-baseline arm hit that no baseline (A) run hit.
    baseline_hits = set().union(*(sets[n]["hits"] & expected for n in sets if n.startswith("A_"))) if any(
        n.startswith("A_") for n in sets) else set()
    for name, row in runs.items():
        row["marker_hits_absent_from_all_A_runs"] = len((sets[name]["hits"] & expected) - baseline_hits)
    by_arm: dict[str, list[dict]] = defaultdict(list)
    for row in runs.values():
        by_arm[row["arm"]].append(row)
    aggregate = {}
    for arm, rows in sorted(by_arm.items()):
        agg = {"runs": len(rows)}
        for key in ("marker_hits", "graph_a_functional_areas", "distinct_request_structures", "external_only_marker_hits",
                    "replay_validated", "untested_transitions", "discovery_root_reloads", "restoration_actions",
                    "total_http_requests", "marker_hits_per_minute", "marker_hits_per_100_requests",
                    "marker_hits_absent_from_all_A_runs", "transitions_observed"):
            values = [r[key] for r in rows if r.get(key) is not None]
            if values:
                agg[key] = {"mean": round(statistics.mean(values), 2), "min": min(values), "max": max(values)}
        aggregate[arm] = agg
    payload = {"expected_total": len(expected), "categories": categories, "runs": runs, "aggregate": aggregate,
               "note": "Marker hits are live integrated results from each run's own Graph A; no offline unions."}
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    for name, row in sorted(runs.items()):
        print(f"{name:8} hits={row['marker_hits']:3} areas={row['graph_a_functional_areas']:2} "
              f"struct={row['distinct_request_structures']:4} ext_only={row['external_only_marker_hits']:2} "
              f"newVsA={row['marker_hits_absent_from_all_A_runs']:2} replay={row['replay_validated']}/{row['replay_attempted']} "
              f"untested={row['untested_transitions']} rootDisc={row['discovery_root_reloads']} restore={row['restoration_actions']} "
              f"http={row['total_http_requests']} missing={row['graph_connections_missing_evidence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
