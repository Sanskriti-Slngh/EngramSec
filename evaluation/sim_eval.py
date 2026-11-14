"""Phase 1b harness: run any selector on a simulated application and score it.

Every policy goes through the same loop: the same adapter (executor and
costs), the same risk gate, the same budget, and the same ACG materializer
over its own evidence log. Scoring reads the simulator's hidden truth through
`Oracle` and never a policy's beliefs.

Run all preregistered tests:  .venv/bin/python -m evaluation.sim_eval --all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from agent1.model.materialize import materialize
from agent1.model.schema import STATUS_RANK, Status
from agent1.planner.baselines import BFS, LegacyFrontier
from agent1.planner.gate import RiskGate
from agent1.planner.interfaces import AgentView

from evaluation.appsim import Oracle, SimAdapter, build, relabel
from evaluation.sim_scenarios import CHECKPOINT, SCENARIOS, SEEDS, STRESS, STRESS_SEEDS, T2, arch_for

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "results"


def policy_factory(name: str):
    if name == "bfs":
        return BFS
    if name == "legacy_frontier":
        return LegacyFrontier
    from agent1.planner.planner import make_planner      # implemented after this harness was frozen
    return make_planner(name)


# ---------------------------------------------------------------------------------- scoring
def score(oracle: Oracle, records: list) -> dict[str, Any]:
    acg = materialize(records)
    spec = oracle.spec
    observable = {c.id for c in spec.caps.values() if c.observable}
    gated = {c.id for c in spec.caps.values() if c.observable and c.gated}
    majority: dict[str, str] = {}
    merges, members = [], defaultdict(set)
    for cap in acg.capabilities:
        truth = Counter(oracle.actions[a] for a in cap.action_ids if oracle.actions.get(a))
        if not truth:
            continue
        majority[cap.id] = sorted(truth.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        if len(truth) > 1:
            merges.append(sorted(truth))
        for t in truth:
            members[t].add(cap.id)
    found = set(majority.values()) & observable
    roles = {c.id: c.role for c in acg.capabilities}
    splits = {t: sorted(c) for t, c in members.items() if len(c) > 1}
    same_role_splits = {t: c for t, c in splits.items() if len({roles[x] for x in c}) < len(c)}
    status = {c.id: c.status for c in acg.capabilities}

    def reached(rank: Status) -> int:
        return len({t for c, t in majority.items() if t in observable and STATUS_RANK.get(status[c], -1) >= STATUS_RANK[rank]})
    return {
        "recall": len(found) / max(1, len(observable)), "found": len(found), "observable": len(observable),
        "gated_recall": (len(found & gated) / len(gated)) if gated else None, "gated_found": len(found & gated),
        "gated": len(gated), "acg_capabilities": len(acg.capabilities),
        "unidentified": sum(c.unidentified for c in acg.capabilities),
        "false_merges": len(merges), "false_splits": len(same_role_splits),
        "role_duplicate_splits": len(splits) - len(same_role_splits),
        "reproduced": reached(Status.REPRODUCED), "verified": reached(Status.VERIFIED),
        "found_ids": sorted(found),
    }


def instance_waste(oracle: Oracle) -> dict[str, Any]:
    """T2b: distinct instances of a large collection's detail page, by the kind of plan that first visited them."""
    large = {k for k, e in oracle.spec.entities.items() if e.large}
    detail = {k for k, p in oracle.spec.pages.items() if p.entity in large and k.startswith("detail_")}
    first: dict[str, str] = {}
    for oid in sorted(oracle.obs, key=lambda o: int(o[1:])):
        page, inst = oracle.obs[oid]
        if page in detail and inst not in first:
            first[inst] = oracle.plan_kind_of_obs.get(oid, "")
    by_kind = Counter(first.values())
    return {"distinct_instances": len(first), "non_split_instances": len(first) - by_kind.get("split_test", 0),
            "by_plan_kind": dict(sorted(by_kind.items()))}


# ---------------------------------------------------------------------------------- one run
def run(policy: str, scenario: str, seed: int, budget: int, *, label_mode: str | None = None,
        keep: bool = False) -> dict[str, Any]:
    conf = SCENARIOS.get(scenario) or STRESS[scenario]
    spec = build(arch_for(scenario, seed), seed, **conf["kw"])
    if label_mode:
        relabel(spec, label_mode)
    adapter = SimAdapter(spec)
    records = adapter.start()
    used_at = [0] * len(records)
    gate = RiskGate(adapter.isolation)
    gate.observe(records)
    selector = policy_factory(policy)(adapter.isolation, adapter.costs, budget, seed)
    used, refused, stalled, live = 0, [], 0, records[-1].obs_id
    purpose: Counter = Counter()
    planner_s = materialize_s = 0.0
    calibration, pending = [], None
    acg = None
    plans = Counter()
    stop = "selector_done"
    while True:
        if selector.uses_acg or pending is not None:
            t = time.perf_counter()
            acg = materialize(records)
            materialize_s += time.perf_counter() - t
        if pending is not None:
            before, p_new, action_ids, truth_before = pending
            cap_of = {a: c.id for c in acg.capabilities for a in c.action_ids}
            new = any(cap_of.get(a) and cap_of[a] not in before for a in action_ids)
            truth_new = any(adapter_truth(adapter, a) and adapter_truth(adapter, a) not in truth_before for a in action_ids)
            calibration.append({"p_new": p_new, "new": new, "truth_new": truth_new})
            pending = None
        if used >= budget:
            stop = "budget"
            break
        view = AgentView.model_construct(records=records, acg=acg if selector.uses_acg else None, live_obs=live,
                                         remaining=budget - used, used=used, isolation=adapter.isolation,
                                         costs=adapter.costs)
        t = time.perf_counter()
        plan = selector.next(view)
        planner_s += time.perf_counter() - t
        if plan is None:
            break
        decision = selector.decisions()[-1] if selector.decisions() else {}
        result = adapter.run(plan, budget - used, gate, records)
        prior_len = len(records)
        records.extend(result.records)
        used_at.extend(used + x for x in result.record_actions)
        gate.observe(records)
        used += result.actions
        live = result.live_obs
        refused.extend(result.refused)
        purpose.update(result.purpose_actions)
        plans[plan.kind] += 1
        t = time.perf_counter()
        selector.update(plan, result, AgentView.model_construct(records=records[:prior_len], acg=acg, live_obs=live,
                                                                remaining=budget - used, used=used,
                                                                isolation=adapter.isolation, costs=adapter.costs))
        planner_s += time.perf_counter() - t
        if "p_new" in decision and acg is not None:
            truth_before = {adapter_truth(adapter, a) for c in acg.capabilities for a in c.action_ids} - {None}
            pending = ({c.id for c in acg.capabilities}, decision["p_new"], result.action_ids, truth_before)
        stalled = stalled + 1 if result.actions == 0 else 0
        if stalled >= 200:
            stop = "stalled"
            break
    oracle = adapter.oracle()
    curve = []
    for b in range(CHECKPOINT, budget + 1, CHECKPOINT):
        prefix = [r for r, u in zip(records, used_at) if u <= b]
        curve.append(score(oracle, prefix)["recall"] if b < used else None)
    final = score(oracle, records)
    curve = [final["recall"] if v is None else v for v in curve]
    gated_curve = {}
    for b in conf.get("budgets", [budget]):
        if b <= budget:
            prefix = [r for r, u in zip(records, used_at) if u <= b]
            gated_curve[b] = score(oracle, prefix)["gated_recall"]
    decisions = selector.decisions()
    out = {
        "policy": policy, "scenario": scenario, "seed": seed, "budget": budget, "arch": spec.arch,
        "label_mode": label_mode, "used": used, "stop": stop, "plans": dict(plans),
        "decision_hash": hashlib.sha256(json.dumps(decisions, sort_keys=True, default=str).encode()).hexdigest()[:16],
        "decisions": len(decisions), "curve": curve, "auc": sum(curve) / len(curve) if curve else 0.0,
        "final": final, "gated_at": gated_curve, "unsafe_attempts": len(refused),
        "refusals": dict(Counter(refused)), "restoration_actions": purpose.get("restore", 0),
        "purpose_actions": dict(purpose), "planner_ms_per_decision": 1000 * planner_s / max(1, len(decisions)),
        "materialize_ms_per_decision": 1000 * materialize_s / max(1, len(decisions)),
        "instances": instance_waste(oracle), "calibration": calibration, "spec": spec.summary(),
    }
    if keep:
        out["decision_log"] = decisions
        out["records"] = records
    return out


def adapter_truth(adapter: SimAdapter, action_id: str) -> str | None:
    return adapter.oracle().actions.get(action_id)


def _job(args: tuple) -> dict[str, Any]:
    policy, scenario, seed, budget, label_mode = args
    try:
        return run(policy, scenario, seed, budget, label_mode=label_mode)
    except Exception as exc:  # recorded, never hidden
        return {"policy": policy, "scenario": scenario, "seed": seed, "budget": budget, "error": repr(exc)}


def run_many(jobs: list[tuple], workers: int = 8) -> list[dict[str, Any]]:
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_job, jobs, chunksize=1))


# ------------------------------------------------------------------------------ T2 tests
def sign_test(diffs: list[float]) -> tuple[int, int, float]:
    wins, losses = sum(d > 0 for d in diffs), sum(d < 0 for d in diffs)
    n = wins + losses
    p = sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n if n else 1.0
    return wins, losses, p


def by(runs: list[dict], policy: str, scenario: str, budget: int | None = None) -> dict[int, dict]:
    return {r["seed"]: r for r in runs if r["policy"] == policy and r["scenario"] == scenario and "error" not in r
            and (budget is None or r["budget"] == budget) and not r.get("label_mode")}


def t2a(runs: list[dict]) -> dict[str, Any]:
    c = T2["T2a"]
    samples = [s for r in by(runs, c["policy"], c["scenario"]).values() for s in r["calibration"]]
    bins = []
    for i in range(int(1 / c["bin_width"])):
        lo, hi = i * c["bin_width"], (i + 1) * c["bin_width"]
        xs = [s for s in samples if lo <= s["p_new"] < hi or (i == int(1 / c["bin_width"]) - 1 and s["p_new"] == 1)]
        if not xs:
            continue
        pred = sum(s["p_new"] for s in xs) / len(xs)
        emp = sum(s["new"] for s in xs) / len(xs)
        truth = sum(s["truth_new"] for s in xs) / len(xs)
        bins.append({"bin": [round(lo, 2), round(hi, 2)], "n": len(xs), "mean_predicted": round(pred, 4),
                     "empirical": round(emp, 4), "empirical_truth_new": round(truth, 4),
                     "populated": len(xs) >= c["min_bin"],
                     "within_tolerance": abs(pred - emp) <= c["tolerance"] if len(xs) >= c["min_bin"] else None})
    populated = [b for b in bins if b["populated"]]
    passed = bool(populated) and all(b["within_tolerance"] for b in populated)
    return {"pass": passed, "samples": len(samples), "bins": bins, "threshold": "±0.10 in every bin with >= 30 samples"}


def t2b(runs: list[dict]) -> dict[str, Any]:
    c = T2["T2b"]
    out = {}
    for policy in ("acg_full", "acg_uniform", "acg_no_unlock", "legacy_frontier", "bfs"):
        rs = by(runs, policy, c["scenario"])
        if rs:
            vals = [r["instances"]["non_split_instances"] for r in rs.values()]
            out[policy] = {"max": max(vals), "mean": sum(vals) / len(vals),
                           "seeds_within_bound": sum(v <= c["max_sampled_instances"] for v in vals), "seeds": len(vals)}
    full = out.get(c["policy"], {})
    return {"pass": bool(full) and full["seeds_within_bound"] == full["seeds"], "by_policy": out,
            "threshold": "<= 3 non-split sampled instances in every seed"}


def t2c(runs: list[dict]) -> dict[str, Any]:
    c = T2["T2c"]
    rows, passed = {}, True
    for b in c["budgets"]:
        full, legacy = by(runs, c["policy"], c["scenario"], b), by(runs, c["comparator"], c["scenario"], b)
        seeds = sorted(set(full) & set(legacy))
        ok = [full[s]["gated_at"][b] >= legacy[s]["gated_at"][b] for s in seeds]
        frac = sum(ok) / len(ok) if ok else 0.0
        rows[b] = {"fraction_of_seeds_full_ge_legacy": round(frac, 4), "seeds": len(seeds),
                   "mean_gated_full": _mean(full[s]["gated_at"][b] for s in seeds),
                   "mean_gated_legacy": _mean(legacy[s]["gated_at"][b] for s in seeds),
                   "other_policies": {p: _mean(r["gated_at"][b] for r in by(runs, p, c["scenario"], b).values())
                                      for p in ("bfs", "acg_uniform", "acg_no_unlock")},
                   "pass": frac >= c["min_seed_fraction"]}
        passed &= frac >= c["min_seed_fraction"]
    return {"pass": passed, "by_budget": rows, "threshold": ">= legacy gated recall in >= 80% of seeds at each budget"}


def t2d(runs: list[dict]) -> dict[str, Any]:
    c = T2["T2d"]
    full, bfs = by(runs, c["policy"], c["scenario"]), by(runs, c["comparator"], c["scenario"])
    seeds = sorted(set(full) & set(bfs))
    a_full, a_bfs = _mean(full[s]["auc"] for s in seeds), _mean(bfs[s]["auc"] for s in seeds)
    ratio = a_full / a_bfs if a_bfs else 0.0
    others = {p: _mean(r["auc"] for r in by(runs, p, c["scenario"]).values())
              for p in ("legacy_frontier", "acg_uniform", "acg_no_unlock")}
    return {"pass": ratio >= c["min_ratio"], "auc_full": a_full, "auc_bfs": a_bfs, "ratio": round(ratio, 4),
            "other_policies_auc": others, "threshold": "AUC_full >= 0.95 x AUC_bfs"}


def t2e(runs: list[dict], repeats: list[dict]) -> dict[str, Any]:
    c = T2["T2e"]
    first = by(runs, c["policy"], c["scenario"])
    second = {r["seed"]: r for r in repeats if "error" not in r}
    same = [first[s]["decision_hash"] == second[s]["decision_hash"] for s in sorted(set(first) & set(second))]
    return {"pass": bool(same) and all(same), "seeds": len(same), "identical": sum(same)}


def t2f(runs: list[dict]) -> dict[str, Any]:
    c = T2["T2f"]
    out, passed = {}, True
    for scenario in c["scenarios"]:
        budgets = SCENARIOS[scenario]["budgets"]

        def metric(policy: str) -> dict[int, float]:
            if scenario == "instances":
                return {s: r["auc"] for s, r in by(runs, policy, scenario).items()}
            per = [by(runs, policy, scenario, b) for b in budgets]
            seeds = set.intersection(*(set(p) for p in per)) if per else set()
            return {s: _mean(p[s]["gated_at"][b] for p, b in zip(per, budgets)) for s in seeds}
        full, uniform = metric(c["policy"]), metric(c["comparator"])
        seeds = sorted(set(full) & set(uniform))
        diffs = [full[s] - uniform[s] for s in seeds]
        wins, losses, p = sign_test(diffs)
        ok = bool(diffs) and _mean(diffs) > 0 and p < c["alpha"]
        nounlock = metric("acg_no_unlock")
        out[scenario] = {"mean_full": _mean(full[s] for s in seeds), "mean_uniform": _mean(uniform[s] for s in seeds),
                         "mean_no_unlock": _mean(nounlock.values()), "mean_difference": _mean(diffs),
                         "wins": wins, "losses": losses, "ties": len(diffs) - wins - losses, "sign_test_p": p,
                         "pass": ok}
        passed &= ok
    return {"pass": passed, "by_scenario": out}


def _mean(xs) -> float:
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default=str(RESULTS / "t2_runs.json"))
    args = ap.parse_args()
    jobs = []
    for scenario, conf in SCENARIOS.items():
        for policy in ["bfs", "legacy_frontier", "acg_uniform", "acg_no_unlock", "acg_full"]:
            for b in conf["budgets"]:
                jobs.extend((policy, scenario, s, b, None) for s in SEEDS)
    for scenario, conf in STRESS.items():
        for policy in ["bfs", "legacy_frontier", "acg_uniform", "acg_no_unlock", "acg_full"]:
            jobs.extend((policy, scenario, s, conf["budget"], None) for s in STRESS_SEEDS)
    t = time.time()
    runs = run_many(jobs, args.workers)
    repeats = run_many([("acg_full", "mixed", s, 150, None) for s in SEEDS], args.workers)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    slim = [{k: v for k, v in r.items() if k not in {"calibration"}} for r in runs]
    Path(args.out).write_text(json.dumps({"runs": slim, "repeat_hashes": {r["seed"]: r.get("decision_hash")
                                                                         for r in repeats}}, indent=0))
    tests = {"T2a": t2a(runs), "T2b": t2b(runs), "T2c": t2c(runs), "T2d": t2d(runs), "T2e": t2e(runs, repeats),
             "T2f": t2f(runs)}
    print(json.dumps({k: v["pass"] for k, v in tests.items()}), f"{time.time() - t:.0f}s")
    (RESULTS / "t2_tests.json").write_text(json.dumps(tests, indent=1, default=str))


if __name__ == "__main__":
    main()
