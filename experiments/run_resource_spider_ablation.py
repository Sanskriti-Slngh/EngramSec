#!/usr/bin/env python3
"""Matched local Crawl Maze policy ablation; never imports evaluator truth."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent1.explorer import Explorer
from agent1.exporter import write_outputs
from agent1.schema import RunConfig
from development_apps.js_heavy_lab import STATE, start_js_heavy_lab
from development_apps.heldout_shop import start_heldout_shop


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:3460/")
    parser.add_argument("--app", choices=("crawlmaze", "js-heavy", "heldout-shop"), default="crawlmaze")
    parser.add_argument("--allow-post-forms", action="store_true")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--tag", default="")
    parser.add_argument(
        "--variants", nargs="+",
        choices=("p0", "spider", "readiness", "replay", "combined", "combined_shallow"),
        required=True,
    )
    parser.add_argument("--seconds", type=float, default=180)
    parser.add_argument("--max-transitions", type=int, default=120)
    parser.add_argument("--max-browser-actions", type=int, default=300)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    summary: list[dict[str, object]] = []
    for variant in args.variants:
        spider = variant in {"spider", "combined", "combined_shallow"}
        readiness = variant in {"readiness", "combined", "combined_shallow"}
        diverse = variant in {"replay", "combined"}
        name = f"{variant}_{args.tag}" if args.tag else variant
        out = args.root / name
        out.mkdir(parents=True, exist_ok=False)
        server = thread = None
        if args.app == "js-heavy":
            server, thread, start_url = start_js_heavy_lab()
            STATE.reset()
            origin_aliases = [f"http://localhost:{server.server_port}"]
        elif args.app == "heldout-shop":
            server, thread, start_url = start_heldout_shop()
            origin_aliases = []
        else:
            start_url = args.url
            origin_aliases = []
        config = RunConfig(
            start_url=start_url,
            output_dir=out,
            policy="multidimensional",
            max_seconds=args.seconds,
            max_transitions=args.max_transitions,
            max_browser_actions=args.max_browser_actions,
            robust_readiness=True,
            readiness_timeout_ms=2_500,
            idle_page_wait_ms=1_600,
            passive_page_wait_ms=200 if readiness else 1_600,
            exploration_mode="persistent",
            interaction_profile="extended",
            hybrid_link_discovery=True,
            origin_aliases=origin_aliases,
            typed_resource_spider=spider,
            max_resource_fetches=100,
            max_resource_depth=3,
            replay_policy="diverse" if diverse else "shallow",
            allow_post_forms=args.allow_post_forms,
            model_provider="none",
            paid_calls_enabled=False,
        )
        try:
            artifact = Explorer(config, Path(__file__).resolve().parents[1]).run()
            write_outputs(artifact, out)
            server_counts = STATE.snapshot() if server and args.app == "js-heavy" else {}
        finally:
            if server:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        metrics = artifact.metrics.model_dump(mode="json")
        metrics["app"] = args.app
        metrics["server_request_counts"] = server_counts
        metrics["run_id"] = artifact.run_id
        metrics["variant"] = name
        (out / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary.append(metrics)
        print(json.dumps({key: metrics.get(key) for key in (
            "variant", "run_id", "elapsed_seconds", "browser_actions", "transitions_observed",
            "navigation_categories_replay_validated", "replay_success_numerator",
            "replay_success_denominator", "replay_untested_paths", "grouped_states",
            "navigation_requests", "network_events_recorded", "resource_references_discovered",
            "resource_fetches_attempted", "resource_fetches_succeeded", "resource_fetch_failures",
            "passive_readiness_wait_ms", "interactive_readiness_wait_ms", "root_reloads",
            "restoration_actions", "graph_connections_missing_evidence", "monetary_cost_usd",
        )}, sort_keys=True), flush=True)
    (args.root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
