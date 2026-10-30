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
from experiments.evaluate_coverage import evaluate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:3460/")
    parser.add_argument("--app", choices=("crawlmaze", "js-heavy", "heldout-shop"), default="crawlmaze")
    parser.add_argument("--allow-post-forms", action="store_true")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--tag", default="")
    parser.add_argument(
        "--variants", nargs="+",
        choices=(
            "p0", "spider", "readiness", "replay", "combined", "combined_shallow",
            "fifo", "route_diverse", "marginal_value", "random",
            "adaptive_readiness", "adaptive_budget", "recursive_depth",
        ),
        required=True,
    )
    parser.add_argument("--seconds", type=float, default=180)
    parser.add_argument("--max-transitions", type=int, default=120)
    parser.add_argument("--max-browser-actions", type=int, default=300)
    parser.add_argument("--max-resource-fetches", type=int, default=100)
    parser.add_argument(
        "--readiness-strategy", choices=("fixed", "adaptive"), default="fixed"
    )
    parser.add_argument(
        "--budget-allocation-strategy", choices=("fixed", "adaptive"), default="fixed"
    )
    parser.add_argument("--random-seed", type=int, default=0)
    parser.add_argument("--javascript-reference-parser", choices=("legacy_regex", "ast"), default="ast")
    parser.add_argument("--no-shared-frontier", action="store_true")
    parser.add_argument("--max-fetches-per-observation", type=int, default=10)
    parser.add_argument("--max-resource-depth", type=int, default=3)
    parser.add_argument("--document-budget", type=int)
    parser.add_argument("--script-budget", type=int)
    parser.add_argument("--stylesheet-budget", type=int)
    parser.add_argument("--asset-budget", type=int)
    parser.add_argument("--zap-evidence", type=Path)
    parser.add_argument("--zap-source-origin")
    parser.add_argument("--max-total-http-requests", type=int)
    parser.add_argument("--state-reuse", choices=("root", "prefix"), default="root")
    parser.add_argument("--resource-allocation", choices=("class_caps", "shared_http"), default="class_caps")
    parser.add_argument("--passive-document-http-reserve", type=int)
    parser.add_argument("--max-passive-document-fetches", type=int)
    parser.add_argument("--html-extraction", choices=("baseline", "extended"), default="baseline")
    parser.add_argument("--max-speculative-fetches", type=int, default=0)
    parser.add_argument("--exploration-policy", choices=("multidimensional", "hierarchical"), default="multidimensional")
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    summary: list[dict[str, object]] = []
    for variant in args.variants:
        spider = variant in {
            "spider", "combined", "combined_shallow", "fifo", "route_diverse",
            "marginal_value", "random", "adaptive_readiness", "adaptive_budget",
            "recursive_depth",
        }
        readiness = variant in {
            "readiness", "combined", "combined_shallow", "fifo", "route_diverse",
            "marginal_value", "random", "adaptive_readiness", "adaptive_budget",
        }
        diverse = variant in {"replay", "combined"}
        frontier_policy = {
            "route_diverse": "route_diverse",
            "marginal_value": "marginal_value",
            "random": "random",
        }.get(variant, "fifo")
        readiness_strategy = (
            "adaptive" if variant == "adaptive_readiness" else args.readiness_strategy
        )
        budget_strategy = (
            "adaptive" if variant == "adaptive_budget" else args.budget_allocation_strategy
        )
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
            policy=args.exploration_policy,
            max_seconds=args.seconds,
            max_transitions=args.max_transitions,
            max_browser_actions=args.max_browser_actions,
            robust_readiness=True,
            readiness_timeout_ms=2_500,
            idle_page_wait_ms=1_600,
            passive_page_wait_ms=200 if readiness else 1_600,
            readiness_strategy=readiness_strategy,
            exploration_mode="persistent",
            interaction_profile="extended",
            hybrid_link_discovery=True,
            origin_aliases=origin_aliases,
            typed_resource_spider=spider,
            max_resource_fetches=args.max_resource_fetches,
            max_resource_depth=6 if variant == "recursive_depth" else args.max_resource_depth,
            max_resource_fetches_per_observation=args.max_fetches_per_observation,
            max_resource_document_fetches=args.document_budget,
            max_resource_script_fetches=args.script_budget,
            max_resource_stylesheet_fetches=args.stylesheet_budget,
            max_resource_asset_fetches=args.asset_budget,
            resource_frontier_policy=frontier_policy,
            resource_random_seed=args.random_seed,
            javascript_reference_parser=args.javascript_reference_parser,
            share_resource_frontier=not args.no_shared_frontier,
            budget_allocation_strategy=budget_strategy,
            replay_policy="diverse" if diverse else "shallow",
            zap_evidence_path=args.zap_evidence,
            zap_source_origin=args.zap_source_origin,
            max_total_http_requests=args.max_total_http_requests,
            state_reuse=args.state_reuse,
            resource_allocation=args.resource_allocation,
            passive_document_http_reserve=args.passive_document_http_reserve,
            max_passive_document_fetches=args.max_passive_document_fetches,
            html_extraction=args.html_extraction,
            max_speculative_fetches=args.max_speculative_fetches,
            allow_post_forms=args.allow_post_forms,
            model_provider="none",
            paid_calls_enabled=False,
        )
        try:
            artifact = Explorer(config, Path(__file__).resolve().parents[1]).run()
            write_outputs(artifact, out)
            if args.app == "heldout-shop":
                # Evaluator ground truth is loaded only after the frozen graph
                # has been produced; Explorer receives neither this data nor labels.
                graph = json.loads((out / "graph_a.json").read_text(encoding="utf-8"))
                truth_path = Path(__file__).resolve().parents[1] / "development_apps" / "heldout_shop_ground_truth.json"
                truth = json.loads(truth_path.read_text(encoding="utf-8"))
                evaluation = evaluate(graph, truth)
                (out / "coverage_evaluation.json").write_text(
                    json.dumps(evaluation, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
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
        (out / "experiment_config.json").write_text(
            json.dumps(
                {
                    "app": args.app,
                    "target": start_url,
                    "variant": name,
                    "source_revision": artifact.code_revision,
                    "run_config": config.model_dump(mode="json", exclude={"output_dir"}),
                    "resource_budgets": {
                        "total": args.max_resource_fetches,
                        "document": args.document_budget,
                        "script": args.script_budget,
                        "stylesheet": args.stylesheet_budget,
                        "other_asset": args.asset_budget,
                    },
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        (out / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary.append(metrics)
        print(json.dumps({key: metrics.get(key) for key in (
            "variant", "run_id", "elapsed_seconds", "browser_actions", "transitions_observed",
            "navigation_categories_replay_validated", "replay_success_numerator",
            "replay_success_denominator", "replay_untested_paths", "grouped_states",
            "navigation_requests", "network_events_recorded", "resource_references_discovered",
            "resource_fetches_attempted", "resource_fetches_succeeded", "resource_fetch_failures",
            "resource_fetch_budget_exhausted", "resource_fetch_class_budget_exhausted",
            "resource_references_extracted", "resource_references_queued",
            "resource_new_references", "resource_unresolved_candidates",
            "passive_readiness_wait_ms", "interactive_readiness_wait_ms", "root_reloads",
            "restoration_actions", "graph_connections_missing_evidence", "monetary_cost_usd",
        )}, sort_keys=True), flush=True)
    (args.root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
