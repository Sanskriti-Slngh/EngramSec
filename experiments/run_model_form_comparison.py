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
from tests.fixtures.interactive_app import start_server


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="llama3.2:latest")
    parser.add_argument("--seconds", type=float, default=30.0)
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit(f"output directory is not empty: {args.out}")
    args.out.mkdir(parents=True, exist_ok=True)

    server, thread = start_server()
    rows = []
    started = time.monotonic()
    try:
        for name, provider, model_forms in (
            ("deterministic", "none", False),
            ("ollama_form_assistance", "ollama", True),
        ):
            server.state.reset()
            output = args.out / name
            artifact = Explorer(
                RunConfig(
                    start_url=server.base_url + "/model-form",
                    output_dir=output,
                    policy="grouped",
                    max_seconds=args.seconds,
                    max_transitions=1,
                    max_browser_actions=80,
                    allow_post_forms=True,
                    replay_reserve_fraction=0.45,
                    context_label="fixture:model-form",
                    model_provider=provider,
                    model_name=args.model if model_forms else None,
                    model_form_assistance=model_forms,
                    max_form_retries=1,
                ),
                ROOT,
            ).run()
            write_outputs(artifact, output)
            events = server.state.snapshot()
            (output / "fixture_events.json").write_text(
                json.dumps(events, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            attempts = [
                attempt.status
                for transition in artifact.transitions
                for attempt in transition.form_attempts
            ]
            rows.append(
                {
                    "variant": name,
                    "functional_verified": artifact.metrics.functional_workflows_verified,
                    "validation_failures": artifact.metrics.functional_validation_failures,
                    "replay_success": (
                        f"{artifact.metrics.replay_navigation_successes}/"
                        f"{artifact.metrics.replay_attempts}"
                    ),
                    "form_attempt_statuses": attempts,
                    "server_submission_successes": [
                        item["success"]
                        for item in events
                        if item.get("kind") == "model_form_submission"
                    ],
                    "model_calls": artifact.metrics.model_calls,
                    "model_failures": artifact.metrics.model_failures,
                    "input_tokens": artifact.metrics.model_input_tokens,
                    "output_tokens": artifact.metrics.model_output_tokens,
                    "cost_usd": artifact.metrics.monetary_cost_usd,
                    "elapsed_seconds": artifact.metrics.elapsed_seconds,
                    "browser_actions": artifact.metrics.browser_actions,
                }
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    summary = {
        "schema_version": "model-form-comparison-1.0",
        "model": args.model,
        "wall_elapsed_seconds": round(time.monotonic() - started, 3),
        "runs": rows,
    }
    (args.out / "comparison.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
