"""Matched role-aware exploration experiment (Phase 2): anonymous vs user vs admin.

The only variable across the three arms is the authenticated session. Everything else -- the starting
URL, the exploration policy, the browser-action / wall-clock / HTTP budgets, the write policy -- is
identical. Each arm runs in its own child process (fixture state is created from code per process, so a
fresh interpreter is the reset). The agent never sees credentials: for an authenticated arm the child
provisions a session OUTSIDE the agent (evaluation/auth_provision) and passes only the storage-state file
and the role label (context_label), so Graph A and the ACG carry the true permission context.

Ground truth is role_lab's own annotations (CAPABILITIES / role_inventory) and its server-side executed
ledger (STATE.functions), so recall and precision are measured, not invented.

  .venv/bin/python -m evaluation.role_experiment            # 3 arms x 3 trials
  .venv/bin/python -m evaluation.role_experiment --smoke    # 1 short trial per arm
  .venv/bin/python -m evaluation.role_experiment child --arm user --trial 0 --out DIR [--seconds N]
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

from evaluation.comprehensive_config import ROOT

BASE = ROOT / "agent1" / "experiments" / "recovery_transfer" / "role_experiment"
OUT = ROOT / "evaluation" / "results" / "role_experiment.json"

# arm -> (seeded account username or None for anonymous, role label used as context_label)
ARMS = {"anon": (None, "anonymous"), "user": ("ava", "registered_user"), "admin": ("iris", "admin")}

# Matched configuration shared by every arm (the authenticated session is the only difference).
MATCHED: dict[str, Any] = {
    "max_seconds": 110.0, "max_browser_actions": 260, "max_transitions": 180,
    "state_aware_exploration": True, "record_aware_graph": True, "interaction_profile": "extended",
    "typed_resource_spider": True, "max_resource_fetches": 120, "max_resource_depth": 3,
    "allow_post_forms": True, "write_policy": "disposable", "max_write_requests": 60,
    "replay_policy": "structure", "replay_structure_attempts": 2, "acg_evidence": True,
}


# ---------------------------------------------------------------- child (one arm, one trial)
def run_child(arm: str, trial: int, out: Path, seconds: float | None) -> None:
    from development_apps.role_lab import ACCOUNTS, start_role_lab
    from agent1.explorer import Explorer
    from agent1.exporter import write_outputs
    from agent1.schema import RunConfig

    out.mkdir(parents=True, exist_ok=True)
    account, role = ARMS[arm]
    server, url, state = start_role_lab()
    auth_public: dict[str, Any] | None = None
    storage_state_path: str | None = None
    try:
        if account is not None:
            # Provision a session OUTSIDE the agent. Seeded creds reach provision only through the
            # environment; they are never passed to Explorer and never written to Graph A / the ACG.
            os.environ["ROLE_LAB_TEST_USERNAME"] = account
            os.environ["ROLE_LAB_TEST_PASSWORD"] = ACCOUNTS[account]["password"]
            os.environ["ROLE_LAB_TEST_ROLE"] = role
            from evaluation.auth_provision import provision
            auth = provision("role_lab", url, attested_disposable=True)
            auth_public = auth.public()
            if auth.status != "authenticated":
                (out / "trial.json").write_text(json.dumps(
                    {"arm": arm, "trial": trial, "status": "auth_unavailable",
                     "auth_barrier": auth.barrier, "auth": auth_public}, default=str))
                return
            storage_state_path = str(auth.storage_state_path)
            (out / "auth_prerequisite.json").write_text(json.dumps(auth.prerequisite, indent=1))

        cfg = dict(MATCHED)
        if seconds is not None:
            cfg["max_seconds"] = seconds
        config = RunConfig(
            start_url=url, output_dir=out, context_label=role,          # <-- role carried into Graph A
            storage_state_path=storage_state_path,
            environment_attestation=f"disposable:role_lab-inproc-reset:{arm}",
            **cfg)
        t0 = time.monotonic()
        explorer = Explorer(config, ROOT)
        artifact = explorer.run()
        write_outputs(artifact, out)
        wall = round(time.monotonic() - t0, 2)

        # ACG export + security capability evidence (post-run; never a verdict).
        try:
            from agent1.model.importer import import_run_artifact
            from agent1.model.materialize import materialize
            from agent1.security_evidence import capability_evidence
            run = artifact.model_dump(mode="json")
            export = materialize(import_run_artifact(run, "run.json", arm)).model_dump(mode="json")
            (out / "acg_export.json").write_text(json.dumps(export))
            (out / "capability_evidence.json").write_text(
                json.dumps(capability_evidence(export, run), indent=1, ensure_ascii=False) + "\n")
        except Exception as exc:
            (out / "acg.error.txt").write_text(f"{type(exc).__name__}: {exc}\n")

        (out / "server_state.json").write_text(json.dumps(state.snapshot(), indent=1, default=str))
        wp = artifact.metrics.write_policy if hasattr(artifact.metrics, "write_policy") else None
        (out / "trial.json").write_text(json.dumps({
            "arm": arm, "trial": trial, "status": "ok", "role": role, "wall_seconds": wall,
            "auth": auth_public, "write_policy": wp}, default=str))
    finally:
        server.shutdown()


# ---------------------------------------------------------------- driver (aggregate metrics)
def _run(run_path: Path) -> dict:
    return json.loads(run_path.read_text())


def _families(observations: list[dict]) -> set[str]:
    from urllib.parse import urlsplit
    fam = set()
    for o in observations:
        segs = [s for s in urlsplit(o.get("url", "")).path.split("/") if s]
        fam.add("/" + (segs[0] if segs else ""))
    return fam


# Write capabilities, keyed by the POST route the form targets, so a discovered-but-not-executed write
# can be told apart from one that was never discovered and one the write policy refused.
def _write_caps_discovered(observations: list[dict]) -> dict[str, dict]:
    from urllib.parse import urlsplit
    found: dict[str, dict] = {}
    for o in observations:
        for c in o.get("controls", []):
            if c.get("kind") != "form_submit":
                continue
            path = urlsplit(c.get("target") or "").path
            key = None
            if path.endswith("/order/new"):
                key = "order_create"
            elif path.endswith("/profile"):
                key = "profile_update"
            elif path.endswith("/admin/settings"):
                key = "admin_settings_update"
            elif "/admin/user/" in path and path.endswith("/delete"):
                key = "admin_user_delete"
            if key and (key not in found or (c.get("safe") and not found[key]["safe"])):
                found[key] = {"safe": bool(c.get("safe")), "skip_reason": c.get("skip_reason")}
    return found


def collect(out: Path, arm: str, trial: int) -> dict[str, Any]:
    from development_apps.role_lab import role_inventory
    tp = out / "trial.json"
    if not tp.exists():
        return {"arm": arm, "trial": trial, "status": "missing"}
    row = json.loads(tp.read_text())
    if row.get("status") != "ok":
        return row
    run = _run(out / "run.json")
    m = run["metrics"]
    obs = run.get("observations", [])
    export = json.loads((out / "acg_export.json").read_text()) if (out / "acg_export.json").exists() else {"capabilities": []}
    caps = export.get("capabilities", [])
    server = json.loads((out / "server_state.json").read_text())
    role = row["role"]
    inv = role_inventory(role)
    executed_keys = set(server.get("functions", {}))             # server-side truth (numerator)
    in_scope = executed_keys & inv
    above_scope = executed_keys - inv                            # must be empty (enforcement works)

    # Three-way distinction the brief asks to preserve: executed vs discovered-but-not-executed
    # (observed/gated) vs undiscovered, for the role's write capabilities.
    write_inv = {k for k in inv if k in {"order_create", "profile_update", "admin_settings_update", "admin_user_delete"}}
    discovered_writes = _write_caps_discovered(obs)
    write_status = {}
    for k in sorted(write_inv):
        if k in executed_keys:
            write_status[k] = "executed"
        elif k in discovered_writes:
            write_status[k] = "discovered_blocked" if not discovered_writes[k]["safe"] else "discovered_deferred"
        else:
            write_status[k] = "undiscovered"

    # session/role representation: every observation's session_context must equal the arm role.
    contexts = sorted({o.get("session_context") for o in obs})
    acg_roles = sorted({(c.get("role")) for c in caps if c.get("role")})

    reproduced = sum(1 for c in caps if c.get("status") in ("reproduced", "verified"))
    observed_or_better = sum(1 for c in caps if c.get("status") in ("observed", "reproduced", "verified"))
    wp = row.get("write_policy") or {}
    return {
        "arm": arm, "trial": trial, "status": "ok", "role": role,
        # 1 functional areas + capabilities
        "functional_areas": sorted(_families(obs)), "functional_area_count": len(_families(obs)),
        "distinct_capabilities": len(caps),
        # 2 executed (server-side ground truth) + the three-way write distinction
        "executed_keys": sorted(executed_keys), "executed_in_scope": sorted(in_scope),
        "write_capability_status": write_status,
        # 3 replay-validated
        "capabilities_reproduced": reproduced, "replay_successes": m.get("replay_successes"),
        "replay_attempts": m.get("replay_attempts"),
        # recall / precision against annotations
        "recall": round(len(in_scope) / len(inv), 3) if inv else None,
        "precision": round(len(in_scope) / len(executed_keys), 3) if executed_keys else None,
        "inventory_size": len(inv),
        # 5 auth + prerequisite
        "auth": row.get("auth"), "prerequisite_recorded": (out / "auth_prerequisite.json").exists(),
        # 6 context representation
        "session_contexts": contexts, "acg_roles": acg_roles,
        "context_is_role": contexts == [role],
        # 7 frontier / budget
        "browser_actions": m.get("browser_actions"), "max_browser_actions": run["config"].get("max_browser_actions"),
        "elapsed_s": m.get("elapsed_seconds"), "observed_http": m.get("observed_http_requests"),
        "transitions_observed": m.get("transitions_observed"), "max_transitions": run["config"].get("max_transitions"),
        "transitions_failed": m.get("transitions_failed"), "restoration_actions": m.get("restoration_actions"),
        "termination": (
            "action_cap" if m.get("browser_actions", 0) >= run["config"].get("max_browser_actions", 1)
            else "transition_cap" if m.get("transitions_observed", 0) >= run["config"].get("max_transitions", 1)
            else "time_cap" if m.get("elapsed_seconds", 0) >= run["config"].get("max_seconds", 1) - 3
            else "discovery_replay_reserve_boundary"),
        # write actions that were generated and left queued (deprioritized), not executed
        "deferred_writes_remaining": sum(1 for v in write_status.values() if v == "discovered_deferred"),
        # 8 efficiency
        "actions_per_executed": round(m.get("browser_actions", 0) / max(1, len(executed_keys)), 1),
        "wall_seconds": row.get("wall_seconds"),
        # 9 safety
        "writes_allowed": wp.get("allowed"), "writes_blocked_destructive": wp.get("blocked_destructive"),
        "writes_blocked_cap": wp.get("blocked_write_cap"),
        "server_access_denied": len(server.get("access_denied", [])),
        "executed_above_role": sorted(above_scope),             # MUST be empty
        "observed_or_better": observed_or_better,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("child")
    c.add_argument("--arm", required=True)
    c.add_argument("--trial", type=int, required=True)
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--seconds", type=float, default=None)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--trials", type=int, default=3)
    args = ap.parse_args()

    if args.cmd == "child":
        run_child(args.arm, args.trial, args.out, args.seconds)
        return

    label = "smoke" if args.smoke else "matched"
    trials = 1 if args.smoke else args.trials
    seconds = 30.0 if args.smoke else None
    results: dict[str, Any] = {"label": label, "matched_config": MATCHED, "arms": {}}
    for arm in ARMS:
        rows = []
        for trial in range(trials):
            out = BASE / label / arm / f"trial_{trial}"
            cmd = [sys.executable, "-m", "evaluation.role_experiment", "child", "--arm", arm,
                   "--trial", str(trial), "--out", str(out)]
            if seconds is not None:
                cmd += ["--seconds", str(seconds)]
            t0 = time.monotonic()
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900,
                                  env=dict(os.environ, PYTHONPATH=str(ROOT)))
            if proc.returncode:
                rows.append({"arm": arm, "trial": trial, "status": "child_error",
                             "error_tail": (proc.stderr.strip().splitlines() or ["?"])[-4:]})
                print(f"{arm} t{trial} CHILD_ERROR {(proc.stderr.strip().splitlines() or ['?'])[-1][:160]}")
                continue
            row = collect(out, arm, trial)
            row["driver_wall_s"] = round(time.monotonic() - t0, 2)
            rows.append(row)
            print(f"{arm} t{trial} {row.get('status')} ctx={row.get('session_contexts')} "
                  f"recall={row.get('recall')} exec={row.get('executed_in_scope')} "
                  f"above_role={row.get('executed_above_role')} actions={row.get('browser_actions')}")
        results["arms"][arm] = rows
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1, default=str) + "\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
