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
from development_apps.heldout_shop import start_heldout_shop
from experiments.evaluate_coverage import evaluate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--policy", choices=("grouped", "coverage"), required=True)
    args = parser.parse_args()
    server, thread, url = start_heldout_shop()
    try:
        artifact = Explorer(
            RunConfig(
                start_url=url, output_dir=args.out, policy=args.policy,
                max_seconds=60, max_transitions=30, max_browser_actions=140,
                allow_post_forms=True, settle_ms=30, replay_reserve_fraction=0.35,
                context_label="heldout-shop",
            ),
            ROOT,
        ).run()
        write_outputs(artifact, args.out)
        graph = json.loads((args.out / "graph_a.json").read_text())
        truth = json.loads((ROOT / "development_apps/heldout_shop_ground_truth.json").read_text())
        result = evaluate(graph, truth)
        (args.out / "coverage_evaluation.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"counts": result["counts"], "metrics": result["metrics"]}, sort_keys=True))
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
