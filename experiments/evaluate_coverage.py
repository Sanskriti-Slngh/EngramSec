#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit


INSTANCE = re.compile(r"(?<![A-Za-z])\d+(?![A-Za-z])")


def route_pattern(url: str) -> str:
    return INSTANCE.sub("{instance}", urlsplit(url).path or "/")


def evaluate(graph: dict, truth: dict) -> dict:
    states = graph["nodes"]["states"]
    actions = graph["nodes"]["actions_evidence"]
    advertised = graph.get("advertised_unexecuted", [])
    state_by_id = {item["id"]: item for item in states}
    action_targets = {}
    for edge in graph["edges"]:
        if edge["type"] == "results_in":
            action_targets[edge["source"]] = edge["target"]

    controls = []
    for action in actions:
        controls.append(
            {
                "label": action["label"],
                "kind": action["kind"],
                "safe": True,
                "skip_reason": None,
                "status": action["status"],
                "action_id": action["id"],
                "workflow_path": action.get("workflow_path", []),
            }
        )
    for item in advertised:
        control = item["control"]
        controls.append(
            {
                "label": control["label"],
                "kind": control["kind"],
                "safe": control.get("safe", True),
                "skip_reason": control.get("skip_reason"),
                "status": "not_tested",
                "action_id": item["id"],
                "workflow_path": [],
            }
        )

    def action_for_label(label: str):
        return next((item for item in actions if item["label"] == label), None)

    def area_status(area: dict) -> str:
        scope = area["scope"]
        if scope == "outside":
            return "outside_access_scope"
        if scope == "blocked":
            return "discovered_blocked" if any(
                item["label"] == "Admin login" and item["skip_reason"] for item in controls
            ) else "missed"
        candidates = [item for item in states if item["route_pattern"] == area["route"]]
        if area.get("via_target_suffix"):
            candidates = []
            for action in actions:
                if not any(
                    (descriptor.get("target") or "").endswith(area["via_target_suffix"])
                    for descriptor in action.get("workflow_path", [])
                ):
                    continue
                target = state_by_id.get(action_targets.get(action["id"], ""))
                if target and target["route_pattern"] == area["route"]:
                    candidates.append(target)
        if area.get("via_label"):
            action = action_for_label(area["via_label"])
            target = state_by_id.get(action_targets.get(action["id"], "")) if action else None
            candidates = [target] if target and target["route_pattern"] == area["route"] else []
        if not candidates:
            return "missed"
        if area["id"] == "home":
            return "covered_replayed"
        for action in actions:
            target = state_by_id.get(action_targets.get(action["id"], ""))
            if target in candidates and action["status"] == "replay_validated":
                return "covered_replayed"
        return "covered_structural_not_replayed"

    area_results = [{**item, "status": area_status(item)} for item in truth["areas"]]
    control_results = []
    for expected in truth["controls"]:
        matches = [
            item
            for item in controls
            if item["label"] == expected["label"] and item["kind"] == expected["kind"]
        ]
        if expected["scope"] == "outside":
            status = "outside_access_scope"
        elif expected["scope"] == "blocked":
            status = "discovered_blocked" if any(not item["safe"] for item in matches) else "missed"
        elif any(item["status"] == "replay_validated" for item in matches):
            status = "covered_replayed"
        elif matches:
            status = "covered_structural_not_replayed"
        else:
            status = "missed"
        control_results.append({**expected, "status": status})

    observed_requests = []
    for action in actions:
        for event in action.get("network", []):
            query_keys = sorted(key for key, _ in parse_qsl(urlsplit(event["url"]).query))
            names = sorted(set(query_keys) | set(event.get("parameter_names", [])))
            observed_requests.append(
                {
                    "method": event["method"].upper(),
                    "path": route_pattern(event["url"]),
                    "params": names,
                    "resource_type": event.get("resource_type"),
                    "action_id": action["id"],
                }
            )
    request_results = []
    for expected in truth["requests"]:
        matches = [
            item
            for item in observed_requests
            if item["method"] == expected["method"]
            and item["path"] == expected["path"]
            and set(expected["params"]).issubset(item["params"])
        ]
        request_results.append(
            {**expected, "status": "covered_replayed" if matches else "missed"}
        )

    instance_results = []
    instance_groups = {}
    for expected in truth["instances"]:
        groups = set()
        for action in actions:
            path = action.get("workflow_path", [])
            if path and (path[-1].get("target") or "").endswith(expected["target_suffix"]):
                target_id = action_targets.get(action["id"])
                if target_id:
                    groups.add(target_id)
        instance_groups[expected["id"]] = groups
        instance_results.append(
            {**expected, "status": "covered_replayed" if groups else "missed"}
        )
    known_instance_groups = [groups for groups in instance_groups.values() if groups]
    instances_distinct = bool(known_instance_groups) and len(
        set().union(*known_instance_groups)
    ) == len(known_instance_groups)

    context_results = []
    for expected in truth["contexts"]:
        if expected["cookie_name"] is None:
            found = bool(states)
        else:
            found = any(
                expected["cookie_name"] in state.get("session_markers", {}).get("cookie_names", [])
                for state in states
            )
        context_results.append(
            {**expected, "status": "covered_structural_not_replayed" if found else "missed"}
        )

    def recall(items: list[dict], denominator_scope: str = "applicable") -> tuple[int, int, float]:
        applicable = [item for item in items if item["scope"] == denominator_scope]
        covered = [item for item in applicable if item["status"].startswith("covered")]
        return len(covered), len(applicable), len(covered) / len(applicable) if applicable else 0.0

    area_score = recall(area_results)
    control_score = recall(control_results)
    request_score = recall(request_results)
    path_applicable = [item for item in area_results if item["scope"] == "applicable"]
    path_covered = [item for item in path_applicable if item["status"] == "covered_replayed"]
    replay_attempts = graph["metrics"]["replay_attempts"]
    replay_successes = graph["metrics"]["replay_navigation_successes"]
    total_covered = area_score[0] + control_score[0] + request_score[0]
    actions_count = graph["metrics"]["browser_actions"]
    elapsed = graph["metrics"]["elapsed_seconds"]
    known_request_matches = sum(
        any(
            observed["method"] == expected["method"]
            and observed["path"] == expected["path"]
            for expected in truth["requests"]
        )
        for observed in observed_requests
    )
    return {
        "application": truth["application"],
        "denominators": {
            "areas": area_score[1],
            "controls": control_score[1],
            "requests": request_score[1],
            "paths": len(path_applicable),
            "instances": len(truth["instances"]),
            "contexts": len(truth["contexts"]),
            "blocked_areas_excluded": sum(item["scope"] == "blocked" for item in truth["areas"]),
            "outside_areas_excluded": sum(item["scope"] == "outside" for item in truth["areas"]),
        },
        "metrics": {
            "state_interface_recall": area_score[2],
            "control_action_recall": control_score[2],
            "request_surface_recall": request_score[2],
            "prerequisite_path_coverage": len(path_covered) / len(path_applicable),
            "instance_recall": (
                sum(item["status"].startswith("covered") for item in instance_results)
                / len(instance_results)
                if instance_results
                else None
            ),
            "instances_distinct": instances_distinct,
            "context_recall": sum(item["status"].startswith("covered") for item in context_results)
            / len(context_results),
            "replay_reliability": replay_successes / replay_attempts if replay_attempts else 0.0,
            "request_precision": known_request_matches / len(observed_requests)
            if observed_requests
            else None,
            "covered_surfaces_per_browser_action": total_covered / actions_count
            if actions_count
            else 0.0,
            "covered_surfaces_per_minute": total_covered / (elapsed / 60) if elapsed else 0.0,
        },
        "counts": {
            "covered_areas": area_score[0],
            "covered_controls": control_score[0],
            "covered_requests": request_score[0],
            "replay_attempts": replay_attempts,
            "replay_successes": replay_successes,
            "browser_actions": actions_count,
            "elapsed_seconds": elapsed,
            "grouped_states": graph["metrics"]["grouped_states"],
            "raw_states": graph["metrics"]["raw_states"],
            "incorrect_state_merges_self_audit": graph["metrics"]["incorrect_state_merges"],
            "graph_connections_missing_evidence": graph["metrics"]["graph_connections_missing_evidence"],
        },
        "areas": area_results,
        "controls": control_results,
        "requests": request_results,
        "instances": instance_results,
        "contexts": context_results,
        "observed_request_structures": observed_requests,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("graph", type=Path)
    parser.add_argument("ground_truth", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    truth = json.loads(args.ground_truth.read_text(encoding="utf-8"))
    result = evaluate(graph, truth)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"application": result["application"], **result["metrics"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
