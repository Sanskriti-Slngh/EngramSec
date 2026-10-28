#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent1.exporter import write_outputs
from agent1.explorer import Explorer
from agent1.providers import load_repository_environment
from agent1.revision import code_revision
from agent1.schema import RunConfig, utc_now


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run matched Agent 1 experiments sequentially")
    parser.add_argument("--url", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=600.0)
    parser.add_argument("--max-transitions", type=int, default=200)
    parser.add_argument("--max-browser-actions", type=int, default=800)
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=("exact", "grouped", "selective_model", "model_all"),
        default=("exact", "grouped", "selective_model"),
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--model-provider", choices=("ollama", "groq"), default="ollama")
    parser.add_argument("--model", default="qwen2.5:0.5b")
    parser.add_argument("--allow-post-forms", action="store_true")
    return parser.parse_args()


def revision() -> str:
    return code_revision(ROOT)


def main() -> int:
    args = parse_args()
    load_repository_environment(ROOT)
    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit(f"experiment output already exists and is not empty: {args.out}")
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "experiment-suite-1.0",
        "started_at": utc_now(),
        "target": args.url,
        "code_revision": revision(),
        "python": platform.python_version(),
        "playwright": importlib.metadata.version("playwright"),
        "budget": {
            "seconds_per_run": args.seconds,
            "max_transitions": args.max_transitions,
            "max_browser_actions": args.max_browser_actions,
        },
        "starting_conditions": {
            "browser_context": "fresh per attempted transition and replay",
            "account_context": "anonymous",
            "application_reset": "not performed; live target has no mapper-visible reset contract",
            "worker_count": 1,
            "paid_calls": False,
        },
        "one_time_setup": {
            "playwright_browser_install_included_in_run_time": False,
            "dependency_install_included_in_run_time": False,
        },
        "runs": [],
    }
    rows: list[dict[str, object]] = []
    for repeat in range(1, args.repeats + 1):
        for variant in args.variants:
            name = f"{variant}-r{repeat}"
            output = args.out / name
            provider = args.model_provider if variant in {"selective_model", "model_all"} else "none"
            config = RunConfig(
                start_url=args.url,
                output_dir=output,
                policy=variant,
                max_seconds=args.seconds,
                max_transitions=args.max_transitions,
                max_browser_actions=args.max_browser_actions,
                allow_post_forms=args.allow_post_forms,
                model_provider=provider,
                model_name=args.model if provider != "none" else None,
                paid_calls_enabled=False,
            )
            wall_started = time.monotonic()
            artifact = Explorer(config, ROOT).run()
            write_outputs(artifact, output)
            wall_elapsed = round(time.monotonic() - wall_started, 3)
            metrics = artifact.metrics.model_dump(mode="json")
            run_record = {
                "name": name,
                "variant": variant,
                "repeat": repeat,
                "run_id": artifact.run_id,
                "wall_elapsed_seconds": wall_elapsed,
                "output": str(output.relative_to(args.out)),
                "metrics": metrics,
            }
            manifest["runs"].append(run_record)
            rows.append(
                {
                    "name": name,
                    "validated_workflows": metrics["distinct_validated_feature_workflows"],
                    "replay_success": f"{metrics['replay_success_numerator']}/{metrics['replay_success_denominator']}",
                    "unsupported_connections": metrics["unsupported_connections"],
                    "incorrect_state_merges": metrics["incorrect_state_merges"],
                    "redundant_states": metrics["redundant_states"],
                    "raw_states": metrics["raw_states"],
                    "grouped_states": metrics["grouped_states"],
                    "browser_actions": metrics["browser_actions"],
                    "network_events_recorded": metrics["network_events_recorded"],
                    "elapsed_seconds": metrics["elapsed_seconds"],
                    "wall_elapsed_seconds": wall_elapsed,
                    "model_calls": metrics["model_calls"],
                    "model_failures": metrics["model_failures"],
                    "input_tokens": metrics["model_input_tokens"],
                    "output_tokens": metrics["model_output_tokens"],
                    "cost_usd": metrics["monetary_cost_usd"],
                }
            )
            (args.out / "manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
    manifest["ended_at"] = utc_now()
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (args.out / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]) if rows else ["name"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"runs": len(rows), "output": str(args.out.resolve())}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
