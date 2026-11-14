"""Aggregate Phase 1b runs into the cross-scenario scorecard (no new measurements).

Run after `python -m evaluation.sim_eval --all`:
    .venv/bin/python -m evaluation.sim_scorecard
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[1] / "evaluation" / "results"
POLICIES = ["bfs", "legacy_frontier", "acg_uniform", "acg_no_unlock", "acg_full"]
CATEGORY = {"flat": "flat", "flaky": "noisy", "workflow": "stateful", "crud": "stateful", "client_only": "client_only",
            "large_list": "structured", "duplicate_pages": "structured", "state_variants": "structured",
            "roles": "structured", "hidden_ids": "structured"}


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def summarize(rs: list[dict]) -> dict:
    curves = [r["curve"] for r in rs]
    width = max((len(c) for c in curves), default=0)
    return {
        "runs": len(rs),
        "recall": _mean(r["final"]["recall"] for r in rs),
        "auc": _mean(r["auc"] for r in rs),
        "recall_curve": [_mean(c[i] for c in curves if i < len(c)) for i in range(width)],
        "gated_recall": {str(b): _mean(r["gated_at"].get(str(b), r["gated_at"].get(b)) for r in rs)
                         for b in sorted({int(k) for r in rs for k in r["gated_at"]})},
        "reproduced": _mean(r["final"]["reproduced"] for r in rs),
        "verified": _mean(r["final"]["verified"] for r in rs),
        "false_merges": _mean(r["final"]["false_merges"] for r in rs),
        "false_splits": _mean(r["final"]["false_splits"] for r in rs),
        "role_duplicate_splits": _mean(r["final"]["role_duplicate_splits"] for r in rs),
        "redundant_instances": _mean(max(0, r["instances"]["non_split_instances"] - 3) for r in rs),
        "distinct_instances": _mean(r["instances"]["distinct_instances"] for r in rs),
        "actions_used": _mean(r["used"] for r in rs),
        "restoration_share": _mean(r["restoration_actions"] / max(1, r["used"]) for r in rs),
        "unsafe_attempts": sum(r["unsafe_attempts"] for r in rs),
        "planner_ms_per_decision": _mean(r["planner_ms_per_decision"] for r in rs),
        "materialize_ms_per_decision": _mean(r["materialize_ms_per_decision"] for r in rs),
        "stopped_early": sum(r["stop"] != "budget" for r in rs),
    }


def main() -> None:
    data = json.loads((RESULTS / "t2_runs.json").read_text())
    runs = [r for r in data["runs"] if "error" not in r]
    errors = [r for r in data["runs"] if "error" in r]
    groups: dict[tuple, list] = defaultdict(list)
    for r in runs:
        groups[(r["scenario"], r["budget"], r["policy"])].append(r)
        if r["scenario"] == "mixed":
            groups[("mixed:" + r["arch"], r["budget"], r["policy"])].append(r)
            groups[("category:" + CATEGORY[r["arch"]], r["budget"], r["policy"])].append(r)
    card = defaultdict(dict)
    for (scenario, budget, policy), rs in sorted(groups.items()):
        card[f"{scenario}@{budget}"][policy] = summarize(rs)
    out = {"errors": len(errors), "tests": json.loads((RESULTS / "t2_tests.json").read_text()), "scorecard": card}
    (RESULTS / "t2_scorecard.json").write_text(json.dumps(out, indent=1))
    for key, row in card.items():
        print(f"{key:40}", "  ".join(f"{p[:10]}:{row[p]['auc']:.3f}/{row[p]['recall']:.2f}" for p in POLICIES if p in row))


if __name__ == "__main__":
    main()
