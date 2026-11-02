"""Aggregate T2R runs into per-scenario scorecards (no new measurements).

Run after `python -m evaluation.t2r_eval --all`:  .venv/bin/python -m evaluation.t2r_scorecard
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from evaluation.sim_scorecard import CATEGORY, _mean

RESULTS = Path(__file__).resolve().parents[1] / "evaluation" / "results"
POLICIES = ["bfs", "legacy_frontier", "acg_uniform", "acg_full", "tour_full", "tour_no_local", "tour_no_global"]


def summarize(rs: list[dict]) -> dict:
    ap = lambda k: _mean(r["actions_by_purpose"].get(k, 0) for r in rs)
    curves = [r["curve"] for r in rs]
    width = max((len(c) for c in curves), default=0)
    out = {
        "runs": len(rs), "auc": _mean(r["auc"] for r in rs), "recall": _mean(r["final"]["recall"] for r in rs),
        "recall_curve": [_mean(c[i] for c in curves if i < len(c)) for i in range(width)],
        "gated_recall": {str(b): _mean(r["gated_at"].get(str(b), r["gated_at"].get(b)) for r in rs)
                         for b in sorted({int(k) for r in rs for k in r["gated_at"]})},
        "reproduced": _mean(r["final"]["reproduced"] for r in rs), "verified": _mean(r["final"]["verified"] for r in rs),
        "false_merges": _mean(r["final"]["false_merges"] for r in rs),
        "false_splits": _mean(r["final"]["false_splits"] for r in rs),
        "role_duplicate_splits": _mean(r["final"]["role_duplicate_splits"] for r in rs),
        "non_split_instances": _mean(r["instances"]["non_split_instances"] for r in rs),
        "actions_used": _mean(r["used"] for r in rs),
        "discovery_actions": ap("discovery_actions"), "verification_actions": ap("verification_actions"),
        "restoration_actions": ap("restoration_actions"), "area_switches": ap("area_switches"),
        "area_switch_restoration_actions": ap("area_switch_restoration_actions"),
        "fresh_or_snapshot_steps": ap("fresh_or_snapshot_steps"),
        "gate_refusals": sum(r["unsafe_attempts"] for r in rs),
        "write_reexecutions": sum(r["write_reexecutions"] for r in rs),
        "planner_ms_per_decision": _mean(r["planner_ms_per_decision"] for r in rs),
        "materialize_ms_per_decision": _mean(r["materialize_ms_per_decision"] for r in rs),
        "stopped_early": sum(r["stop"] != "budget" for r in rs),
    }
    if any("chains" in r for r in rs):
        out["chains"] = {k: sum(r.get("chains", {}).get(k, 0) for r in rs) for k in ("chains", "completed", "abandoned")}
    sch = [r["scheduler"] for r in rs if r.get("scheduler")]
    if sch:
        out["scheduler"] = {
            "mean_tours": _mean(s["tours"] for s in sch), "mean_tour_length": _mean(s["mean_tour_length"] for s in sch),
            "tour_end_reasons": dict(sum((Counter(s["tour_end_reasons"]) for s in sch), Counter())),
            "chain_events": sum(s["chain_events"] for s in sch),
            "chain_continuations_executed": sum(s["chain_continuations_executed"] for s in sch),
            "chain_events_not_executed": sum(s["chain_events_not_executed"] for s in sch),
            "chain_events_cross_page": sum(s["chain_events_cross_page"] for s in sch),
            "chain_events_across_contexts": sum(s.get("chain_events_across_contexts", 0) for s in sch),
            "revisits": sum(s["revisits"] for s in sch),
            "verification_blocked": sum(s["verification_blocked"] for s in sch),
            "verification_blocked_reasons": dict(sum((Counter(s["verification_blocked_reasons"]) for s in sch),
                                                     Counter())),
            "runs_ending_in_breadth_mode": sum(s["final_mode"] == "breadth" for s in sch),
            "mode_switches": sum(len(s["mode_switches"]) for s in sch),
        }
    return out


def main() -> None:
    runs = [r for r in json.loads((RESULTS / "t2r_runs.json").read_text())["runs"] if "error" not in r]
    groups = defaultdict(list)
    for r in runs:
        groups[(r["scenario"], r["budget"], r["policy"])].append(r)
        if r["scenario"] == "mixed":
            groups[("mixed:" + r["arch"], r["budget"], r["policy"])].append(r)
            groups[("category:" + CATEGORY[r["arch"]], r["budget"], r["policy"])].append(r)
    card = defaultdict(dict)
    for (scenario, budget, policy), rs in sorted(groups.items()):
        card[f"{scenario}@{budget}"][policy] = summarize(rs)
    tests = json.loads((RESULTS / "t2r_tests.json").read_text())
    (RESULTS / "t2r_scorecard.json").write_text(json.dumps({"tests": tests, "scorecard": card}, indent=1))
    for key, row in card.items():
        print(f"{key:34}", " ".join(f"{p[:9]}:{row[p]['auc']:.3f}/{row[p]['recall']:.2f}" for p in POLICIES if p in row))


if __name__ == "__main__":
    main()
