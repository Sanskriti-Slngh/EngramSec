#!/usr/bin/env python3
"""Score completed Crawl Maze graphs via its documented evaluator endpoint.

This script is an offline/post-run evaluator. Agent 1 never imports it and does
not receive the returned marker paths as exploration input.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from urllib.request import urlopen


def path_of(value: str) -> str:
    return unquote(urlsplit(value).path or "/")


def top_level_categories(graph: dict, base_url: str) -> list[str]:
    root_groups = {
        state["group_signature"]
        for state in graph["nodes"]["states"]
        if state.get("route_pattern") == "/"
    }
    candidates = []
    for action in graph["nodes"]["actions_evidence"]:
        if action.get("workflow_path_length") == 1:
            candidates.extend(step.get("target") or "" for step in action.get("workflow_path", []))
    for item in graph.get("advertised_unexecuted", []):
        if item.get("source_group_signature") in root_groups:
            candidates.append(item.get("control", {}).get("target") or "")
    return sorted({
        parts.path.strip("/").split("/", 1)[0]
        for url in candidates
        if (parts := urlsplit(url)).scheme in {"http", "https"}
        and parts.netloc == urlsplit(base_url).netloc
        and parts.path.strip("/")
        and not parts.path.lstrip("/").startswith("__eval__")
        and not parts.path.lstrip("/").startswith("test/")
    })


def expected_paths(base_url: str, categories: list[str]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for category in categories:
        endpoint = f"{base_url.rstrip('/')}/fetch-expected-results?path={quote(category)}"
        with urlopen(endpoint, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result[category] = {path_of(value) for value in payload}
    return result


def network_events(graph: dict) -> tuple[list[dict], list[dict]]:
    result: list[dict] = []
    result.extend(
        event
        for navigation in graph.get("navigation_evidence", [])
        for event in navigation.get("network", [])
    )
    replay_events = [
        event
        for replay in graph.get("replays", [])
        for event in replay.get("network", [])
    ]
    result.extend(
        event
        for action in graph["nodes"].get("actions_evidence", [])
        for event in action.get("network", [])
    )
    result.extend(
        event
        for action in graph["nodes"].get("actions_evidence", [])
        for step in action.get("prerequisite_network", [])
        for event in step.get("network", [])
    )
    return result, replay_events


def score(graph: dict, categories: dict[str, set[str]]) -> dict:
    browser_events, replay_events = network_events(graph)
    browser_paths = {path_of(item["url"]) for item in browser_events if item.get("url")}
    browser_ok = {
        path_of(item["url"])
        for item in browser_events
        if item.get("url") and item.get("status") is not None and 200 <= int(item["status"]) < 300
    }
    references = graph.get("resource_evidence", [])
    reference_paths = {path_of(item["url"]) for item in references if item.get("url")}
    spider_fetched = {
        path_of(item["url"])
        for item in references
        if item.get("url") and item.get("status") == "fetched"
        and item.get("http_status") is not None and 200 <= int(item["http_status"]) < 300
    }
    replay_paths = set()
    replay_successes = 0
    replay_failures = 0
    for replay in graph.get("replays", []):
        if replay.get("status") == "replay_validated":
            replay_successes += 1
            replay_paths.update(
                path_of(item["url"])
                for item in replay.get("network", [])
                if item.get("url")
            )
        elif replay.get("status") == "failed":
            replay_failures += 1
    by_category = {}
    ui_state_paths = {
        path_of(item["url"])
        for item in graph["nodes"].get("states", [])
        if item.get("url")
    }
    all_browser_events = browser_events + replay_events
    browser_ok |= {
        path_of(item["url"])
        for item in replay_events
        if item.get("url") and item.get("status") is not None and 200 <= int(item["status"]) < 300
    }
    totals = defaultdict(lambda: {
        "expected": 0, "referenced": 0, "browser_fetched": 0,
        "spider_fetched": 0, "replay_requested": 0,
        "ui_state_reached": 0, "any_fetch": 0,
    })
    for category, expected in categories.items():
        counts = {
            "expected": len(expected),
            "referenced": len(expected & reference_paths),
            "browser_fetched": len(expected & browser_ok),
            "spider_fetched": len(expected & spider_fetched),
            "replay_requested": len(expected & replay_paths),
            "ui_state_reached": len(expected & ui_state_paths),
            "any_fetch": len(expected & (browser_ok | spider_fetched)),
        }
        by_category[category] = counts
        for key, value in counts.items():
            totals["all"][key] += value
    metrics = graph["metrics"]
    total = totals["all"]
    denom = total["expected"]
    all_expected = set().union(*categories.values()) if categories else set()
    hit_count = len(all_expected & (browser_ok | spider_fetched))
    return {
        "coverage_by_category": by_category,
        "coverage_total": total,
        "recall": {
            key: (total[key] / denom if denom else None)
            for key in (
                "referenced", "browser_fetched", "spider_fetched",
                "replay_requested", "ui_state_reached", "any_fetch",
            )
        },
        "application_observations": {
            "states": len(graph["nodes"].get("states", [])),
            "distinct_routes": len({item.get("route_pattern") for item in graph["nodes"].get("states", [])}),
            "observed_transitions": sum(item.get("status") in {"observed", "replay_validated"} for item in graph["nodes"].get("actions_evidence", [])),
            "actions": len(graph["nodes"].get("actions_evidence", [])) + len(graph.get("advertised_unexecuted", [])),
            "browser_network_events": len(all_browser_events),
            "browser_http_requests_accounted": metrics.get("observed_http_requests", 0),
            "typed_resource_fetches": metrics.get("resource_fetches_attempted", 0),
            "typed_resource_fetch_successes": metrics.get("resource_fetches_succeeded", 0),
            "typed_resource_failures": metrics.get("resource_fetch_failures", 0),
            "replay_attempts": metrics.get("replay_attempts", 0),
            "replay_successes": replay_successes,
            "replay_failures": replay_failures,
            "untested_paths": metrics.get("replay_untested_paths", 0),
            "elapsed_seconds": metrics.get("elapsed_seconds", 0),
            "browser_actions": metrics.get("browser_actions", 0),
            "browser_actions_per_marker": (
                metrics.get("browser_actions", 0) / hit_count if hit_count else None
            ),
            "graph_connections_complete": metrics.get("graph_connections_complete", 0),
            "graph_connections_total": metrics.get("graph_connections_total", 0),
            "graph_connections_missing": metrics.get("graph_connections_missing_evidence", 0),
            "reported_false_merges": metrics.get("incorrect_state_merges", 0),
            "model_calls": metrics.get("model_calls", 0),
            "external_cost_usd": metrics.get("monetary_cost_usd", 0.0),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:3460/")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--extra-graph", type=Path, action="append", default=[])
    parser.add_argument("--server-log", type=Path)
    args = parser.parse_args()
    baseline = json.loads((args.root / "p0" / "graph_a.json").read_text(encoding="utf-8"))
    categories = top_level_categories(baseline, args.url)
    truth = expected_paths(args.url, categories)
    results = {}
    graph_paths = sorted(args.root.glob("*/graph_a.json")) + args.extra_graph
    for graph_path in graph_paths:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        label = "frozen_decc0a2" if str(graph_path).startswith("/private/tmp/agent1-frozen-decc0a2-run") else graph_path.parent.name
        results[label] = score(graph, truth)
    if args.server_log:
        logged_paths = {
            path_of(match.group(1))
            for match in re.finditer(r'"GET (/[^ ?]+) HTTP/', args.server_log.read_text(errors="replace"))
        }
        expected_all = set().union(*truth.values()) if truth else set()
        server_hits = expected_all & logged_paths
        results["combined_shallow_final"]["independent_server_marker_hits"] = {
            "hit_count": len(server_hits),
            "expected_count": len(expected_all),
            "recall": len(server_hits) / len(expected_all) if expected_all else None,
            "paths_by_category": {
                category: len(paths & server_hits)
                for category, paths in truth.items()
            },
            "status": "derived from local Crawl Maze request log after crawl; evaluator paths were not read by Agent 1",
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"scoring_interface": "documented post-run fetch-expected-results", "categories": categories, "results": results}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    compact = {
        name: {
            "markers": item["coverage_total"],
            "marker_recall": item["recall"],
            "states": item["application_observations"]["states"],
            "transitions": item["application_observations"]["observed_transitions"],
            "actions": item["application_observations"]["browser_actions"],
            "replay": f"{item['application_observations']['replay_successes']}/{item['application_observations']['replay_attempts']}",
        }
        for name, item in results.items()
    }
    print(json.dumps(compact, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
