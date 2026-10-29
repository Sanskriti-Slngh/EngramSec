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
from development_apps.js_heavy_lab import STATE, start_js_heavy_lab
from experiments.evaluate_generalization import write_evaluation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--variant", choices=("p0", "p1", "p2"), required=True)
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--max-transitions", type=int, default=30)
    parser.add_argument("--max-browser-actions", type=int, default=140)
    args = parser.parse_args()
    server, thread, start_url = start_js_heavy_lab()
    try:
        config_data = {
            "start_url": start_url,
            "output_dir": args.out,
            "policy": "coverage",
            "max_seconds": args.seconds,
            "max_transitions": args.max_transitions,
            "max_browser_actions": args.max_browser_actions,
            "allow_post_forms": True,
            "settle_ms": 30,
            "replay_reserve_fraction": 0.35,
            "context_label": "js-heavy-lab",
        }
        if args.variant in {"p1", "p2"}:
            config_data.update(
                {
                    "robust_readiness": True,
                    "readiness_timeout_ms": 2_000,
                    "origin_aliases": [f"http://localhost:{server.server_port}"],
                }
            )
        if args.variant == "p2":
            config_data["exploration_mode"] = "persistent"
        config = RunConfig.model_validate(config_data)
        artifact = Explorer(config, ROOT).run()
        write_outputs(artifact, args.out)
        result = write_evaluation(
            args.out / "graph_a.json",
            ROOT / "evaluation_ground_truth" / "js_heavy_lab.json",
            args.out / "generalization_evaluation.json",
            STATE.snapshot(),
        )
        print(json.dumps(result["generalization_metrics"], sort_keys=True))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
