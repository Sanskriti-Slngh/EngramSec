#!/usr/bin/env python3
"""Post-run scorer for development fixtures; never imported by Agent 1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.evaluate_coverage import evaluate
from experiments.evaluate_generalization import evaluate_generalization


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--mode", choices=("coverage", "generalization"), required=True)
    args = parser.parse_args()
    truth = json.loads(args.ground_truth.read_text(encoding="utf-8"))
    results = {}
    for graph_path in sorted(args.root.glob("*/graph_a.json")):
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        if args.mode == "coverage":
            result = evaluate(graph, truth)
            results[graph_path.parent.name] = {
                "application": result["application"],
                "denominators": result["denominators"],
                "metrics": result["metrics"],
                "counts": result["counts"],
            }
        else:
            result = evaluate_generalization(
                graph,
                truth,
                graph_path.parent.joinpath("metrics.json").exists()
                and json.loads(graph_path.parent.joinpath("metrics.json").read_text()).get("server_request_counts"),
            )
            results[graph_path.parent.name] = {
                "application": result["application"],
                "base_metrics": result["base"]["metrics"],
                "base_counts": result["base"]["counts"],
                "generalization_metrics": result["generalization_metrics"],
            }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"mode": args.mode, "results": results}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(results, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
