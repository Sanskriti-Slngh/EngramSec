from __future__ import annotations

import argparse
import json
from pathlib import Path

from .exporter import write_outputs
from .explorer import Explorer
from .providers import load_repository_environment
from .schema import Checkpoint, RunConfig


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--max-transitions", type=int, default=20)
    parser.add_argument("--max-browser-actions", type=int, default=80)
    parser.add_argument(
        "--policy",
        choices=("exact", "grouped", "selective_model", "model_all"),
        default="grouped",
    )
    parser.add_argument("--provider", choices=("none", "ollama", "groq", "openai"), default="none")
    parser.add_argument("--model")
    parser.add_argument("--model-forms", action="store_true")
    parser.add_argument("--max-form-retries", type=int, default=1, choices=(0, 1, 2))
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--allow-post-forms", action="store_true")
    parser.add_argument("--context-label", default="anonymous")
    parser.add_argument(
        "--search-probe",
        dest="search_probe_primary",
        help="ordinary primary query for paired GET-search verification",
    )
    parser.add_argument(
        "--search-contrast",
        dest="search_probe_contrast",
        help="distinct ordinary contrast query for paired GET-search verification",
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="EngramSec Agent 1 browser workflow mapper")
    commands = root.add_subparsers(dest="command", required=True)
    map_command = commands.add_parser("map", help="start a new mapping run")
    map_command.add_argument("--url", required=True)
    map_command.add_argument("--out", type=Path, required=True)
    _add_common(map_command)

    resume = commands.add_parser("resume", help="resume a saved checkpoint")
    resume.add_argument("--checkpoint", type=Path, required=True)
    resume.add_argument("--seconds", type=float, default=60.0)
    resume.add_argument("--max-transitions", type=int)
    resume.add_argument("--max-browser-actions", type=int)

    deepen = commands.add_parser("deepen", help="prioritize an unresolved action or feature label")
    deepen.add_argument("--checkpoint", type=Path, required=True)
    deepen.add_argument("--query", required=True)
    deepen.add_argument("--seconds", type=float, default=120.0)
    deepen.add_argument("--max-transitions", type=int)
    deepen.add_argument("--max-browser-actions", type=int)
    return root


def _config_from_checkpoint(args: argparse.Namespace) -> RunConfig:
    checkpoint = Checkpoint.model_validate_json(args.checkpoint.read_text(encoding="utf-8"))
    stored = dict(checkpoint.artifact.config)
    stored["output_dir"] = str(args.checkpoint.parent)
    stored["resume_from"] = str(args.checkpoint)
    stored["seconds"] = args.seconds
    stored["max_seconds"] = args.seconds
    if args.max_transitions is not None:
        stored["max_transitions"] = args.max_transitions
    if args.max_browser_actions is not None:
        stored["max_browser_actions"] = args.max_browser_actions
    if args.command == "deepen":
        stored["focus_query"] = args.query
    return RunConfig.model_validate(stored)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    load_repository_environment(REPOSITORY_ROOT)
    if args.command == "map":
        if args.out.exists() and any(args.out.iterdir()):
            raise SystemExit(f"output directory is not empty: {args.out}")
        config = RunConfig(
            start_url=args.url,
            output_dir=args.out,
            policy=args.policy,
            max_seconds=args.seconds,
            max_transitions=args.max_transitions,
            max_browser_actions=args.max_browser_actions,
            headless=not args.headed,
            allow_post_forms=args.allow_post_forms,
            context_label=args.context_label,
            model_provider=args.provider,
            model_name=args.model,
            model_form_assistance=args.model_forms,
            max_form_retries=args.max_form_retries,
            search_probe_primary=args.search_probe_primary,
            search_probe_contrast=args.search_probe_contrast,
            paid_calls_enabled=False,
        )
    else:
        config = _config_from_checkpoint(args)
    artifact = Explorer(config, REPOSITORY_ROOT).run()
    write_outputs(artifact, config.output_dir)
    print(
        json.dumps(
            {
                "run_id": artifact.run_id,
                "output_dir": str(config.output_dir.resolve()),
                "navigation_categories_replay_validated": (
                    artifact.metrics.navigation_categories_replay_validated
                ),
                "functional_workflows_verified": artifact.metrics.functional_workflows_verified,
                "functional_validation_failures": artifact.metrics.functional_validation_failures,
                "replay": {
                    "attempts": artifact.metrics.replay_attempts,
                    "navigation_successes": artifact.metrics.replay_navigation_successes,
                    "failures": artifact.metrics.replay_failures,
                    "untested_paths": artifact.metrics.replay_untested_paths,
                },
                "graph_connections_missing_evidence": (
                    artifact.metrics.graph_connections_missing_evidence
                ),
                "cost_usd": artifact.metrics.monetary_cost_usd,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
