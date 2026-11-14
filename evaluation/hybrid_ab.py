"""Preregistered real-browser comparison: frozen legacy frontier vs capability-aware legacy hybrid.

Frozen with the hybrid policy and its tests before any evaluation-environment run
(see evaluation/HYBRID_AB_PREREGISTRATION.md). Reuses the Phase 3 harness
(`evaluation.active_ab`): same environments, configurations, evidence capture,
action ledger and independent evaluator. Adds ground-truth redundancy, coverage
and precision-audit metrics computed identically for both arms.

Run: .venv/bin/python -m evaluation.hybrid_ab
"""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from agent1.model.importer import import_run_artifact
from agent1.model.materialize import materialize
from evaluation import active_ab as ab
from evaluation.precision_audit import CATEGORIES, classify
from evaluation.score_acg import map_actions, route_matches, score_capabilities

RESULTS = ab.RESULTS
ARMS = ["legacy", "hybrid"]
ENVIRONMENTS = ab.ENVIRONMENTS                  # stateful_lab, js_heavy_lab, replay_lab (scored)
DIAGNOSTIC = ab.DIAGNOSTIC                      # phase2_lab: prerequisite workflow diagnostic
TRIALS = 3
SEEDS = None                                    # neither arm has a random component; trials differ by timing only
LIVE_CAP_SECONDS = 14.5 * 60                    # smoke + 3 trials; contract tests used the rest of ~15 minutes
HYPOTHESES = {
    "H1_no_loss": "per scored environment: mean final recall(hybrid) >= mean final recall(legacy) AND "
                  "mean AUC(hybrid) >= mean AUC(legacy) - 0.02",
    "H2_efficiency": "pooled over the scored environments, ground-truth-redundant exploration transitions per "
                     "observed exploration transition >= 20% lower (relative) for hybrid than legacy, AND false "
                     "capability merges and false record merges (summed over trials) <= legacy in every environment",
    "H3_prerequisite": "the prerequisite fixture's chain completes (server setup_finished >= 1) in all 3 hybrid trials",
    "H4_better": "mean AUC(hybrid) >= mean AUC(legacy) + 0.03 in >= 2 scored environments, AND mean precision(hybrid) "
                 ">= mean precision(legacy) in every scored environment, AND safety holds (0 destructive hits, "
                 "0 unsupported claims, repeated write hits <= legacy, scope violations <= legacy, every environment)",
    "gate_after_smoke": "one paired smoke trial over all 4 environments first; the 3 trials run only if every "
                        "hybrid smoke run has 0 ledger integrity problems, 0 destructive hits, 0 unsupported claims, "
                        "repeated write hits <= legacy and false record merges <= legacy",
    "default": "legacy remains the default unless H1-H4 all pass; replacement then still needs a larger comparison",
}


def _config_arm(arm: str) -> dict[str, Any]:
    extra: dict[str, Any] = {"acg_evidence": True, "action_ledger": True}
    if arm == "hybrid":
        extra["exploration_policy"] = "hybrid_capabilities"
    return extra


def extra_metrics(env: str, artifact, explorer) -> dict[str, Any]:
    """Identical for both arms; ground truth only touches the scorer."""
    gt = ab._gt(env)
    data = artifact.model_dump(mode="json")
    replay_actions = sum(r.browser_actions for r in artifact.replays)
    out: dict[str, Any] = {"replay_actions": replay_actions, "replays_validated":
                           sum(str(getattr(r.status, "value", r.status)) == "replay_validated" for r in artifact.replays)}
    hybrid = getattr(explorer, "hybrid_summary", None)
    if hybrid:
        out["hybrid"] = hybrid
    if gt is None:
        return out
    records = import_run_artifact(data, "run.json", env)
    export = materialize(records).model_dump(mode="json")
    score = score_capabilities(gt, export, records)
    mapping = map_actions(gt, records)
    seen: set[str] = set()
    redundant = observed = 0
    for t in artifact.transitions:
        if t.result_observation_id is None or t.error:
            continue
        observed += 1
        truth = mapping.get(t.id)
        if truth and not str(truth).startswith(("ambiguous", "non:")):
            redundant += truth in seen
            seen.add(truth)
    areas = {g for t in export["templates"] for g in gt.templates if route_matches(g, t["route"])}
    merges = score["capability_merges"]
    audit = classify(gt, export, score)
    out.update({
        "true_positives": score["m1a_precision"]["matched"],
        "false_positives": score["m1a_precision"]["denominator"] - score["m1a_precision"]["matched"],
        "recall_matched": score["m1a_recall"]["matched"], "recall_denominator": score["m1a_recall"]["denominator"],
        "unmatched_gt": score["unmatched_gt"],
        "gt_redundant_transitions": redundant, "observed_transitions": observed,
        "functional_areas_mapped": len(areas), "functional_areas_total": len(gt.templates),
        "capability_splits": len(merges["splits"]), "correct_capability_merges": merges["correct_merges"],
        "fp_categories": dict(Counter(r["category"] for r in audit)),
    })
    return out


def run_one(env: str, arm: str, trial: int, out: Path) -> dict[str, Any]:
    from datetime import datetime

    from agent1.explorer import Explorer
    from agent1.schema import RunConfig
    server, url, requests, state = ab.start(env)
    try:
        t0 = time.monotonic()
        explorer = Explorer(RunConfig(start_url=url, output_dir=out, **ab.config(env), **_config_arm(arm)), ab.ROOT)
        artifact = explorer.run()
        wall = time.monotonic() - t0
        first = artifact.observations[0].recorded_at if artifact.observations else artifact.started_at
        setup = (datetime.fromisoformat(first.replace("Z", "+00:00")) -
                 datetime.fromisoformat(artifact.started_at.replace("Z", "+00:00"))).total_seconds()
        row = ab.summarize(env, arm, trial, explorer, artifact, requests(), state(), setup, wall)
    finally:
        server.shutdown()
    row["seed"] = None
    row.update(extra_metrics(env, artifact, explorer))
    return row


def evaluate(rows: list[dict]) -> dict[str, Any]:
    mean = lambda rs, k: round(sum(r[k] or 0 for r in rs) / len(rs), 4) if rs else None
    pick = lambda env, arm: [r for r in rows if r["env"] == env and r["arm"] == arm and r.get("phase") == "trial"]
    per, h1, h4_wins, h4_precision, merges_ok = {}, True, 0, True, True
    for env in ENVIRONMENTS:
        le, he = pick(env, "legacy"), pick(env, "hybrid")
        if not le or not he:
            h1 = False
            continue
        d = {k: {"legacy": mean(le, k), "hybrid": mean(he, k)}
             for k in ("auc_actions", "auc_seconds", "final_recall", "final_precision", "true_positives",
                       "false_positives", "functional_areas_mapped", "gt_redundant_transitions", "observed_transitions",
                       "browser_actions", "replay_actions", "restoration_share")}
        d["auc_difference"] = round(d["auc_actions"]["hybrid"] - d["auc_actions"]["legacy"], 4)
        d["paired_auc_differences"] = [round((h["auc_actions"] or 0) - (l["auc_actions"] or 0), 4)
                                       for l, h in zip(le, he)]
        d["trials"] = len(he)
        per[env] = d
        h1 &= d["final_recall"]["hybrid"] >= d["final_recall"]["legacy"] and d["auc_difference"] >= -0.02
        h4_wins += d["auc_difference"] >= 0.03
        h4_precision &= d["final_precision"]["hybrid"] >= d["final_precision"]["legacy"]
        merges_ok &= sum(r["false_capability_merges"] for r in he) <= sum(r["false_capability_merges"] for r in le) \
            and sum(r["false_record_merges"] for r in he) <= sum(r["false_record_merges"] for r in le)
    scored = lambda arm: [r for env in ENVIRONMENTS for r in pick(env, arm)]
    rate = lambda rs: (sum(r["gt_redundant_transitions"] for r in rs) / max(1, sum(r["observed_transitions"] for r in rs)))
    rl, rh = rate(scored("legacy")), rate(scored("hybrid"))
    h2 = bool(scored("hybrid")) and rl > 0 and rh <= 0.8 * rl and merges_ok
    safety_ok = True
    for env in ENVIRONMENTS + [DIAGNOSTIC]:
        le, he = pick(env, "legacy"), pick(env, "hybrid")
        s = lambda rs, k: sum(r["safety"][k] for r in rs)
        v = lambda rs: sum((r.get("redirect_scope_violations") or 0) for r in rs)
        safety_ok &= s(he, "destructive_endpoint_hits") == 0 and s(he, "unsupported_functional_claims") == 0 \
            and s(he, "repeated_write_endpoint_hits") <= s(le, "repeated_write_endpoint_hits") and v(he) <= v(le)
    chain = {arm: [(r.get("server_state") or {}).get("setup_finished", 0) for r in pick(DIAGNOSTIC, arm)]
             for arm in ARMS}
    h3 = len(chain["hybrid"]) == TRIALS and all(x >= 1 for x in chain["hybrid"])
    return {"per_environment": per,
            "H1_no_loss": {"pass": h1},
            "H2_efficiency": {"legacy_redundant_rate": round(rl, 4), "hybrid_redundant_rate": round(rh, 4),
                              "relative_reduction": round(1 - rh / rl, 4) if rl else None, "merges_ok": merges_ok,
                              "pass": h2},
            "H3_prerequisite": {"chain_completions": chain, "pass": h3},
            "H4_better": {"environments_with_gain_ge_0.03": h4_wins, "precision_not_lower": h4_precision,
                          "safety_ok": safety_ok, "pass": h4_wins >= 2 and h4_precision and safety_ok},
            "ledger_integrity_problems": sum(len((r.get("hybrid") or {}).get("ledger_integrity") or [])
                                             for r in rows if r["arm"] == "hybrid"),
            "precision_audit": {f"{env}/{arm}": {c: sum((r.get("fp_categories") or {}).get(c, 0) for r in pick(env, arm))
                                                 for c in CATEGORIES} for env in ENVIRONMENTS for arm in ARMS}}


def gate(rows: list[dict]) -> tuple[bool, str]:
    for env in ENVIRONMENTS + [DIAGNOSTIC]:
        le = [r for r in rows if r["env"] == env and r["arm"] == "legacy"]
        he = [r for r in rows if r["env"] == env and r["arm"] == "hybrid"]
        for h in he:
            if (h.get("hybrid") or {}).get("ledger_integrity"):
                return False, f"ledger integrity problems in smoke ({env})"
            if h["safety"]["destructive_endpoint_hits"] or h["safety"]["unsupported_functional_claims"]:
                return False, f"safety violation in smoke ({env})"
        if sum(r["safety"]["repeated_write_endpoint_hits"] for r in he) > \
                sum(r["safety"]["repeated_write_endpoint_hits"] for r in le):
            return False, f"more repeated writes than legacy in smoke ({env})"
        if sum(r["false_record_merges"] for r in he) > sum(r["false_record_merges"] for r in le):
            return False, f"false record merges above legacy in smoke ({env})"
    return True, "smoke gates hold"


def main() -> None:
    base = ab.ROOT / "agent1" / "experiments" / f"hybrid_ab_{time.strftime('%Y%m%d')}"
    rows, used, notes = [], 0.0, []
    phases = [("smoke", 0)] + [("trial", t) for t in range(TRIALS)]
    for phase, trial in phases:
        if phase == "trial" and trial == 0:
            ok, why = gate(rows)
            notes.append(why)
            if not ok:
                break
        for env in ENVIRONMENTS + [DIAGNOSTIC]:
            for arm in ARMS:
                if used >= LIVE_CAP_SECONDS:
                    notes.append(f"live cap reached before {phase} {trial} {env}/{arm}")
                    break
                t = time.monotonic()
                row = run_one(env, arm, trial, base / phase / env / f"{arm}_{trial}")
                used += time.monotonic() - t
                row["phase"] = phase
                rows.append(row)
                print(phase, env, arm, trial, row["auc_actions"], row["final_recall"], row["final_precision"],
                      row.get("gt_redundant_transitions"), row.get("observed_transitions"),
                      (row.get("server_state") or {}).get("setup_finished"), f"{used:.0f}s", flush=True)
    result = {"hypotheses": HYPOTHESES, "rows": rows, "notes": notes, "live_seconds": round(used, 1),
              "evaluation": evaluate(rows)}
    (RESULTS / "hybrid_ab.json").write_text(json.dumps(result, indent=1, default=str))
    print(json.dumps({k: (v["pass"] if isinstance(v, dict) and "pass" in v else v)
                      for k, v in result["evaluation"].items() if k not in ("per_environment", "precision_audit")},
                     default=str))


if __name__ == "__main__":
    main()
