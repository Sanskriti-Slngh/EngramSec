"""Phase 1b-R (T2R): preregistered evaluation of the Capability Tour Scheduler.

Frozen before the scheduler exists. Reuses the frozen T2 simulator, scenarios,
run loop, executor, risk gate and scorer unchanged; it only
- uses fresh seeds never used to develop the Phase 1b planner,
- registers the D1–D4 diagnostic apps (evaluation/sim_diagnostics.py),
- resolves the new `tour_*` policy names, and
- wraps every selector to count actions by purpose (a pure observer).

Run: .venv/bin/python -m evaluation.t2r_eval --all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import evaluation.sim_eval as se
from evaluation import sim_diagnostics
from evaluation.appsim import build as _appsim_build
from evaluation.sim_scenarios import SCENARIOS, STRESS

RESULTS = Path(__file__).resolve().parents[1] / "evaluation" / "results"

# ------------------------------------------------------------------ preregistration
SEEDS = list(range(1000, 1050))           # never used in Phase 1b development or evaluation
STRESS_SEEDS = list(range(1000, 1020))
DIAG_SEEDS = list(range(2000, 2010))
POLICIES = ["bfs", "legacy_frontier", "acg_uniform", "acg_full", "tour_full", "tour_no_local", "tour_no_global"]
DIAG_BUDGET = 80
DIAGNOSTIC_SCENARIOS = {f"diag:{a[5:]}": {"arch": a, "kw": {}, "budget": DIAG_BUDGET}
                        for a in sim_diagnostics.DIAGNOSTICS}
VERIFICATION_KINDS = {"reproduce", "verify_effect", "test_dependency", "test_equivalence"}

T2R = {
    "R1_flat": {"scenario": "flat", "budget": 100, "policy": "tour_full", "comparator": "bfs", "min_ratio": 0.95},
    "R2_prerequisites": {"scenario": "prerequisites", "budgets": [100, 200, 400], "policy": "tour_full",
                         "comparator": "legacy_frontier", "min_seed_fraction": 0.80},
    "R3_instances": {"scenario": "instances", "budget": 150, "policy": "tour_full", "max_sampled_instances": 3},
    "R4_mixed": {"scenario": "mixed", "budget": 150, "policy": "tour_full", "auc_comparator": "legacy_frontier",
                 "alpha": 0.05, "recall_reference": "acg_uniform", "recall_margin": 0.02,
                 "rule": "AUC: mean(tour) > mean(legacy) and one-sided sign test p < 0.05; recall: mean(tour) >= "
                         "mean(acg_uniform) - 0.02 and mean(tour) > mean(legacy)"},
    "R5_determinism": {"scenario": "mixed", "budget": 150, "policy": "tour_full"},
    "R6_safety": {"policies": ["tour_full", "tour_no_local", "tour_no_global"],
                  "rule": "0 risk-gate refusals in every run of every scenario"},
    "R7_diagnostics": {
        "D1_search": "tour_full reaches VERIFIED collection_query in >= 9 of 10 seeds (budget 80)",
        "D2_snapshot": "tour_full reaches VERIFIED instance_creation in >= 9 of 10 seeds (budget 80)",
        "D3_drift": "no VERIFIED write capability in any seed; every write replay attempt aborted or blocked",
        "D4_absent": "no write capability re-executed in any seed; write verification recorded as blocked",
    },
    "H_local": "tour_full > tour_no_local on prerequisites gated recall averaged over 100/200/400 "
               "(mean difference > 0, sign test p < 0.05)",
    "H_global": "tour_full > tour_no_global on flat AUC and on mixed AUC (each: mean difference > 0, p < 0.05)",
    "success": "R1, R2, R3, R4, R5, R6 and R7 all pass",
    "if_failed": "retain the policy with the highest mean mixed AUC among those passing R3 and R6 "
                 "(ties: higher mixed recall)",
}

# ------------------------------------------------------------------ harness wiring
STRESS.update({k: v for k, v in DIAGNOSTIC_SCENARIOS.items()})      # registration only; T2 entries untouched
_orig_factory = se.policy_factory
_LAST: list[Any] = []


def _build(arch: str, seed: int, **kw):
    return sim_diagnostics.build(arch, seed, **kw) if arch.startswith("diag_") else _appsim_build(arch, seed, **kw)


class _Observed:
    """Pure observer around a selector: counts actions by purpose; never changes a decision."""

    def __init__(self, inner) -> None:
        self.inner, self.name, self.uses_acg = inner, inner.name, inner.uses_acg
        self.stats: Counter = Counter()
        self.url: dict[str, str] = {}
        self.area_before = ""

    def _area(self, obs_id: str) -> str:
        path = urlsplit(self.url.get(obs_id, "")).path.strip("/")
        return path.split("/")[0] if path else "root"

    def next(self, view):
        if not self.url:
            self.url.update({r.obs_id: r.url for r in view.records if r.kind == "observation"})
        self.area_before = self._area(view.live_obs)
        return self.inner.next(view)

    def update(self, plan, result, view):
        self.url.update({r.obs_id: r.url for r in result.records if r.kind == "observation"})
        cls = "verification" if plan.kind in VERIFICATION_KINDS else "discovery"
        restore = result.purpose_actions.get("restore", 0)
        self.stats[cls + "_actions"] += result.actions
        self.stats["restoration_actions"] += restore
        self.stats["fresh_or_snapshot_steps"] += sum(s.op in {"fresh", "snapshot"} for s in plan.steps)
        if self._area(result.live_obs) != self.area_before:
            self.stats["area_switches"] += 1
            self.stats["area_switch_restoration_actions"] += restore
        if result.abort_reason:
            self.stats["aborted_plans"] += 1
        self.inner.update(plan, result, view)

    def decisions(self):
        return self.inner.decisions()


def _factory(name: str):
    if name.startswith("tour_"):
        from agent1.planner.tours import make_tour      # implemented after this file was frozen
        inner = make_tour(name)
    else:
        inner = _orig_factory(name)

    def make(isolation, costs, budget, seed=0):
        sel = _Observed(inner(isolation, costs, budget, seed))
        _LAST[:] = [sel]
        return sel
    return make


def install() -> None:
    """Wire the T2R policies and diagnostic apps into the frozen run loop (idempotent)."""
    se.build = _build
    se.policy_factory = _factory


def chains(scenario: str, seed: int, found: set[str]) -> dict[str, int]:
    """Truth-side prerequisite-chain outcomes: started (first gated step found), completed (gated end found)."""
    conf = SCENARIOS.get(scenario) or STRESS.get(scenario)
    spec = _build(se.arch_for(scenario, seed), seed, **conf["kw"])
    out = Counter()
    for area in sorted({c.area for c in spec.caps.values() if c.cls == "gated_capability"}):
        caps = [c for c in spec.caps.values() if c.area == area and c.cls in {"step", "gated_capability"}]
        steps = [c.id for c in caps if c.cls == "step"]
        final = [c.id for c in caps if c.cls == "gated_capability"]
        out["chains"] += 1
        started = any(s in found for s in steps)
        done = any(f in found for f in final)
        out["completed"] += done
        out["abandoned"] += started and not done
    return dict(out)


def job(args: tuple) -> dict[str, Any]:
    install()
    policy, scenario, seed, budget = args
    try:
        r = se.run(policy, scenario, seed, budget, keep=True)
    except Exception as exc:
        return {"policy": policy, "scenario": scenario, "seed": seed, "budget": budget, "error": repr(exc)}
    sel = _LAST[0]
    r["actions_by_purpose"] = dict(sel.stats)
    inner = sel.inner
    if hasattr(inner, "summary"):
        r["scheduler"] = inner.summary()
    records = r.pop("records")
    r.pop("decision_log", None)
    from agent1.model.materialize import materialize
    acg = materialize(records)
    r["verified_classes"] = sorted({c.behavioral_class.name for c in acg.capabilities
                                    if c.behavioral_class and str(c.status) == "verified"})
    r["write_reexecutions"] = _write_reexecutions(records)
    if "prerequisites" in scenario or "false_prereq" in scenario or "workflow" in r["arch"]:
        r["chains"] = chains(scenario, seed, set(r["final"]["found_ids"]))
    return r


def _write_reexecutions(records) -> int:
    """Executions of a control already observed writing, counted per click (actions and replays)."""
    from agent1.planner.gate import control_key, writes
    known, url, n = set(), {}, 0
    actions = {x.action_id: x for x in records if x.kind == "action"}
    for x in records:
        if x.kind == "observation":
            url[x.obs_id] = x.url
        if x.kind not in {"action", "replay"}:
            continue
        orig = actions.get(x.action_id)
        if orig is None or orig.affordance is None:
            continue
        key = control_key(url.get(orig.source_obs), orig.affordance)
        n += key in known
        if writes(x) or writes(orig):
            known.add(key)
    return n


def jobs() -> list[tuple]:
    out = []
    for scenario, conf in SCENARIOS.items():
        for policy in POLICIES:
            for b in conf["budgets"]:
                out.extend((policy, scenario, s, b) for s in SEEDS)
    for scenario, conf in STRESS.items():
        if scenario in DIAGNOSTIC_SCENARIOS:
            continue
        for policy in POLICIES:
            out.extend((policy, scenario, s, conf["budget"]) for s in STRESS_SEEDS)
    for scenario in DIAGNOSTIC_SCENARIOS:
        for policy in POLICIES:
            out.extend((policy, scenario, s, DIAG_BUDGET) for s in DIAG_SEEDS)
    return out


# ------------------------------------------------------------------ tests
def _by(runs, policy, scenario, budget=None):
    return {r["seed"]: r for r in runs if r["policy"] == policy and r["scenario"] == scenario and "error" not in r
            and (budget is None or r["budget"] == budget)}


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else 0.0


def _sign(diffs):
    w, l = sum(d > 0 for d in diffs), sum(d < 0 for d in diffs)
    n = w + l
    return w, l, (sum(math.comb(n, k) for k in range(w, n + 1)) / 2 ** n if n else 1.0)


def _paired(a: dict, b: dict, alpha=0.05):
    seeds = sorted(set(a) & set(b))
    d = [a[s] - b[s] for s in seeds]
    w, l, p = _sign(d)
    return {"mean_a": _mean(a[s] for s in seeds), "mean_b": _mean(b[s] for s in seeds), "mean_difference": _mean(d),
            "wins": w, "losses": l, "ties": len(d) - w - l, "p": p, "pass": bool(d) and _mean(d) > 0 and p < alpha}


def evaluate(runs: list[dict], repeats: list[dict]) -> dict[str, Any]:
    t = {}
    c = T2R["R1_flat"]
    full, bfs = _by(runs, c["policy"], c["scenario"]), _by(runs, c["comparator"], c["scenario"])
    a_f, a_b = _mean(r["auc"] for r in full.values()), _mean(r["auc"] for r in bfs.values())
    t["R1_flat"] = {"auc_tour": a_f, "auc_bfs": a_b, "ratio": round(a_f / a_b, 4) if a_b else 0,
                    "pass": a_b > 0 and a_f >= c["min_ratio"] * a_b}
    c = T2R["R2_prerequisites"]
    rows, ok = {}, True
    for b in c["budgets"]:
        f, l = _by(runs, c["policy"], c["scenario"], b), _by(runs, c["comparator"], c["scenario"], b)
        seeds = sorted(set(f) & set(l))
        frac = _mean(float(f[s]["gated_at"][b] >= l[s]["gated_at"][b]) for s in seeds)
        rows[b] = {"fraction": frac, "mean_tour": _mean(f[s]["gated_at"][b] for s in seeds),
                   "mean_legacy": _mean(l[s]["gated_at"][b] for s in seeds), "pass": frac >= c["min_seed_fraction"]}
        ok &= frac >= c["min_seed_fraction"]
    t["R2_prerequisites"] = {"by_budget": rows, "pass": ok}
    c = T2R["R3_instances"]
    vals = [r["instances"]["non_split_instances"] for r in _by(runs, c["policy"], c["scenario"]).values()]
    t["R3_instances"] = {"max": max(vals) if vals else None, "seeds_within": sum(v <= 3 for v in vals),
                         "seeds": len(vals), "pass": bool(vals) and max(vals) <= c["max_sampled_instances"]}
    c = T2R["R4_mixed"]
    tour, leg, uni = (_by(runs, p, c["scenario"]) for p in (c["policy"], c["auc_comparator"], c["recall_reference"]))
    auc = _paired({s: r["auc"] for s, r in tour.items()}, {s: r["auc"] for s, r in leg.items()})
    rec_t, rec_u, rec_l = (_mean(r["final"]["recall"] for r in x.values()) for x in (tour, uni, leg))
    t["R4_mixed"] = {"auc_vs_legacy": auc, "recall_tour": rec_t, "recall_acg_uniform": rec_u, "recall_legacy": rec_l,
                     "pass": auc["pass"] and rec_t >= rec_u - c["recall_margin"] and rec_t > rec_l}
    first = _by(runs, "tour_full", "mixed")
    same = [first[r["seed"]]["decision_hash"] == r["decision_hash"] for r in repeats if r["seed"] in first]
    t["R5_determinism"] = {"identical": sum(same), "seeds": len(same), "pass": bool(same) and all(same)}
    tours = [r for r in runs if r["policy"] in T2R["R6_safety"]["policies"] and "error" not in r]
    refusals = sum(r["unsafe_attempts"] for r in tours)
    below_l3 = sum(r["write_reexecutions"] for r in tours if r["arch"] not in {"flaky", "diag_snapshot"})
    t["R6_safety"] = {"gate_refusals": refusals, "write_reexecutions_below_L3": below_l3, "runs": len(tours),
                      "pass": refusals == 0 and below_l3 == 0}
    d = {}
    for key, cls in (("diag:search", "collection_query"), ("diag:snapshot", "instance_creation")):
        rs = _by(runs, "tour_full", key)
        hits = sum(cls in r["verified_classes"] for r in rs.values())
        d[key] = {"verified_seeds": hits, "seeds": len(rs), "pass": hits >= 9}
    for key in ("diag:snapshot_drift", "diag:snapshot_absent"):
        rs = _by(runs, "tour_full", key)
        bad = sum("instance_creation" in r["verified_classes"] for r in rs.values())
        reexec = sum(r["write_reexecutions"] for r in rs.values()) if key.endswith("absent") else 0
        blocked = sum(r.get("scheduler", {}).get("verification_blocked", 0) > 0 for r in rs.values())
        d[key] = {"verified_write_seeds": bad, "write_reexecutions": reexec, "seeds_with_blocked_verification": blocked,
                  "seeds": len(rs), "pass": bad == 0 and reexec == 0 and blocked == len(rs)}
    t["R7_diagnostics"] = {"by_app": d, "pass": all(v["pass"] for v in d.values())}

    def gated_avg(policy):
        per = [_by(runs, policy, "prerequisites", b) for b in (100, 200, 400)]
        seeds = set.intersection(*(set(p) for p in per))
        return {s: _mean(p[s]["gated_at"][b] for p, b in zip(per, (100, 200, 400))) for s in seeds}
    t["H_local"] = _paired(gated_avg("tour_full"), gated_avg("tour_no_local"))
    hg = {sc: _paired({s: r["auc"] for s, r in _by(runs, "tour_full", sc).items()},
                      {s: r["auc"] for s, r in _by(runs, "tour_no_global", sc).items()}) for sc in ("flat", "mixed")}
    t["H_global"] = {"by_scenario": hg, "pass": all(v["pass"] for v in hg.values())}
    t["success"] = all(t[k]["pass"] for k in ("R1_flat", "R2_prerequisites", "R3_instances", "R4_mixed",
                                               "R5_determinism", "R6_safety", "R7_diagnostics"))
    eligible = []
    for p in POLICIES:
        rs = [r for r in runs if r["policy"] == p and "error" not in r]
        inst = [r["instances"]["non_split_instances"] for r in rs if r["scenario"] == "instances"]
        if inst and max(inst) <= 3 and sum(r["unsafe_attempts"] for r in rs) == 0:
            m = _by(runs, p, "mixed")
            eligible.append((_mean(r["auc"] for r in m.values()), _mean(r["final"]["recall"] for r in m.values()), p))
    t["retained_if_failed"] = sorted(eligible, reverse=True)[0][2] if eligible else None
    return t


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--workers", type=int, default=9)
    args = ap.parse_args()
    install()
    start = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        runs = list(pool.map(job, jobs(), chunksize=1))
        repeats = list(pool.map(job, [("tour_full", "mixed", s, 150) for s in SEEDS], chunksize=1))
    tests = evaluate(runs, repeats)
    RESULTS.mkdir(parents=True, exist_ok=True)
    slim = [{k: v for k, v in r.items() if k != "calibration"} for r in runs]
    (RESULTS / "t2r_runs.json").write_text(json.dumps({"runs": slim}, default=str))
    (RESULTS / "t2r_tests.json").write_text(json.dumps(tests, indent=1, default=str))
    print(json.dumps({k: (v["pass"] if isinstance(v, dict) and "pass" in v else v) for k, v in tests.items()}),
          f"errors={sum('error' in r for r in runs)}", f"{time.time() - start:.0f}s")


def fingerprint() -> str:
    """Hash of the frozen T2 evaluation sources this experiment depends on."""
    root = Path(__file__).resolve().parents[1]
    h = hashlib.sha256()
    for p in ("evaluation/appsim.py", "evaluation/sim_eval.py", "evaluation/sim_scenarios.py"):
        h.update((root / p).read_bytes())
    return h.hexdigest()[:16]


if __name__ == "__main__":
    main()
