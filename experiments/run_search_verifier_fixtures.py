#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent1.explorer import Explorer
from agent1.exporter import write_outputs
from agent1.schema import FunctionalStatus, RunConfig
from tests.fixtures.search_adversarial_app import start_adversarial_search_server
from tests.fixtures.search_adversarial_ground_truth import SEARCH_CASES


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate paired search against independent fixtures")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    server, thread, base_url = start_adversarial_search_server()
    results = []
    try:
        for name, truth in SEARCH_CASES.items():
            output = args.out / name
            artifact = Explorer(
                RunConfig(
                    start_url=base_url + truth["path"],
                    output_dir=output,
                    policy="grouped",
                    max_seconds=12,
                    max_transitions=1,
                    max_browser_actions=60,
                    settle_ms=20,
                    replay_reserve_fraction=0.55,
                    search_probe_primary="alpha",
                    search_probe_contrast="beta",
                    context_label=f"fixture:{name}",
                ),
                ROOT,
            ).run()
            write_outputs(artifact, output)
            search_workflows = [
                workflow
                for workflow in artifact.functional_workflows
                if any(
                    replay.transition_id == workflow.transition_id
                    and replay.verification_kind == "paired_search"
                    for replay in artifact.replays
                )
            ]
            status = (
                search_workflows[0].status
                if len(search_workflows) == 1
                else FunctionalStatus.UNRESOLVED
            )
            verified = status == FunctionalStatus.VERIFIED
            results.append(
                {
                    "case": name,
                    "expected_functional": truth["functional"],
                    "expected_reason": truth["reason"],
                    "actual_status": status,
                    "false_positive": verified and not truth["functional"],
                    "false_negative": bool(truth["functional"]) and not verified,
                    "replay_attempts": artifact.metrics.replay_attempts,
                    "replay_navigation_successes": artifact.metrics.replay_navigation_successes,
                    "browser_actions": artifact.metrics.browser_actions,
                    "elapsed_seconds": artifact.metrics.elapsed_seconds,
                    "cost_usd": artifact.metrics.monetary_cost_usd,
                }
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    summary = {
        "cases": results,
        "false_positives": sum(item["false_positive"] for item in results),
        "false_negatives": sum(item["false_negative"] for item in results),
        "browser_actions": sum(item["browser_actions"] for item in results),
        "elapsed_seconds": round(sum(item["elapsed_seconds"] for item in results), 3),
        "external_cost_usd": sum(item["cost_usd"] for item in results),
    }
    (args.out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
