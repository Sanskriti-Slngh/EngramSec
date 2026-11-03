"""Audit of the execution-grounded A/B precision regression (diagnostic, not a frozen metric).

Re-scores the saved run artifacts of `evaluation.grounded_ab` with the frozen
M1a scorer (unchanged) and classifies every unmatched ACG capability:

  role_duplicate         same operations (or label and effect) as a ground-truth capability that is
                         already matched, but asserted under a different session role
  repeated_navigation    same role, duplicate of an already-matched navigation capability
  behavioral_split       same role, duplicate of an already-matched non-navigation capability
  absent_from_gt         real operations that match no ground-truth capability or non-capability
  unsupported_effect     no operations, and its label is an annotated non-capability or it matches
                         nothing in the ground truth (an effect inferred without operation evidence)

Run: .venv/bin/python -m evaluation.precision_audit [results/grounded_ab run root]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from agent1.model.importer import import_run_artifact
from agent1.model.materialize import materialize
from evaluation.active_ab import ENVIRONMENTS, ROOT, RESULTS, _gt
from evaluation.score_acg import _op_matches, score_capabilities

CATEGORIES = ("role_duplicate", "repeated_navigation", "behavioral_split", "absent_from_gt", "unsupported_effect")


def _gt_matches(gt, cap: dict, ops: dict) -> list[str]:
    """Ground-truth capabilities this ACG capability would match, ignoring the one-to-one assignment."""
    labels = {l["text"] for l in cap.get("labels", [])}
    cops = [ops[i] for i in cap["operation_ids"]]
    out = []
    for g in gt.capabilities:
        if not g.in_scope:
            continue
        if g.operations:
            if any(_op_matches(o, co) for o in g.operations for co in cops):
                out.append(g.id)
        elif not cops and any(e["kind"] == g.no_operation_effect for e in cap["effects"]) \
                and any(ep.label in labels for ep in g.entry_points if ep.label):
            out.append(g.id)
    return out


def classify(gt, export: dict, score: dict) -> list[dict[str, Any]]:
    ops = {o["id"]: o for o in export["operations"]}
    caps = {c["id"]: c for c in export["capabilities"]}
    gt_by_id = {g.id: g for g in gt.capabilities}
    non_labels = {ep.label for n in gt.non_capabilities for ep in n.entry_points if ep.label}
    rows = []
    for cid in score["unmatched_acg"]:
        cap = caps[cid]
        labels = sorted({l["text"] for l in cap.get("labels", [])})
        targets = [g for g in _gt_matches(gt, cap, ops) if g in score["matches"]]
        if targets:
            g = targets[0]
            if caps[score["matches"][g]]["role"] != cap["role"]:
                category = "role_duplicate"
            elif gt_by_id[g].behavioral_class == "navigation":
                category = "repeated_navigation"
            else:
                category = "behavioral_split"
        elif cap["operation_ids"]:
            category = "absent_from_gt"
        else:
            category = "unsupported_effect"
        rows.append({"capability": cid, "category": category, "duplicate_of": targets[0] if targets else None,
                     "role": cap["role"], "labels": labels, "non_capability_label": bool(set(labels) & non_labels),
                     "operations": sorted(f"{ops[i]['method']} {ops[i]['route']}" for i in cap["operation_ids"]),
                     "effects": sorted({e["kind"] for e in cap["effects"]})})
    return rows


def audit_run(env: str, run_dir: Path) -> dict[str, Any]:
    artifact = json.loads((run_dir / "checkpoint.json").read_text())["artifact"]
    records = import_run_artifact(artifact, "run.json", env)
    export = materialize(records).model_dump(mode="json")
    gt = _gt(env)
    score = score_capabilities(gt, export, records)
    rows = classify(gt, export, score)
    counts = {c: sum(r["category"] == c for r in rows) for c in CATEGORIES}
    p, r = score["m1a_precision"], score["m1a_recall"]
    return {"true_positives": p["matched"], "false_positives": p["denominator"] - p["matched"],
            "asserted": p["denominator"], "precision": p["value"], "recall": r["value"],
            "recall_matched": r["matched"], "recall_denominator": r["denominator"],
            "fp_categories": counts, "unmatched": rows,
            "precision_without_role_duplicates": (p["matched"] / (p["denominator"] - counts["role_duplicate"])
                                                  if p["denominator"] - counts["role_duplicate"] else None)}


def main(root: Path | None = None) -> dict[str, Any]:
    root = root or sorted((ROOT / "agent1" / "experiments").glob("grounded_ab_*"))[-1]
    out: dict[str, Any] = {"source": str(root.relative_to(ROOT)), "runs": {}, "totals": {}}
    for env in ENVIRONMENTS:
        for run_dir in sorted((root / env).iterdir()):
            out["runs"][f"{env}/{run_dir.name}"] = audit_run(env, run_dir)
    for env in ENVIRONMENTS:
        for arm in ("legacy", "tour", "grounded"):
            rs = [v for k, v in out["runs"].items() if k.startswith(f"{env}/{arm}_")]
            if not rs:
                continue
            out["totals"][f"{env}/{arm}"] = {
                "trials": len(rs), "true_positives": sum(r["true_positives"] for r in rs),
                "false_positives": sum(r["false_positives"] for r in rs),
                "mean_precision": round(sum(r["precision"] or 0 for r in rs) / len(rs), 4),
                "mean_recall": round(sum(r["recall"] or 0 for r in rs) / len(rs), 4),
                "fp_categories": {c: sum(r["fp_categories"][c] for r in rs) for c in CATEGORIES},
                "mean_precision_without_role_duplicates": round(
                    sum(r["precision_without_role_duplicates"] or 0 for r in rs) / len(rs), 4)}
    return out


if __name__ == "__main__":
    result = main(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    (RESULTS / "precision_audit.json").write_text(json.dumps(result, indent=1))
    for key, t in result["totals"].items():
        print(f"{key:24s} TP {t['true_positives']:3d} FP {t['false_positives']:3d} P {t['mean_precision']:.3f} "
              f"R {t['mean_recall']:.3f} P(no role dup) {t['mean_precision_without_role_duplicates']:.3f} "
              f"{t['fp_categories']}")
