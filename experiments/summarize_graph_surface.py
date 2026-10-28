#!/usr/bin/env python3
"""Summarize a frozen Agent 1 run without benchmark ground truth.

This evaluator reads only mapper artifacts.  It intentionally cannot calculate
vulnerability recall, application-area recall, or false state merges: each of
those needs an independent denominator that is not present in Graph A.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _unique_controls(observations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    controls: dict[str, dict[str, Any]] = {}
    for observation in observations:
        for control in observation.get("controls", []):
            controls.setdefault(control.get("signature") or control["id"], control)
    return controls


def _form_key(form: dict[str, Any]) -> tuple[Any, ...]:
    return (
        form.get("method"),
        tuple((field.get("name"), field.get("input_type")) for field in form.get("fields", [])),
    )


def _request_key(event: dict[str, Any]) -> tuple[Any, ...]:
    return (
        event.get("method"),
        event.get("route_pattern") or event.get("url"),
        tuple(event.get("parameter_names", [])),
        event.get("body_encoding"),
        event.get("resource_type"),
    )


def summarize(run: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    observations = run.get("observations", [])
    transitions = run.get("transitions", [])
    replays = run.get("replays", [])
    controls = _unique_controls(observations)
    forms = {_form_key(form) for obs in observations for form in obs.get("forms", [])}
    request_events = [event for transition in transitions for event in transition.get("network", [])]
    request_surfaces = {_request_key(event) for event in request_events}
    unique_ads = {
        (ad.get("source_group_signature"), ad.get("control", {}).get("signature"))
        for ad in run.get("advertisements", [])
    }
    successful_replays = [replay for replay in replays if replay.get("status") == "replay_validated"]
    verified_paths = [replay.get("path_length", 0) for replay in successful_replays]
    attempted_paths = [len(transition.get("workflow_path", [])) for transition in transitions]
    skip_reasons = Counter(
        control.get("skip_reason") or "executable"
        for control in controls.values()
        if not control.get("safe", False)
    )
    route_titles = {
        (observation.get("route_pattern"), observation.get("title"))
        for observation in observations
    }
    record_facts = {
        json.dumps(observation.get("instance_facts", {}), sort_keys=True)
        for observation in observations
        if observation.get("instance_facts")
    }
    metrics = graph.get("metrics", {})
    return {
        "assessment_kind": "mapper_artifact_only_no_benchmark_ground_truth",
        "code_revision": run.get("code_revision"),
        "run_id": run.get("run_id"),
        "configuration": run.get("config", {}),
        "observed_inventory": {
            "route_title_areas": len(route_titles),
            "grouped_states": metrics.get("grouped_states", 0),
            "raw_states": metrics.get("raw_states", 0),
            "observations": len(observations),
            "unique_controls": len(controls),
            "unique_safe_controls": sum(bool(control.get("safe")) for control in controls.values()),
            "unique_blocked_controls": sum(not bool(control.get("safe")) for control in controls.values()),
            "blocked_control_reasons": dict(sorted(skip_reasons.items())),
            "unique_form_structures": len(forms),
            "unique_request_surfaces": len(request_surfaces),
            "network_events": len(request_events),
            "observation_fact_sets": len(record_facts),
            "independently_identified_record_instances": 0,
            "session_contexts": sorted(
                {observation.get("session_context") for observation in observations if observation.get("session_context")}
            ),
        },
        "reachability_and_replay": {
            "transitions_attempted": metrics.get("transitions_attempted", 0),
            "transitions_observed": metrics.get("transitions_observed", 0),
            "transitions_failed": metrics.get("transitions_failed", 0),
            "unique_advertised_control_groups": len(unique_ads),
            "advertisement_records": len(run.get("advertisements", [])),
            "replay_attempts": metrics.get("replay_attempts", 0),
            "replay_navigation_successes": metrics.get("replay_navigation_successes", 0),
            "replay_failures": metrics.get("replay_failures", 0),
            "replay_untested_paths": metrics.get("replay_untested_paths", 0),
            "deepest_attempted_path": max(attempted_paths, default=0),
            "deepest_replay_validated_path": max(verified_paths, default=0),
            "functional_workflows_verified": metrics.get("functional_workflows_verified", 0),
            "functional_unresolved": metrics.get("functional_unresolved", 0),
        },
        "effort": {
            "elapsed_seconds": metrics.get("elapsed_seconds", 0),
            "browser_actions": metrics.get("browser_actions", 0),
            "model_calls": metrics.get("model_calls", 0),
            "monetary_cost_usd": metrics.get("monetary_cost_usd", 0),
        },
        "evidence": {
            "graph_connections_total": metrics.get("graph_connections_total", 0),
            "graph_connections_missing_evidence": metrics.get("graph_connections_missing_evidence", 0),
        },
        "not_measurable_without_independent_ground_truth": [
            "application_area_recall",
            "control_recall",
            "request_surface_recall",
            "vulnerability_relevant_surface_coverage",
            "false_state_merges",
            "missed_paths",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run = json.loads((args.run_dir / "run.json").read_text())
    graph = json.loads((args.run_dir / "graph_a.json").read_text())
    summary = summarize(run, graph)
    output = args.output or args.run_dir / "surface_assessment.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
