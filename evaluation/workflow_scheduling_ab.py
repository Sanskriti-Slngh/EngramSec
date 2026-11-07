"""Phase 3 A/B: baseline scheduler (write deferred) vs authorized_fair (bounded write sweep).

Identical budgets, write policy, attestation and limits in both arms; the only difference is
`write_execution_policy`. Two resettable development fixtures:

  workflow_lab (anonymous)   -- a safe write (create project) unlocks a deeper subtree; a second safe
                                write (feedback) unlocks only a dead-end (negative control).
  role_lab (admin)           -- authenticated writes behind a login; writes mutate content but unlock
                                no new route (negative-ish control for "unlocks functionality").

Each arm runs in its own child process (fixture state created from code per process = the reset). The
read-only terminal-frontier recorder is on in both arms, so deferred writes are measured directly.

  .venv/bin/python -m evaluation.workflow_scheduling_ab --smoke
  .venv/bin/python -m evaluation.workflow_scheduling_ab --trials 3
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

BASE = ROOT / "agent1" / "experiments" / "recovery_transfer" / "workflow_scheduling"
OUT = ROOT / "evaluation" / "results" / "workflow_scheduling_ab.json"

MATCHED: dict[str, Any] = {
    # Discovery is TIME-bound (the action/transition limits are deliberately non-binding), so it stops at
    # the 70%-of-time exploration deadline with the create write still queued under the baseline, leaving
    # headroom for the treatment's post-discovery sweep to execute queued writes and explore what they
    # unlock. Identical in both arms.
    "max_seconds": 140.0, "max_browser_actions": 600, "max_transitions": 300,
    "state_aware_exploration": True, "record_aware_graph": True, "interaction_profile": "extended",
    "typed_resource_spider": False, "allow_post_forms": True, "write_policy": "disposable",
    "max_write_requests": 60, "replay_policy": "structure", "replay_structure_attempts": 2,
    "acg_evidence": True, "record_unexecuted_frontier": True,
}
ARMS = {"baseline": "deferred", "treatment": "authorized_fair"}
FIXTURES = ("workflow_lab", "role_lab_admin")


def _ground_truth(fixture: str):
    if fixture == "workflow_lab":
        from development_apps.workflow_lab import ALWAYS_REACHABLE, FUNCTIONAL_CAPABILITIES, WRITE_UNLOCKS
        return FUNCTIONAL_CAPABILITIES, ALWAYS_REACHABLE, WRITE_UNLOCKS
    from development_apps.role_lab import CAPABILITIES, role_inventory
    inv = role_inventory("admin")
    writes = {"order_create", "profile_update", "admin_settings_update"}        # safe admin writes
    return inv, inv - writes - {"admin_user_delete"}, {}                         # role_lab writes unlock no route


def run_child(fixture: str, arm: str, trial: int, out: Path, seconds: float | None) -> None:
    from agent1.explorer import Explorer
    from agent1.exporter import write_outputs
    from agent1.schema import RunConfig

    out.mkdir(parents=True, exist_ok=True)
    policy = ARMS[arm]
    storage_state_path = None
    context_label = f"wf-{arm}"
    auth_public = None
    if fixture == "workflow_lab":
        from development_apps.workflow_lab import start_workflow_lab
        server, url, state = start_workflow_lab()
    else:
        from development_apps.role_lab import ACCOUNTS, start_role_lab
        server, url, state = start_role_lab()
        os.environ["ROLE_LAB_TEST_USERNAME"] = "iris"
        os.environ["ROLE_LAB_TEST_PASSWORD"] = ACCOUNTS["iris"]["password"]
        os.environ["ROLE_LAB_TEST_ROLE"] = "admin"
        from evaluation.auth_provision import provision
        auth = provision("role_lab", url, attested_disposable=True)
        auth_public = auth.public()
        if auth.status != "authenticated":
            server.shutdown()
            (out / "trial.json").write_text(json.dumps({"fixture": fixture, "arm": arm, "trial": trial,
                                                        "status": "auth_unavailable", "auth": auth_public}))
            return
        storage_state_path = str(auth.storage_state_path)
        context_label = "admin"
        (out / "auth_prerequisite.json").write_text(json.dumps(auth.prerequisite, indent=1))
    try:
        cfg = dict(MATCHED, write_execution_policy=policy)
        if seconds is not None:
            cfg["max_seconds"] = seconds
        config = RunConfig(start_url=url, output_dir=out, context_label=context_label,
                           storage_state_path=storage_state_path,
                           environment_attestation=f"disposable:{fixture}-inproc-reset:{arm}", **cfg)
        t0 = time.monotonic()
        explorer = Explorer(config, ROOT)
        artifact = explorer.run()
        write_outputs(artifact, out)
        (out / "server_state.json").write_text(json.dumps(state.snapshot(), indent=1, default=str))
        m = artifact.metrics
        (out / "trial.json").write_text(json.dumps({
            "fixture": fixture, "arm": arm, "trial": trial, "status": "ok", "policy": policy,
            "wall_seconds": round(time.monotonic() - t0, 2), "auth": auth_public,
            "write_policy": m.write_policy, "write_sweep": m.write_sweep,
            "unexecuted_frontier": m.unexecuted_frontier}, default=str))
    finally:
        server.shutdown()


def _families(obs):
    fam = set()
    for o in obs:
        segs = [s for s in urlsplit(o.get("url", "")).path.split("/") if s]
        fam.add("/" + (segs[0] if segs else ""))
    return fam


def collect(fixture: str, arm: str, trial: int, out: Path) -> dict[str, Any]:
    tp = out / "trial.json"
    if not tp.exists():
        return {"fixture": fixture, "arm": arm, "trial": trial, "status": "missing"}
    row = json.loads(tp.read_text())
    if row.get("status") != "ok":
        return row
    gt, always, unlocks = _ground_truth(fixture)
    run = json.loads((out / "run.json").read_text())
    m = run["metrics"]
    server = json.loads((out / "server_state.json").read_text())
    executed = set(server.get("functions", {})) & set(gt)
    unlocked_caps = set().union(*unlocks.values()) if unlocks else set()
    unlocked_executed = sorted(executed & unlocked_caps)
    reproduced = sum(1 for t in run.get("transitions", []) if t.get("status") == "replay_validated")
    uf = row.get("unexecuted_frontier") or {}
    deferred_writes = uf.get("remaining_form_submits")
    wp = row.get("write_policy") or {}
    sweep = row.get("write_sweep") or {}
    exec_count = len(executed)
    return {
        "fixture": fixture, "arm": arm, "trial": trial, "status": "ok",
        # 1 functional areas
        "functional_areas": len(_families(run.get("observations", []))),
        # 2 unique capabilities executed
        "capabilities_executed": sorted(executed), "capabilities_executed_count": exec_count,
        "inventory_size": len(gt),
        # 3 reproduced
        "replay_validated_transitions": reproduced,
        # 4 prerequisite chains completed (capabilities reachable only after a write)
        "write_unlocked_capabilities_executed": unlocked_executed,
        "write_unlocked_count": len(unlocked_executed),
        # 5 safe writes executed vs deferred
        "writes_executed": wp.get("allowed"), "writes_blocked_destructive": wp.get("blocked_destructive"),
        "writes_blocked_read_only": wp.get("blocked_read_only"),
        "write_sweep": {k: sweep.get(k) for k in ("promotable", "writes_executed", "sweep_actions", "unlocked_transitions")},
        "writes_still_deferred_at_end": deferred_writes,
        # 6 cost per reproduced capability
        "actions": m.get("browser_actions"), "observed_http": m.get("observed_http_requests"),
        "actions_per_executed_cap": round(m.get("browser_actions", 0) / max(1, exec_count), 1),
        # 7 incorrect / redundant state changes
        "projects_created": server.get("projects"), "tasks_created": server.get("tasks"),
        "repeat_write_actions_suppressed": m.get("repeat_write_actions_suppressed"),
        # 8 restoration / reset
        "transitions_failed": m.get("transitions_failed"), "unsafe_restorations_suppressed": m.get("unsafe_restorations_suppressed"),
        # 9 safety / cross-role
        "elapsed_s": m.get("elapsed_seconds"), "wall_seconds": row.get("wall_seconds"),
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
    args = ap.parse_args()

    if args.cmd == "child":
        run_child(args.fixture, args.arm, args.trial, args.out, args.seconds)
        return

    label = "smoke" if args.smoke else "matched"
    trials = 1 if args.smoke else args.trials
    seconds = 60.0 if args.smoke else None
    results: dict[str, Any] = {"label": label, "matched_config": MATCHED, "fixtures": {}}
    for fixture in FIXTURES:
        results["fixtures"][fixture] = {}
        for arm in ARMS:
            rows = []
            for trial in range(trials):
                out = BASE / label / fixture / arm / f"trial_{trial}"
                cmd = [sys.executable, "-m", "evaluation.workflow_scheduling_ab", "child",
                       "--fixture", fixture, "--arm", arm, "--trial", str(trial), "--out", str(out)]
                if seconds is not None:
                    cmd += ["--seconds", str(seconds)]
                proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900,
                                      env=dict(os.environ, PYTHONPATH=str(ROOT)))
                if proc.returncode:
                    rows.append({"fixture": fixture, "arm": arm, "trial": trial, "status": "child_error",
                                 "error_tail": (proc.stderr.strip().splitlines() or ["?"])[-4:]})
                    print(f"{fixture}/{arm} t{trial} ERROR {(proc.stderr.strip().splitlines() or ['?'])[-1][:150]}")
                    continue
                r = collect(fixture, arm, trial, out)
                rows.append(r)
                print(f"{fixture}/{arm} t{trial}: exec={r.get('capabilities_executed_count')}/{r.get('inventory_size')} "
                      f"unlocked={r.get('write_unlocked_count')} writes={r.get('writes_executed')} "
                      f"sweep={r.get('write_sweep',{}).get('writes_executed')} deferred_end={r.get('writes_still_deferred_at_end')} "
                      f"replay={r.get('replay_validated_transitions')} actions={r.get('actions')}")
            results["fixtures"][fixture][arm] = rows
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1, default=str) + "\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
