"""Aggregate analysis of a live shadow run directory (no raw values written).

Run: .venv/bin/python experiments/analyze_live_shadow.py agent1/experiments/live_shadow_<date>
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent1.model.importer import import_run_artifact  # noqa: E402
from agent1.model.materialize import materialize  # noqa: E402
from evaluation.ground_truth import load_ground_truth  # noqa: E402
from evaluation.score_acg import observation_paths, score_capabilities, score_identity  # noqa: E402


def main(base: Path) -> None:
    out = {}
    for lab_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        lab = lab_dir.name
        decisions = [json.loads(x) for x in (lab_dir / "on" / "shadow_decisions.jsonl").read_text().splitlines()]
        made = [d for d in decisions if d.get("proposal")]
        open_d = sum(d.get("open_discovery") or 0 for d in made)
        infeasible = sum(d.get("infeasible_discovery") or 0 for d in made)
        blocked = Counter()
        for d in made:
            blocked.update(d.get("blocked_verification") or {})
        artifact = json.loads((lab_dir / "on" / "checkpoint.json").read_text())["artifact"]
        records = import_run_artifact(artifact, "run.json", lab)
        export = materialize(records).model_dump(mode="json")
        gt = load_ground_truth(ROOT / "evaluation" / "annotations" / f"{lab}.json")
        caps = score_capabilities(gt, export, records)
        ident = score_identity(gt, export, observation_paths(records))
        live = json.loads((lab_dir / "on" / "live_acg.json").read_text())
        out[lab] = {
            "decisions": len(decisions), "proposals": len(made),
            "open_discovery_questions_per_decision": round(open_d / len(made), 2) if made else None,
            "discovery_questions_blocked_or_unreachable_fraction": round(infeasible / (open_d + infeasible), 3)
            if open_d + infeasible else None,
            "blocked_verification_reasons": dict(blocked),
            "legacy_unmatched_ground_truth_capabilities": caps.get("unmatched_gt"),
            "entity_identity": {k: ident[k] for k in ("incorrect_entity_merges", "entity_splits", "entity_instances",
                                                      "true_instances_observed") if k in ident},
            "context_dependent_controls": sum(1 for c in live["claims"] if c["predicate"] == "observed_disabled"),
            "establishes_claims": sum(1 for c in live["claims"] if c["predicate"] == "establishes"),
            "learned_predicates": len(live["learned_predicates"]),
            "gaps": [g["kind"] for g in live["gaps"]],
            "unsupported_or_blocked_affordances": sum(1 for a in live["affordances"] if a["status"] == "blocked"),
        }
    (base / "analysis.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
