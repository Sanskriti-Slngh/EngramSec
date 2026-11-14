#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent1.exporter import write_outputs
from agent1.explorer import Explorer
from agent1.schema import RunConfig
from tests.fixtures.ground_truth import CASES, event_values
from tests.fixtures.interactive_app import start_server


def evaluate(case: str, artifact: object, events: list[dict]) -> dict:
    observations = artifact.observations
    replays = artifact.replays
    replay_successes = sum(str(item.status) == "replay_validated" for item in replays)
    functional_available = str(getattr(artifact, "schema_version", "1.0")) != "1.0"
    functional_verified = (
        sum(str(item.status) == "functional_verified" for item in artifact.functional_workflows)
        if functional_available
        else 0
    )
    result: dict[str, object] = {
        "case": case,
        "groups": len({item.group_signature for item in observations}),
        "raw_states": len({item.state_signature for item in observations}),
        "replays_succeeded": replay_successes,
        "replays_failed": len(replays) - replay_successes,
        "replays_attempted": len(replays),
        "functional_verification_available": functional_available,
        "functional_verified": functional_verified,
        "functional_validation_failures": (
            sum(str(item.status) == "validation_failure" for item in artifact.functional_workflows)
            if functional_available
            else 0
        ),
        "connections_missing_evidence": (
            artifact.metrics.graph_connections_missing_evidence if functional_available else None
        ),
        "functional_false_positives": 0,
        "functional_false_negatives": 0,
        "navigation_validation_false_positives": 0,
        "incorrect_merges": 0,
        "unnecessary_splits": 0,
    }
    if case == "search":
        values = event_values(events, "search_result", "result")
        result.update(
            emitted_results=values,
            distinct_results_emitted=len(set(values)),
            result_texts_share_group=any(
                left.text_excerpt != right.text_excerpt and left.group_signature == right.group_signature
                for index, left in enumerate(observations)
                for right in observations[index + 1 :]
                if left.route_pattern == right.route_pattern == "/search"
            ),
        )
        if len(set(values)) > 1 and replay_successes:
            result["navigation_validation_false_positives"] = 1
        if result["result_texts_share_group"]:
            result["incorrect_merges"] = 1
    elif case == "form":
        outcomes = event_values(events, "form_submission", "success")
        result.update(
            submissions=outcomes,
            validation_failure_observed=any(value is False for value in outcomes),
            success_observed=any(value is True for value in outcomes),
            failure_counted_as_replay_success=any(value is False for value in outcomes)
            and any(str(item.status) == "replay_validated" for item in replays),
        )
        stable_success = bool(outcomes) and all(value is True for value in outcomes)
        if functional_available:
            result["functional_false_positives"] = int(functional_verified > 0 and not stable_success)
            result["functional_false_negatives"] = int(stable_success and functional_verified == 0)
        else:
            result["functional_false_positives"] = int(
                any(value is False for value in outcomes) and replay_successes > 0
            )
    elif case == "multi":
        kinds = [item["kind"] for item in events if item.get("kind") in {"setup", "completion"}]
        completions = [item for item in events if item.get("kind") == "completion"]
        result.update(
            event_sequence=kinds,
            successful_completion=any(item.get("success") for item in completions),
            successful_completion_with_prerequisite=any(
                item.get("success") and item.get("prerequisite") for item in completions
            ),
        )
        stable_success = bool(completions) and all(item.get("success") for item in completions)
        result["functional_false_negatives"] = int(stable_success and functional_verified == 0)
        result["functional_false_positives"] = int(functional_verified > 0 and not stable_success)
    elif case == "records":
        visits = event_values(events, "record_visit", "record")
        result.update(
            record_visits=visits,
            wrong_instance_replay_possible=len(visits) >= 2 and visits[-1] != visits[-2],
            wrong_instance_accepted=(len(visits) >= 2 and visits[-1] != visits[-2])
            and any(str(item.status) == "replay_validated" for item in replays),
        )
        if result["wrong_instance_accepted"]:
            result["navigation_validation_false_positives"] = 1
            result["incorrect_merges"] = 1
    elif case == "cosmetic":
        cosmetic = [item for item in observations if item.route_pattern == "/cosmetic"]
        result.update(
            observations=len(cosmetic),
            unnecessary_splits=max(0, len({item.group_signature for item in cosmetic}) - 1),
        )
    elif case == "outcomes":
        result.update(
            statuses=sorted(
                str(item.status) for item in getattr(artifact, "functional_workflows", [])
            ),
            advertised_unexecuted=artifact.metrics.advertised_unexecuted,
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=12.0)
    parser.add_argument("--max-transitions", type=int, default=8)
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit(f"output directory is not empty: {args.out}")
    args.out.mkdir(parents=True, exist_ok=True)
    server, thread = start_server()
    started = time.monotonic()
    results = []
    try:
        for case, truth in CASES.items():
            server.state.reset()
            output = args.out / case
            config = RunConfig(
                start_url=server.base_url + truth["path"],
                output_dir=output,
                policy="grouped",
                max_seconds=args.seconds,
                max_transitions=(
                    1
                    if case in {"search", "form", "records", "cosmetic"}
                    else 2
                    if case == "outcomes"
                    else args.max_transitions
                ),
                max_browser_actions=120,
                allow_post_forms=True,
                replay_reserve_fraction=0.45,
                context_label=f"fixture:{case}",
            )
            artifact = Explorer(config, ROOT).run()
            write_outputs(artifact, output)
            events = server.state.snapshot()
            (output / "fixture_events.json").write_text(
                json.dumps(events, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            results.append(evaluate(case, artifact, events))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    summary = {
        "schema_version": "validation-fixtures-1.0",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "cases": results,
        "totals": {
            key: sum(int(item.get(key, 0) or 0) for item in results)
            for key in (
                "functional_false_positives",
                "functional_false_negatives",
                "navigation_validation_false_positives",
                "incorrect_merges",
                "unnecessary_splits",
            )
        },
    }
    (args.out / "evaluation.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
