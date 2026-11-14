#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from experiments.evaluate_coverage import evaluate, route_pattern


def _request_shape(event: dict) -> tuple[str, str, frozenset[str]]:
    query = {key for key, _ in parse_qsl(urlsplit(event.get("url", "")).query)}
    names = query | set(event.get("parameter_names", []))
    return event.get("method", "GET").upper(), route_pattern(event.get("url", "")), frozenset(names)


def evaluate_generalization(
    graph: dict, truth: dict, server_stats: dict[str, int] | None = None
) -> dict:
    base = evaluate(graph, truth)
    actions = graph["nodes"]["actions_evidence"]
    states = graph["nodes"]["states"]
    edges = graph["edges"]
    target_by_action = {
        edge["source"]: edge["target"] for edge in edges if edge["type"] == "results_in"
    }
    action_by_label = {item["label"]: item for item in actions}
    navigation_events = [
        event
        for navigation in graph.get("navigation_evidence", [])
        for event in navigation.get("network", [])
    ]
    action_events = [event for action in actions for event in action.get("network", [])]
    all_shapes = {_request_shape(event) for event in action_events + navigation_events}
    request_results = []
    for expected in truth["requests"]:
        matches = [
            shape
            for shape in all_shapes
            if shape[0] == expected["method"]
            and shape[1] == expected["path"]
            and set(expected["params"]).issubset(shape[2])
        ]
        request_results.append({**expected, "status": "covered" if matches else "missed"})
    applicable_requests = [item for item in request_results if item["scope"] == "applicable"]
    covered_requests = [item for item in applicable_requests if item["status"] == "covered"]

    def area_state(area_id: str) -> str | None:
        area = next(item for item in truth["areas"] if item["id"] == area_id)
        if area.get("via_label"):
            action = action_by_label.get(area["via_label"])
            return target_by_action.get(action["id"]) if action else None
        candidates = [
            item
            for item in states
            if item.get("route_pattern") == area["route"] and item.get("return_path_length") == 0
        ]
        return candidates[0]["id"] if candidates else None

    false_merges = []
    for left, right in truth.get("distinct_area_pairs", []):
        left_state, right_state = area_state(left), area_state(right)
        if left_state and right_state and left_state == right_state:
            false_merges.append([left, right])

    initial_root_states = [
        item
        for item in states
        if item.get("route_pattern") == "/"
        and item.get("return_path_length") == 0
        and item.get("title") == "JavaScript Readiness Lab"
        and not item.get("session_markers", {}).get("cookie_names")
    ]
    readiness_counts = Counter(
        status
        for item in states
        for status in item.get("readiness_statuses", ["not_recorded"])
    )
    replayed_paths = [
        action
        for action in actions
        if action.get("status") == "replay_validated" and action.get("workflow_path")
    ]
    alias_controls = [
        item
        for item in graph.get("advertised_unexecuted", [])
        if item.get("control", {}).get("label") == "Public alias area"
    ]
    alias_actions = [item for item in actions if item.get("label") == "Public alias area"]
    alias_status = "missed"
    if alias_actions:
        alias_status = "executed"
    elif alias_controls:
        alias_status = alias_controls[0].get("control", {}).get("skip_reason") or "advertised"

    serialized = json.dumps(graph, sort_keys=True)
    sensitive_hits = [value for value in truth.get("sensitive_values", []) if value in serialized]
    metrics = graph["metrics"]
    covered_areas = base["counts"]["covered_areas"]
    return {
        "application": truth["application"],
        "base": base,
        "generalization_metrics": {
            "applicable_area_recall": base["metrics"]["state_interface_recall"],
            "applicable_control_recall": base["metrics"]["control_action_recall"],
            "request_surface_recall_all_phases": (
                len(covered_requests) / len(applicable_requests) if applicable_requests else 0.0
            ),
            "unique_replayed_prerequisite_paths": len(
                {tuple(step.get("signature", "") for step in item["workflow_path"]) for item in replayed_paths}
            ),
            "deepest_verified_path": max(
                (len(item["workflow_path"]) for item in replayed_paths), default=0
            ),
            "startup_readiness_failures": metrics.get("startup_readiness_failures", 0),
            "readiness_statuses": dict(sorted(readiness_counts.items())),
            "alias_scope_status": alias_status,
            "root_reloads": metrics.get("root_reloads", metrics.get("navigation_requests", 0)),
            "restoration_actions": metrics.get(
                "restoration_actions",
                sum(max(0, len(item.get("workflow_path", [])) - 1) for item in actions),
            ),
            "actions_per_covered_area": (
                metrics["browser_actions"] / covered_areas if covered_areas else None
            ),
            "browser_actions": metrics["browser_actions"],
            "elapsed_seconds": metrics["elapsed_seconds"],
            "replay_reliability": base["metrics"]["replay_reliability"],
            "critical_false_merges": len(false_merges),
            "unnecessary_initial_state_splits": max(0, len(initial_root_states) - 1),
            "sensitive_value_leaks": len(sensitive_hits),
            "initial_navigation_events": len(navigation_events),
            "action_network_events": len(action_events),
        },
        "request_results_all_phases": request_results,
        "false_merge_pairs": false_merges,
        "server_request_counts": server_stats or {},
    }


def write_evaluation(
    graph_path: Path,
    truth_path: Path,
    output_path: Path,
    server_stats: dict[str, int] | None = None,
) -> dict:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    result = evaluate_generalization(graph, truth, server_stats)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
