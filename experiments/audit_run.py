#!/usr/bin/env python3
"""Rebuild derived feature nodes from immutable raw run evidence.

This intentionally writes to a new directory. It is useful when a feature
identity rule changes after a run without pretending the browser experiment was
rerun or altering its original report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent1.exporter import write_outputs
from agent1.explorer import Explorer
from agent1.schema import EvidenceStatus, RunArtifact, RunConfig, utc_now


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_json", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit(f"audit output already exists and is not empty: {args.out}")

    artifact = RunArtifact.model_validate_json(args.run_json.read_text(encoding="utf-8"))
    config_data = dict(artifact.config)
    config_data.update(output_dir=args.out, model_provider="none", model_name=None)
    explorer = Explorer(RunConfig.model_validate(config_data), ROOT)
    explorer.artifact = artifact
    explorer._observation_ids = {item.id for item in artifact.observations}

    original_count = artifact.metrics.distinct_validated_feature_workflows
    artifact.features = explorer._build_features()
    validated = [item for item in artifact.features if item.status == EvidenceStatus.REPLAY_VALIDATED]
    artifact.metrics.distinct_validated_feature_workflows = len(validated)
    artifact.metrics.incorrect_state_merges = explorer._audit_incorrect_merges()
    artifact.notes.append(
        "Post-run feature-identity audit: repeated site-wide links were collapsed across source states; "
        "raw observations, transitions, replays, and the original run directory remain unchanged."
    )
    write_outputs(artifact, args.out)
    metadata = {
        "schema_version": "agent1-derived-audit-1.0",
        "audited_at": utc_now(),
        "source_run": str(args.run_json),
        "original_reported_validated_workflows": original_count,
        "audited_validated_workflows": len(validated),
        "raw_evidence_changed": False,
        "feature_identity": (
            "links: kind+normalized target route; non-links: action/form shape plus observable outcome; "
            "source states retained as evidence but excluded from identity; volatile carousel controls excluded"
        ),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "audit_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
