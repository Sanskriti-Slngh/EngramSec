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
from agent1.schema import RunConfig
from development_apps.coverage_lab import start_coverage_lab
from experiments.evaluate_coverage import evaluate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--policy", default="grouped")
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--max-transitions", type=int, default=30)
    parser.add_argument("--max-browser-actions", type=int, default=140)
    args = parser.parse_args()
    server, thread, start_url = start_coverage_lab()
    try:
        config = RunConfig(
            start_url=start_url,
            output_dir=args.out,
            policy=args.policy,
            max_seconds=args.seconds,
            max_transitions=args.max_transitions,
            max_browser_actions=args.max_browser_actions,
            allow_post_forms=True,
            settle_ms=30,
            replay_reserve_fraction=0.35,
            context_label="coverage-lab",
        )
        artifact = Explorer(config, ROOT).run()
        write_outputs(artifact, args.out)
        truth = json.loads(
            (ROOT / "development_apps/coverage_lab_ground_truth.json").read_text()
        )
        graph = json.loads((args.out / "graph_a.json").read_text())
        evaluation = evaluate(graph, truth)
        (args.out / "coverage_evaluation.json").write_text(
            json.dumps(evaluation, indent=2, sort_keys=True) + "\n"
        )
        print(json.dumps({"counts": evaluation["counts"], "metrics": evaluation["metrics"]}, sort_keys=True))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
