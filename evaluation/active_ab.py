"""Phase 3: preregistered real-browser A/B of the legacy frontier vs the Capability Tour Scheduler.

Frozen before the executor adapter exists (see evaluation/ACTIVE_AB_PREREGISTRATION.md).
Arms run through the same Explorer, the same evidence capture (`acg_evidence`),
the same budgets and the same independent scorer. Scoring uses legacy's own
artifact format for both arms: `import_run_artifact` + the per-record action
ledger, then `score_capabilities` against the frozen ground-truth annotations.

Run: .venv/bin/python -m evaluation.active_ab
"""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any

from agent1.model.importer import import_run_artifact
from agent1.model.materialize import materialize
from agent1.model.schema import STATUS_RANK, Status
from evaluation.ground_truth import load_ground_truth
from evaluation.score_acg import observation_paths, score_capabilities, score_identity

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "results"

# ------------------------------------------------------------------ preregistration
FROZEN = {"legacy": "f6744ba frontier as configured per environment below (agent1/explorer.py at a43f69a, "
                    "exploration_policy='legacy')",
          "tour": "tour_v2 in agent1/planner/tours.py at a43f69a (fails preregistered T2V V3; see t2v_tests.json)"}
ENVIRONMENTS = ["stateful_lab", "js_heavy_lab", "replay_lab"]
DIAGNOSTIC = "phase2_lab"
TRIALS = 3
TOUR_SEEDS = [101, 102, 103]            # legacy has no seed parameter: its trials differ only by run timing
CHECKPOINT = 5                          # browser actions between curve points
WALL_CHECKPOINT = 2.0                   # seconds between wall-time curve points
LIVE_CAP_SECONDS = 25 * 60              # cumulative live evaluation cap (whole milestone)
STATEFUL = dict(policy="multidimensional", exploration_mode="persistent", max_seconds=35, max_transitions=30,
                max_browser_actions=100, settle_ms=60, action_timeout_ms=1500, allow_post_forms=True,
                replay_policy="structure", state_aware_exploration=True)
PHASE2 = dict(policy="multidimensional", exploration_mode="persistent", max_seconds=150, max_transitions=60,
              max_browser_actions=150, settle_ms=80, action_timeout_ms=1500, allow_post_forms=False,
              replay_policy="structure", state_aware_exploration=True, max_total_http_requests=600)
DECISION = {
    "success": "mean AUC(tour) > mean AUC(legacy) in >= 2 of 3 environments and not lower by more than 0.02 in "
               "the third; AND tour safety violations = 0 and <= legacy on every safety measure; AND tour false "
               "capability merges and false record merges <= legacy (summed over trials); AND 0 unsupported "
               "functional claims",
    "replace": "success",
    "experimental": "safety holds and tour wins >= 1 environment but success fails (keep both policies)",
    "redesign": "tour loses all 3 environments, or any tour safety violation",
    "stop_conditions": ["any tour-arm destructive-endpoint hit or repeated write without isolation: stop that "
                        "environment's tour trials", "cumulative live time >= 25 minutes",
                        "deterministic executor tests failing: no A/B"],
}


# ------------------------------------------------------------------ environments
def start(env: str):
    """Returns (server, url, request_log_fn, state_fn)."""
    if env == "stateful_lab":
        from development_apps.stateful_lab import start_stateful_lab
        server, url, _, log = start_stateful_lab(Path(tempfile.mkdtemp()) / "lab.sqlite")
        return server, url, lambda: [(m, p) for m, p in log], lambda: {}
    if env == "js_heavy_lab":
        from development_apps.js_heavy_lab import STATE, start_js_heavy_lab
        server, _, url = start_js_heavy_lab()
        return server, url, lambda: [tuple(k.split(" ", 1)) for k, n in STATE.snapshot().items() for _ in range(n)], \
            lambda: {}
    if env == "replay_lab":
        from development_apps.replay_lab import STATE, start_replay_lab
        server, _, url = start_replay_lab()
        return server, url, lambda: [(e["method"], e["path"]) for e in STATE.log], lambda: {}
    from development_apps.phase2_lab import start_phase2_lab
    server, url, log, state = start_phase2_lab()
    return server, url, lambda: [x for x in log if x[0] != "WS"], lambda: dict(state)


def config(env: str) -> dict:
    if env == "stateful_lab":
        return dict(STATEFUL)
    if env == DIAGNOSTIC:
        return dict(PHASE2)
    from evaluation.datasets import archive_paths
    data = json.loads([p for p in archive_paths(env) if p.exists()][0].read_text())
    cfg = dict((data.get("artifact") or data)["config"])
    for key in ("start_url", "output_dir", "run_id", "resume_from", "acg_evidence", "shadow_tours",
                "exploration_policy", "tour_seed", "action_ledger"):
        cfg.pop(key, None)
    return cfg


# ------------------------------------------------------------------ scoring
def _gt(env: str):
    path = ROOT / "evaluation" / "annotations" / f"{env}.json"
    return load_ground_truth(path) if path.exists() else None


def curve(env: str, artifact: dict, ledger: dict[str, list], budget: int, max_seconds: float) -> dict[str, Any]:
    """Recall at every CHECKPOINT browser actions and every WALL_CHECKPOINT seconds, from evidence available then."""
    gt = _gt(env)
    records = import_run_artifact(artifact, "run.json", env)
    stamp = {}
    for collection, prefix in (("observations", "ev:observations:"), ("replay_observations", "ev:replay_observations:"),
                               ("transitions", "ev:transitions:"), ("replays", "ev:replays:")):
        for item in artifact.get(collection) or []:
            stamp[prefix + item["id"]] = ledger.get(item["id"], [10**9, 10**9])
    out: dict[str, Any] = {"actions": [], "seconds": []}
    if gt is None:
        return out
    for axis, step, limit, index in (("actions", CHECKPOINT, budget, 0), ("seconds", WALL_CHECKPOINT, max_seconds, 1)):
        x = step
        while x <= limit + 1e-9:
            prefix = [r for r in records if r.kind == "capture_manifest" or stamp.get(r.id, [0, 0])[index] <= x]
            score = score_capabilities(gt, materialize(prefix).model_dump(mode="json"), prefix)
            out[axis].append(score["m1a_recall"]["value"] or 0.0)
            x += step
    return out


def safety(env: str, requests: list[tuple[str, str]], records, export) -> dict[str, Any]:
    gt = _gt(env)
    from agent1.model.routes import path_route
    writes, destructive = {}, set()
    if gt is not None:
        for cap in gt.capabilities:
            for op in cap.operations:
                if cap.effect_risk == "destructive":
                    destructive.add((op.method, op.route))
                elif cap.effect_risk == "server_write":
                    writes[(op.method, op.route)] = 0
    hits_destructive = 0
    for method, path in requests:
        key = (method, path_route(path))
        if key in destructive:
            hits_destructive += 1
        if key in writes:
            writes[key] += 1
    by_id = {r.id: r for r in records}
    unsupported = 0
    for cap in export.capabilities:
        if cap.status == Status.VERIFIED:
            kinds = {by_id[e].verification_kind for e in (cap.behavioral_class.evidence_ids if cap.behavioral_class else [])
                     if e in by_id and by_id[e].kind == "replay"}
            unsupported += not (kinds & {"paired_search", "cross_view"})
    return {"destructive_endpoint_hits": hits_destructive,
            "repeated_write_endpoint_hits": sum(max(0, n - 1) for n in writes.values()),
            "write_endpoint_hits": dict((f"{m} {r}", n) for (m, r), n in sorted(writes.items())),
            "unsupported_functional_claims": unsupported}


def summarize(env: str, arm: str, trial: int, explorer, artifact, requests, state, setup_s: float, wall_s: float):
    data = artifact.model_dump(mode="json")
    cfg = config(env)
    budget = cfg.get("max_browser_actions", 80)
    ledger = getattr(explorer, "action_ledger", {})
    c = curve(env, data, ledger, budget, cfg.get("max_seconds", 60))
    records = import_run_artifact(data, "run.json", env)
    export = materialize(records)
    dump = export.model_dump(mode="json")
    gt = _gt(env)
    caps = score_capabilities(gt, dump, records) if gt else {}
    ident = score_identity(gt, dump, observation_paths(records)) if gt else {}
    reproduced = sum(1 for cap in export.capabilities if STATUS_RANK.get(cap.status, -1) >= STATUS_RANK[Status.REPRODUCED])
    executed = sum(1 for t in artifact.transitions) + len(artifact.replays)
    return {
        "env": env, "arm": arm, "trial": trial, "seed": TOUR_SEEDS[trial] if arm == "tour" else None,
        "auc_actions": round(sum(c["actions"]) / len(c["actions"]), 4) if c["actions"] else None,
        "auc_seconds": round(sum(c["seconds"]) / len(c["seconds"]), 4) if c["seconds"] else None,
        "curve_actions": c["actions"], "curve_seconds": c["seconds"],
        "final_recall": (caps.get("m1a_recall") or {}).get("value"),
        "final_precision": (caps.get("m1a_precision") or {}).get("value"),
        "false_capability_merges": len((caps.get("capability_merges") or {}).get("incorrect_merges") or []),
        "false_record_merges": len(ident.get("incorrect_entity_merges") or []),
        "record_instances": ident.get("entity_instances"), "true_instances_observed": ident.get("true_instances_observed"),
        "reproduced_capabilities": reproduced,
        "browser_actions": artifact.metrics.browser_actions, "transitions": len(artifact.transitions),
        "replays": len(artifact.replays),
        "restoration_share": round(1 - executed / max(1, artifact.metrics.browser_actions), 4),
        "setup_seconds": round(setup_s, 2), "exploration_seconds": round(wall_s - setup_s, 2),
        "http_blocked_out_of_scope": getattr(explorer.http_budget, "blocked", None) if explorer.http_budget else None,
        "redirect_scope_violations": getattr(explorer.http_budget, "redirect_scope_violations", None)
        if explorer.http_budget else None,
        "safety": safety(env, requests, records, export),
        "server_state": state,
        "tour": getattr(explorer, "tour_summary", None),
    }


def run_one(env: str, arm: str, trial: int, out: Path) -> dict[str, Any]:
    from agent1.explorer import Explorer
    from agent1.schema import RunConfig
    server, url, requests, state = start(env)
    try:
        t0 = time.monotonic()
        cfg = config(env)
        extra = {"acg_evidence": True, "action_ledger": True}
        if arm == "tour":
            extra.update(exploration_policy="tours", tour_seed=TOUR_SEEDS[trial])
        explorer = Explorer(RunConfig(start_url=url, output_dir=out, **cfg, **extra), ROOT)
        artifact = explorer.run()
        wall = time.monotonic() - t0
        first = artifact.observations[0].recorded_at if artifact.observations else artifact.started_at
        from datetime import datetime
        setup = (datetime.fromisoformat(first.replace("Z", "+00:00")) -
                 datetime.fromisoformat(artifact.started_at.replace("Z", "+00:00"))).total_seconds()
        return summarize(env, arm, trial, explorer, artifact, requests(), state(), setup, wall)
    finally:
        server.shutdown()


def decide(rows: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {"per_environment": {}}
    wins = losses_big = 0
    for env in ENVIRONMENTS:
        leg = [r for r in rows if r["env"] == env and r["arm"] == "legacy"]
        tour = [r for r in rows if r["env"] == env and r["arm"] == "tour"]
        if not leg or not tour:
            continue
        mean = lambda rs, k: round(sum(r[k] or 0 for r in rs) / len(rs), 4)
        d = mean(tour, "auc_actions") - mean(leg, "auc_actions")
        wins += d > 0
        losses_big += d < -0.02
        out["per_environment"][env] = {"auc_legacy": mean(leg, "auc_actions"), "auc_tour": mean(tour, "auc_actions"),
                                       "difference": round(d, 4),
                                       "auc_seconds_legacy": mean(leg, "auc_seconds"),
                                       "auc_seconds_tour": mean(tour, "auc_seconds"),
                                       "paired_trial_differences": [round((t["auc_actions"] or 0) - (l["auc_actions"] or 0), 4)
                                                                    for l, t in zip(leg, tour)]}
    tours = [r for r in rows if r["arm"] == "tour" and r["env"] in ENVIRONMENTS]
    legs = [r for r in rows if r["arm"] == "legacy" and r["env"] in ENVIRONMENTS]
    s = lambda rs, k: sum(r["safety"][k] for r in rs)
    violations = s(tours, "destructive_endpoint_hits") + s(tours, "unsupported_functional_claims")
    safety_ok = violations == 0 and all(s(tours, k) <= s(legs, k) for k in
                                        ("destructive_endpoint_hits", "repeated_write_endpoint_hits",
                                         "unsupported_functional_claims"))
    merges_ok = sum(r["false_capability_merges"] for r in tours) <= sum(r["false_capability_merges"] for r in legs) \
        and sum(r["false_record_merges"] for r in tours) <= sum(r["false_record_merges"] for r in legs)
    success = wins >= 2 and losses_big == 0 and safety_ok and merges_ok
    out.update({"wins": wins, "big_losses": losses_big, "safety_ok": safety_ok, "merges_ok": merges_ok,
                "success": success,
                "verdict": "replace" if success else ("redesign" if wins == 0 or not safety_ok else "experimental")})
    return out


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    base = ROOT / "agent1" / "experiments" / f"active_ab_{time.strftime('%Y%m%d')}"
    rows, used, stopped = [], 0.0, {}
    for env in ENVIRONMENTS + [DIAGNOSTIC]:
        for trial in range(TRIALS):
            for arm in ("legacy", "tour"):
                if arm == "tour" and env in stopped:
                    continue
                if used >= LIVE_CAP_SECONDS:
                    stopped["_cap"] = "cumulative live time cap reached"
                    break
                t = time.monotonic()
                row = run_one(env, arm, trial, base / env / f"{arm}_{trial}")
                used += time.monotonic() - t
                rows.append(row)
                print(env, arm, trial, row["auc_actions"], row["final_recall"], row["safety"]["destructive_endpoint_hits"],
                      f"{used:.0f}s", flush=True)
                if arm == "tour" and (row["safety"]["destructive_endpoint_hits"] or
                                      row["safety"]["unsupported_functional_claims"]):
                    stopped[env] = "tour safety violation"
    result = {"frozen": FROZEN, "decision_rule": DECISION, "rows": rows, "stopped": stopped,
              "live_seconds": round(used, 1), "decision": decide(rows)}
    (RESULTS / "active_ab.json").write_text(json.dumps(result, indent=1, default=str))
    print(json.dumps(result["decision"], indent=1))


if __name__ == "__main__":
    main()
