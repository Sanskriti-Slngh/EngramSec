#!/usr/bin/env python3
"""Apply the independent fixture evaluator to preserved mapper artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent1.schema import RunArtifact
from experiments.run_validation_fixtures import evaluate
from tests.fixtures.ground_truth import CASES


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite existing evaluation: {args.out}")
    cases = []
    for case in CASES:
        case_dir = args.run_dir / case
        if not (case_dir / "run.json").exists():
            continue
        artifact = RunArtifact.model_validate_json((case_dir / "run.json").read_text(encoding="utf-8"))
        events = json.loads((case_dir / "fixture_events.json").read_text(encoding="utf-8"))
        cases.append(evaluate(case, artifact, events))
    total_keys = (
        "functional_false_positives",
        "functional_false_negatives",
        "navigation_validation_false_positives",
        "incorrect_merges",
        "unnecessary_splits",
    )
    result = {
        "schema_version": "validation-posthoc-1.0",
        "source_run_dir": str(args.run_dir),
        "raw_evidence_changed": False,
        "cases": cases,
        "totals": {key: sum(int(item.get(key, 0) or 0) for item in cases) for key in total_keys},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
