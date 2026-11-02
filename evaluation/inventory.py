"""Inventory of local development archives and the evidence each contains.

Writes aggregate facts only (paths, counts, capture flags, archive digests).
Run: .venv/bin/python -m evaluation.inventory
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from agent1.model.importer import import_path
from .datasets import DATASETS, ROOT, archive_paths

OUT = ROOT / "evaluation" / "development_inventory.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe(path: Path, application: str) -> dict[str, object]:
    if not path.exists():
        return {"archive": str(path.relative_to(ROOT)), "exists": False}
    records = import_path(path, application, ROOT)
    capture = records[0].capture.model_dump()
    kinds = Counter(r.kind for r in records)
    actions = [r for r in records if r.kind == "action"]
    observations = [r for r in records if r.kind == "observation"]
    missing = sorted(k for k, v in capture.items() if not v)
    if observations and all(o.url_confidence == "group_representative" for o in observations if o.context == "exploration"):
        missing.append("exact_observation_urls")
    return {
        "archive": str(path.relative_to(ROOT)), "exists": True, "sha256": sha256(path),
        "format": "graph_a" if path.name == "graph_a.json" else path.name.removesuffix(".json"),
        "records": dict(sorted(kinds.items())),
        "actions_by_status": dict(sorted(Counter(a.status for a in actions).items())),
        "replays_by_kind": dict(sorted(Counter(r.verification_kind for r in records if r.kind == "replay").items())),
        "observations_with_affordances": sum(1 for o in observations if o.affordances),
        "observations_with_group_representative_url": sum(1 for o in observations if o.url_confidence != "exact"),
        "capture": capture, "not_captured": missing,
    }


def main() -> None:
    report = {name: {"role": spec["role"], "annotation": spec["annotation"],
                     "archives": [describe(p, name) for p in archive_paths(name)]}
              for name, spec in DATASETS.items()}
    OUT.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for name, item in report.items():
        present = [a for a in item["archives"] if a["exists"]]
        print(name, f"{len(present)}/{len(item['archives'])} archives", present[0]["not_captured"] if present else "")


if __name__ == "__main__":
    main()
