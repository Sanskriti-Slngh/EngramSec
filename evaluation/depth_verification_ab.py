"""Phase 3: depth continuation vs verification budget.

Arms (identical time/action/HTTP/transition/write budgets; only the scheduler differs):
  authorized_fair    the committed baseline: write sweep, no focus, replay floor 0.10.
  focused            focused_subtree sweep (short-lived focus on unlocked subtrees), replay floor 0.10.
                     Ablation A: isolates subtree continuation (same replay protection as the baseline).
  focused_protected  focused_subtree sweep + replay floor 0.25.
                     Ablation B: isolates replay-budget protection on top of focus.

Fixtures (independent, resettable): workflow_lab (deep subtree + shallow feedback dead-end negative
control), branch_lab (two competing deep subtrees), role_lab (authenticated admin writes that unlock no
route). role_lab provisions a session OUTSIDE the agent; the agent only receives the storage-state file.

  .venv/bin/python -m evaluation.depth_verification_ab --smoke
  .venv/bin/python -m evaluation.depth_verification_ab --trials 3
  .venv/bin/python -m evaluation.depth_verification_ab child --fixture workflow_lab --arm focused --trial 0 --out DIR
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from evaluation.comprehensive_config import ROOT

BASE = ROOT / "agent1" / "experiments" / "recovery_transfer" / "depth_verification"
OUT = ROOT / "evaluation" / "results" / "depth_verification_ab.json"

MATCHED: dict[str, Any] = {
    "max_seconds": 140.0, "max_browser_actions": 600, "max_transitions": 300,
    "state_aware_exploration": True, "record_aware_graph": True, "interaction_profile": "extended",
    "typed_resource_spider": False, "allow_post_forms": True, "write_policy": "disposable",
    "max_write_requests": 60, "replay_policy": "structure", "replay_structure_attempts": 2,
    "acg_evidence": True, "record_unexecuted_frontier": True,
    # Same restoration config in every arm: a write-gated GET child can be re-reached by direct URL
    # (the project persists server-side) instead of replaying the write. Isolates the scheduler change.
    "restoration_shortcut": "direct_url",
}
ARMS = {
    "authorized_fair":   {"write_execution_policy": "authorized_fair", "write_sweep_replay_floor": 0.10},
    "focused":           {"write_execution_policy": "focused_subtree", "write_sweep_replay_floor": 0.10},
    "focused_protected": {"write_execution_policy": "focused_subtree", "write_sweep_replay_floor": 0.25},
    # generalized event-driven focus (seeds subtrees unlocked in ordinary discovery too)
    "adaptive":          {"write_execution_policy": "focused_adaptive", "write_sweep_replay_floor": 0.10},
    "adaptive_protected": {"write_execution_policy": "focused_adaptive", "write_sweep_replay_floor": 0.25},
}
FIXTURES = ("workflow_lab", "branch_lab", "gated_get_lab", "role_lab_admin")


def _gt(fixture: str):
    if fixture == "workflow_lab":
        from development_apps.workflow_lab import ALWAYS_REACHABLE, FUNCTIONAL_CAPABILITIES, WRITE_UNLOCKS
        return FUNCTIONAL_CAPABILITIES, ALWAYS_REACHABLE, WRITE_UNLOCKS
    if fixture == "branch_lab":
        from development_apps.branch_lab import ALWAYS_REACHABLE, FUNCTIONAL_CAPABILITIES, WRITE_UNLOCKS
        return FUNCTIONAL_CAPABILITIES, ALWAYS_REACHABLE, WRITE_UNLOCKS
    if fixture == "gated_get_lab":
        from development_apps.gated_get_lab import ALWAYS_REACHABLE, DEEP_GET_SUBTREE, FUNCTIONAL_CAPABILITIES
        # the deep subtree is "unlocked" by a GET to the hub, not a write; model it as the unlock set
        return FUNCTIONAL_CAPABILITIES, ALWAYS_REACHABLE, {"dashboard_view": DEEP_GET_SUBTREE}
    from development_apps.role_lab import role_inventory
    inv = role_inventory("admin")
    return inv, inv - {"order_create", "profile_update", "admin_settings_update", "admin_user_delete"}, {}


def run_child(fixture: str, arm: str, trial: int, out: Path, seconds: float | None) -> None:
    from agent1.explorer import Explorer
    from agent1.exporter import write_outputs
    from agent1.schema import RunConfig

    out.mkdir(parents=True, exist_ok=True)
    storage_state_path, context_label, auth_public = None, f"{fixture}-{arm}", None
    if fixture == "workflow_lab":
        from development_apps.workflow_lab import start_workflow_lab as start
    elif fixture == "branch_lab":
        from development_apps.branch_lab import start_branch_lab as start
    elif fixture == "gated_get_lab":
        from development_apps.gated_get_lab import start_gated_get_lab as start
    else:
        start = None
    if start is not None:
        server, url, state = start()
    else:
        from development_apps.role_lab import ACCOUNTS, start_role_lab
        server, url, state = start_role_lab()
        os.environ.update(ROLE_LAB_TEST_USERNAME="iris", ROLE_LAB_TEST_PASSWORD=ACCOUNTS["iris"]["password"],
                          ROLE_LAB_TEST_ROLE="admin")
        from evaluation.auth_provision import provision
        auth = provision("role_lab", url, attested_disposable=True)
        auth_public = auth.public()
        if auth.status != "authenticated":
            server.shutdown()
            (out / "trial.json").write_text(json.dumps({"fixture": fixture, "arm": arm, "trial": trial,
                                                        "status": "auth_unavailable", "auth": auth_public}))
            return
        storage_state_path, context_label = str(auth.storage_state_path), "admin"
        (out / "auth_prerequisite.json").write_text(json.dumps(auth.prerequisite, indent=1))
    try:
        cfg = dict(MATCHED, **ARMS[arm])
        if seconds is not None:
            cfg["max_seconds"] = seconds
        config = RunConfig(start_url=url, output_dir=out, context_label=context_label,
                           storage_state_path=storage_state_path,
                           environment_attestation=f"disposable:{fixture}-inproc-reset:{arm}", **cfg)
        t0 = time.monotonic()
        artifact = Explorer(config, ROOT).run()
        write_outputs(artifact, out)
        (out / "server_state.json").write_text(json.dumps(state.snapshot(), indent=1, default=str))
        m = artifact.metrics
        (out / "trial.json").write_text(json.dumps({
            "fixture": fixture, "arm": arm, "trial": trial, "status": "ok",
            "wall_seconds": round(time.monotonic() - t0, 2), "auth": auth_public,
            "write_policy": m.write_policy, "write_sweep": m.write_sweep,
            "unexecuted_frontier": m.unexecuted_frontier}, default=str))
    finally:
        server.shutdown()


def _families(obs):
    out = set()
    for o in obs:
        segs = [s for s in urlsplit(o.get("url", "")).path.split("/") if s]
        out.add("/" + (segs[0] if segs else ""))
    return out


def _deepest_prereq_chain(executed: set, unlocks: dict) -> int:
    """Longest completed chain: a write whose unlocked capability was executed (+ nested writes)."""
    depth = 0
    if unlocks:
        for w, children in unlocks.items():
            if w in executed and (children & executed):
                depth = max(depth, 2)                         # write -> unlocked capability
                # nested: an unlocked child that is itself a write with executed children
                for c in children & executed:
                    if c in unlocks and (unlocks[c] & executed):
                        depth = max(depth, 3)
    return depth


def collect(fixture: str, arm: str, trial: int, out: Path) -> dict[str, Any]:
    tp = out / "trial.json"
    if not tp.exists():
        return {"fixture": fixture, "arm": arm, "trial": trial, "status": "missing"}
    row = json.loads(tp.read_text())
    if row.get("status") != "ok":
        return row
    gt, always, unlocks = _gt(fixture)
    run = json.loads((out / "run.json").read_text())
    m = run["metrics"]
    server = json.loads((out / "server_state.json").read_text())
    executed = set(server.get("functions", {})) & set(gt)
    unlocked_all = set().union(*unlocks.values()) if unlocks else set()
    unlocked_exec = sorted(executed & unlocked_all)
    reproduced = sum(1 for t in run.get("transitions", []) if t.get("status") == "replay_validated")
    # replay-validated capabilities: executed capabilities whose landing route was replay-validated
    repro_routes = {urlsplit((next((o for o in run.get("observations", []) if o["id"] == t.get("result_observation_id")), {}) or {}).get("url") or "").path
                    for t in run.get("transitions", []) if t.get("status") == "replay_validated"}
    uf = row.get("unexecuted_frontier") or {}
    FAM = ("project", "report", "dashboard")
    # eligible child actions left unexplored inside an unlocked family
    leftover_in_family = sum(1 for it in uf.get("items", [])
                             if any(seg in FAM for seg in (it.get("target_path") or "").split("/")))
    wp = row.get("write_policy") or {}
    sweep = row.get("write_sweep") or {}
    exec_n = len(executed)
    return {
        "fixture": fixture, "arm": arm, "trial": trial, "status": "ok",
        "capabilities_executed": sorted(executed), "capabilities_executed_count": exec_n, "inventory": len(gt),
        "write_unlocked_executed": unlocked_exec, "write_unlocked_count": len(unlocked_exec),
        "deepest_prereq_chain": _deepest_prereq_chain(executed, unlocks),
        "functional_areas": len(_families(run.get("observations", []))),
        "replay_validated_transitions": reproduced,
        "replay_validated_unlocked_routes": sorted(r for r in repro_routes
                                                   if any(f"/{x}/" in r for x in ("project", "report", "dashboard"))),
        "writes_executed": wp.get("allowed"), "writes_blocked_destructive": wp.get("blocked_destructive"),
        "write_sweep": {k: sweep.get(k) for k in
                        ("promotable", "writes_executed", "sweep_actions", "unlocked_transitions", "focus",
                         "focus_steps", "focus_prefixes", "replay_floor")},
        "leftover_eligible_in_unlocked_family": leftover_in_family,
        # budget allocation across stages
        "discovery_actions": uf.get("browser_actions"), "sweep_actions": sweep.get("sweep_actions"),
        "replay_actions": m.get("replay_browser_actions"), "total_actions": m.get("browser_actions"),
        "replay_attempts": m.get("replay_attempts"), "replay_untested_paths": m.get("replay_untested_paths"),
        "replay_failures": m.get("replay_failures"), "replay_failure_reasons": m.get("replay_failure_reasons"),
        # efficiency
        "actions_per_executed": round(m.get("browser_actions", 0) / max(1, exec_n), 1),
        "elapsed_s": m.get("elapsed_seconds"), "wall_seconds": row.get("wall_seconds"),
        # integrity / safety
        "projects_created": server.get("projects"), "reports_created": server.get("reports"),
        "tasks_created": server.get("tasks"), "repeat_write_actions_suppressed": m.get("repeat_write_actions_suppressed"),
        "transitions_failed": m.get("transitions_failed"), "unsafe_restorations_suppressed": m.get("unsafe_restorations_suppressed"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("child")
    c.add_argument("--fixture", required=True)
    c.add_argument("--arm", required=True)
    c.add_argument("--trial", type=int, required=True)
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--seconds", type=float, default=None)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--fixtures", default=",".join(FIXTURES))
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--seconds", type=float, default=None)
    ap.add_argument("--label", default=None)
    args = ap.parse_args()

    if args.cmd == "child":
        run_child(args.fixture, args.arm, args.trial, args.out, args.seconds)
        return

    label = args.label or ("smoke" if args.smoke else "matched")
    trials = 1 if args.smoke else args.trials
    seconds = args.seconds if args.seconds is not None else (60.0 if args.smoke else None)
    fixtures = [f for f in args.fixtures.split(",") if f]
    arms = [a for a in args.arms.split(",") if a]
    results: dict[str, Any] = {"label": label, "matched_config": MATCHED, "arms_config": ARMS, "fixtures": {}}
    for fixture in fixtures:
        results["fixtures"][fixture] = {}
        for arm in arms:
            rows = []
            for trial in range(trials):
                out = BASE / label / fixture / arm / f"trial_{trial}"
                cmd = [sys.executable, "-m", "evaluation.depth_verification_ab", "child", "--fixture", fixture,
                       "--arm", arm, "--trial", str(trial), "--out", str(out)]
                if seconds is not None:
                    cmd += ["--seconds", str(seconds)]
                proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1200,
                                      env=dict(os.environ, PYTHONPATH=str(ROOT)))
                if proc.returncode:
                    rows.append({"fixture": fixture, "arm": arm, "trial": trial, "status": "child_error",
                                 "error_tail": (proc.stderr.strip().splitlines() or ["?"])[-4:]})
                    print(f"{fixture}/{arm} t{trial} ERROR {(proc.stderr.strip().splitlines() or ['?'])[-1][:150]}")
                    continue
                r = collect(fixture, arm, trial, out)
                rows.append(r)
                print(f"{fixture}/{arm} t{trial}: exec={r.get('capabilities_executed_count')}/{r.get('inventory')} "
                      f"unlocked={r.get('write_unlocked_count')} chain={r.get('deepest_prereq_chain')} "
                      f"replay={r.get('replay_validated_transitions')} focus_steps={(r.get('write_sweep') or {}).get('focus_steps')} "
                      f"leftover_family={r.get('leftover_eligible_in_unlocked_family')} actions={r.get('total_actions')}")
            results["fixtures"][fixture][arm] = rows
    out = OUT if label in ("matched", "smoke") else OUT.with_name(f"depth_verification_ab_{label}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=1, default=str) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
