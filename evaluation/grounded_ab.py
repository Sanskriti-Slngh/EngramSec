"""Preregistered small real-browser comparison: legacy vs post-hoc tour (control) vs execution-grounded tour.

Frozen with the grounded execution interface and its contract tests, before any
performance measurement (see evaluation/GROUNDED_AB_PREREGISTRATION.md). Reuses
the Phase 3 harness (`evaluation.active_ab`): same environments, configurations,
evidence capture, action ledger and independent evaluator.

Run: .venv/bin/python -m evaluation.grounded_ab
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from evaluation import active_ab as ab

RESULTS = ab.RESULTS
ARMS = ["legacy", "tour", "grounded"]          # tour = post-hoc corrected tour_v2 (control)
SEEDS = [301, 302, 303]                        # fresh; shared by both tour arms within a pair
ENVIRONMENTS = ab.ENVIRONMENTS                 # scored with ground truth
DIAGNOSTIC = ab.DIAGNOSTIC                     # prerequisite fixture (chain completion only)
LIVE_CAP_SECONDS = 15 * 60                     # remaining share of the 20-minute live limit for this milestone
RESTORATION_FAILURES = ("control_not_found", "record_identity_mismatch", "arrived_at_wrong_state",
                        "restoration_mismatch", "live_state_stale", "history_unavailable", "goto_unresolved")
CRITERIA = {
    "C1_ledger_integrity": "0 ledger integrity problems in every grounded run",
    "C2_safety": "grounded: 0 destructive hits, 0 unsupported claims, repeated write hits <= control in every env",
    "C3_repeated_blocked": "grounded: 0 re-proposals of a refused question under unchanged conditions",
    "C4_accuracy": "grounded mean precision >= control mean precision - 0.02 and false capability/record merges "
                   "<= control, per environment",
    "C5_restoration": "pooled over the 3 scored environments: restoration failures per restoration attempt AND "
                      "restoration actions per discovered capability each >= 25% lower than control",
    "C6_discovery": "mean discovery AUC(grounded) > mean AUC(control) on js_heavy_lab and replay_lab",
    "success": "C1-C6 all hold; legacy remains production regardless of this result",
    "gate_after_pair_0": "pairs 1-2 run only if pair 0 shows C1 and C2 hold and no executed record/session identity "
                         "error; otherwise stop and report",
}


def _config_arm(env: str, arm: str, trial: int) -> dict[str, Any]:
    extra: dict[str, Any] = {"acg_evidence": True, "action_ledger": True}
    if arm != "legacy":
        extra.update(exploration_policy="tours" if arm == "tour" else "tours_grounded", tour_seed=SEEDS[trial])
    return extra


def run_one(env: str, arm: str, trial: int, out: Path) -> dict[str, Any]:
    from datetime import datetime

    from agent1.explorer import Explorer
    from agent1.schema import RunConfig
    server, url, requests, state = ab.start(env)
    try:
        t0 = time.monotonic()
        explorer = Explorer(RunConfig(start_url=url, output_dir=out, **ab.config(env), **_config_arm(env, arm, trial)),
                            ab.ROOT)
        artifact = explorer.run()
        wall = time.monotonic() - t0
        first = artifact.observations[0].recorded_at if artifact.observations else artifact.started_at
        setup = (datetime.fromisoformat(first.replace("Z", "+00:00")) -
                 datetime.fromisoformat(artifact.started_at.replace("Z", "+00:00"))).total_seconds()
        row = ab.summarize(env, arm, trial, explorer, artifact, requests(), state(), setup, wall)
    finally:
        server.shutdown()
    row["seed"] = SEEDS[trial] if arm != "legacy" else None
    row.update(restoration_metrics(out, row))
    return row


def restoration_metrics(out: Path, row: dict) -> dict[str, Any]:
    decisions = out / "tour_decisions.jsonl"
    if not decisions.exists():
        return {}
    rows = [json.loads(x) for x in decisions.read_text().splitlines() if x.strip()]
    attempted = failed = repeats_any = 0
    refused_before: set[str] = set()
    for r in rows:
        p, e = r.get("proposal") or {}, r.get("executed") or {}
        q = p.get("question")
        if q in refused_before:
            repeats_any += 1
        if (p.get("restoration") or {}).get("kind") not in (None, "stay", "none"):
            attempted += 1
            failed += any((e.get("abort") or "").startswith(f) for f in RESTORATION_FAILURES)
        if e.get("refused"):
            refused_before.add(q)
    tour = row.get("tour") or {}
    matched = round((row.get("final_recall") or 0) * 1000)
    restoration_actions = round(row["restoration_share"] * row["browser_actions"])
    return {"restoration_attempts": attempted, "restoration_failures": failed,
            "restoration_actions": restoration_actions,
            "reproposals_after_refusal_any_condition": repeats_any,
            "repeated_blocked_same_condition": tour.get("repeated_blocked_proposals"),
            "ledger_integrity": tour.get("ledger_integrity"), "grounded_restorations": tour.get("restorations"),
            "verification_actions": tour.get("verification_actions",
                                             (tour.get("scheduler") or {}).get("verification_actions")),
            "verification_wasted_actions": (tour.get("scheduler") or {}).get("verification_wasted_actions"),
            "step_outcomes": tour.get("step_outcomes"), "_recall_x1000": matched}


def evaluate(rows: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    g = [r for r in rows if r["arm"] == "grounded"]
    t = [r for r in rows if r["arm"] == "tour"]
    out["C1_ledger_integrity"] = {"problems": sum(len(r.get("ledger_integrity") or []) for r in g),
                                  "pass": all(not r.get("ledger_integrity") for r in g)}
    c2 = True
    for env in ENVIRONMENTS + [DIAGNOSTIC]:
        ge, te = [r for r in g if r["env"] == env], [r for r in t if r["env"] == env]
        s = lambda rs, k: sum(r["safety"][k] for r in rs)
        c2 &= s(ge, "destructive_endpoint_hits") == 0 and s(ge, "unsupported_functional_claims") == 0 \
            and s(ge, "repeated_write_endpoint_hits") <= s(te, "repeated_write_endpoint_hits")
    out["C2_safety"] = {"pass": c2}
    rep = sum(r.get("repeated_blocked_same_condition") or 0 for r in g)
    out["C3_repeated_blocked"] = {"grounded_same_condition": rep,
                                  "grounded_any_condition": sum(r.get("reproposals_after_refusal_any_condition") or 0 for r in g),
                                  "control_any_condition": sum(r.get("reproposals_after_refusal_any_condition") or 0 for r in t),
                                  "pass": rep == 0}
    mean = lambda rs, k: round(sum(r[k] or 0 for r in rs) / len(rs), 4) if rs else None
    c4, per = True, {}
    for env in ENVIRONMENTS:
        ge, te, le = ([r for r in rows if r["env"] == env and r["arm"] == a] for a in ("grounded", "tour", "legacy"))
        if not ge or not te:
            continue
        per[env] = {"auc": {a: mean(rs, "auc_actions") for a, rs in (("legacy", le), ("tour", te), ("grounded", ge))},
                    "auc_seconds": {a: mean(rs, "auc_seconds") for a, rs in (("legacy", le), ("tour", te), ("grounded", ge))},
                    "final_recall": {a: mean(rs, "final_recall") for a, rs in (("legacy", le), ("tour", te), ("grounded", ge))},
                    "precision": {a: mean(rs, "final_precision") for a, rs in (("legacy", le), ("tour", te), ("grounded", ge))},
                    "trials": len(ge)}
        c4 &= (mean(ge, "final_precision") or 0) >= (mean(te, "final_precision") or 0) - 0.02 \
            and sum(r["false_capability_merges"] for r in ge) <= sum(r["false_capability_merges"] for r in te) \
            and sum(r["false_record_merges"] for r in ge) <= sum(r["false_record_merges"] for r in te)
    out["per_environment"] = per
    out["C4_accuracy"] = {"pass": c4}
    scored = lambda rs: [r for r in rs if r["env"] in ENVIRONMENTS]
    def rates(rs):
        att = sum(r.get("restoration_attempts") or 0 for r in rs)
        fail = sum(r.get("restoration_failures") or 0 for r in rs)
        acts = sum(r.get("restoration_actions") or 0 for r in rs)
        caps = sum((r.get("final_recall") or 0) for r in rs)
        return {"failure_rate": round(fail / att, 4) if att else 0.0, "attempts": att, "failures": fail,
                "restoration_actions_per_recall_unit": round(acts / caps, 2) if caps else None}
    rg, rt = rates(scored(g)), rates(scored(t))
    c5 = rt["failure_rate"] > 0 and rg["failure_rate"] <= 0.75 * rt["failure_rate"] and \
        rg["restoration_actions_per_recall_unit"] is not None and rt["restoration_actions_per_recall_unit"] and \
        rg["restoration_actions_per_recall_unit"] <= 0.75 * rt["restoration_actions_per_recall_unit"]
    out["C5_restoration"] = {"grounded": rg, "control": rt, "pass": bool(c5)}
    c6 = all(per.get(env) and (per[env]["auc"]["grounded"] or 0) > (per[env]["auc"]["tour"] or 0)
             for env in ("js_heavy_lab", "replay_lab"))
    out["C6_discovery"] = {"pass": c6}
    chain = {a: [((r.get("server_state") or {}).get("setup_finished", 0)) for r in rows
                 if r["env"] == DIAGNOSTIC and r["arm"] == a] for a in ARMS}
    out["prerequisite_chain_completions"] = chain
    out["success"] = all(out[k]["pass"] for k in ("C1_ledger_integrity", "C2_safety", "C3_repeated_blocked",
                                                   "C4_accuracy", "C5_restoration", "C6_discovery"))
    return out


def gate(rows: list[dict]) -> tuple[bool, str]:
    g = [r for r in rows if r["arm"] == "grounded"]
    if any(r.get("ledger_integrity") for r in g):
        return False, "ledger integrity problems in pair 0"
    if any(r["safety"]["destructive_endpoint_hits"] or r["safety"]["unsupported_functional_claims"] for r in g):
        return False, "safety violation in pair 0"
    return True, "pair 0 gates hold"


def main() -> None:
    base = ab.ROOT / "agent1" / "experiments" / f"grounded_ab_{time.strftime('%Y%m%d')}"
    rows, used, notes = [], 0.0, []
    for trial in range(len(SEEDS)):
        if trial == 1:
            ok, why = gate(rows)
            notes.append(why)
            if not ok:
                break
        for env in ENVIRONMENTS + [DIAGNOSTIC]:
            for arm in ARMS:
                if used >= LIVE_CAP_SECONDS:
                    notes.append(f"live cap reached before {env}/{arm}/trial {trial}")
                    break
                t = time.monotonic()
                row = run_one(env, arm, trial, base / env / f"{arm}_{trial}")
                used += time.monotonic() - t
                rows.append(row)
                print(env, arm, trial, row["auc_actions"], row["final_recall"], row.get("restoration_failures"),
                      row.get("restoration_attempts"), f"{used:.0f}s", flush=True)
    result = {"criteria": CRITERIA, "rows": rows, "notes": notes, "live_seconds": round(used, 1),
              "evaluation": evaluate(rows)}
    (RESULTS / "grounded_ab.json").write_text(json.dumps(result, indent=1, default=str))
    print(json.dumps({k: (v["pass"] if isinstance(v, dict) and "pass" in v else v)
                      for k, v in result["evaluation"].items() if k != "per_environment"}, default=str))


if __name__ == "__main__":
    main()
