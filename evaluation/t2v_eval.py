"""Phase 2 step 1 (T2V): preregistered offline check of the scheduler cleanup.

Frozen before `tour_v2` exists. Compares `tour_v2` (deterministic seeded-uniform
movement between areas, structural deduplication of global navigation,
explicit `blocked_unrestorable_context` for verification that cannot be
restored) with the frozen `tour_full` and the baselines, on fresh seeds, using
the unchanged T2 simulator, run loop, risk gate and scorer through
`evaluation.t2r_eval`.

Run: .venv/bin/python -m evaluation.t2v_eval
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from evaluation import t2r_eval as r

RESULTS = Path(__file__).resolve().parents[1] / "evaluation" / "results"
SEEDS = list(range(3000, 3030))                  # never used before
POLICIES = ["bfs", "legacy_frontier", "tour_full", "tour_v2"]
WEAK = {"crud_writes_without_snapshots": ("writes_without_snapshots", 150),
        "duplicate_pages": ("misleading_novelty", 150)}
GUARDS = {"flat": ("flat", 100), "prerequisites": ("prerequisites", 200), "instances": ("instances", 150)}

T2V = {
    "V1_crud": "AUC(tour_v2) > AUC(tour_full) on writes_without_snapshots (CRUD app at L2); mean difference > 0 "
               "and one-sided sign test p < 0.05",
    "V2_duplicates": "AUC(tour_v2) > AUC(tour_full) on misleading_novelty (30 duplicate pages); same rule",
    "V3_verification": "on writes_without_snapshots: mean verification actions spent on items that never reach "
                       "REPRODUCED (scheduler summary `verification_wasted_actions`) lower for tour_v2 than tour_full; "
                       "tour_v2 records `blocked_unrestorable_context` in >= 1 seed; 0 write re-executions",
    "G1_flat": "mean AUC(tour_v2) >= 0.95 x mean AUC(bfs) on flat@100",
    "G2_prerequisites": "tour_v2 gated recall >= legacy in >= 80% of seeds at 200 actions",
    "G3_instances": "<= 3 non-split sampled instances in every seed",
    "G4_safety": "0 gate refusals for tour_v2 in every run; identical decision logs on rerun of 10 seeds",
    "reported_only": "AUC(tour_v2) vs AUC(legacy_frontier) on the two weak regimes",
    "success": "V1, V2, V3 and G1-G4 all pass",
}


def jobs() -> list[tuple]:
    out = []
    for scenario, budget in list(WEAK.values()) + list(GUARDS.values()):
        out.extend((p, scenario, s, budget) for p in POLICIES for s in SEEDS)
    return out


def evaluate(runs: list[dict], repeats: list[dict]) -> dict:
    by = r._by
    t = {}
    for key, (scenario, _) in (("V1_crud", WEAK["crud_writes_without_snapshots"]),
                               ("V2_duplicates", WEAK["duplicate_pages"])):
        v2, full, leg = (by(runs, p, scenario) for p in ("tour_v2", "tour_full", "legacy_frontier"))
        t[key] = r._paired({s: x["auc"] for s, x in v2.items()}, {s: x["auc"] for s, x in full.items()})
        t[key]["vs_legacy"] = r._paired({s: x["auc"] for s, x in v2.items()}, {s: x["auc"] for s, x in leg.items()})
    scenario = WEAK["crud_writes_without_snapshots"][0]
    v2, full = by(runs, "tour_v2", scenario), by(runs, "tour_full", scenario)
    waste = lambda rs: r._mean(x.get("scheduler", {}).get("verification_wasted_actions") for x in rs.values())
    unrestorable = sum(x.get("scheduler", {}).get("verification_blocked_reasons", {})
                       .get("blocked_unrestorable_context", 0) > 0 for x in v2.values())
    reexec = sum(x["write_reexecutions"] for x in v2.values())
    t["V3_verification"] = {"waste_v2": waste(v2), "waste_full": waste(full), "seeds_with_unrestorable": unrestorable,
                            "write_reexecutions": reexec,
                            "pass": waste(v2) < waste(full) and unrestorable >= 1 and reexec == 0}
    v2, bfs = by(runs, "tour_v2", "flat"), by(runs, "bfs", "flat")
    a, b = r._mean(x["auc"] for x in v2.values()), r._mean(x["auc"] for x in bfs.values())
    t["G1_flat"] = {"auc_v2": a, "auc_bfs": b, "ratio": round(a / b, 4) if b else 0, "pass": b > 0 and a >= 0.95 * b}
    v2, leg = by(runs, "tour_v2", "prerequisites", 200), by(runs, "legacy_frontier", "prerequisites", 200)
    seeds = sorted(set(v2) & set(leg))
    frac = r._mean(float(v2[s]["gated_at"][200] >= leg[s]["gated_at"][200]) for s in seeds)
    t["G2_prerequisites"] = {"fraction": frac, "mean_v2": r._mean(v2[s]["gated_at"][200] for s in seeds),
                             "mean_legacy": r._mean(leg[s]["gated_at"][200] for s in seeds), "pass": frac >= 0.8}
    inst = [x["instances"]["non_split_instances"] for x in by(runs, "tour_v2", "instances").values()]
    t["G3_instances"] = {"max": max(inst), "pass": max(inst) <= 3}
    refusals = sum(x["unsafe_attempts"] for x in runs if x["policy"] == "tour_v2" and "error" not in x)
    first = by(runs, "tour_v2", "writes_without_snapshots")
    same = [first[x["seed"]]["decision_hash"] == x["decision_hash"] for x in repeats if x["seed"] in first]
    t["G4_safety"] = {"gate_refusals": refusals, "identical_reruns": sum(same), "reruns": len(same),
                      "pass": refusals == 0 and bool(same) and all(same)}
    t["success"] = all(t[k]["pass"] for k in ("V1_crud", "V2_duplicates", "V3_verification", "G1_flat",
                                               "G2_prerequisites", "G3_instances", "G4_safety"))
    return t


def main() -> None:
    r.install()
    start = time.time()
    with ProcessPoolExecutor(max_workers=9) as pool:
        runs = list(pool.map(r.job, jobs(), chunksize=1))
        repeats = list(pool.map(r.job, [("tour_v2", "writes_without_snapshots", s, 150) for s in SEEDS[:10]]))
    tests = evaluate(runs, repeats)
    slim = [{k: v for k, v in x.items() if k != "calibration"} for x in runs]
    (RESULTS / "t2v_runs.json").write_text(json.dumps({"runs": slim}, default=str))
    (RESULTS / "t2v_tests.json").write_text(json.dumps(tests, indent=1, default=str))
    print(json.dumps({k: v["pass"] if isinstance(v, dict) else v for k, v in tests.items()}),
          f"errors={sum('error' in x for x in runs)}", f"{time.time() - start:.0f}s")


if __name__ == "__main__":
    main()
