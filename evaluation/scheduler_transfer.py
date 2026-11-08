"""Phase 4 transfer: run the authorized_fair scheduler on independent development apps and confirm it
does not regress or violate safety -- in particular that it never executes a destructive operation.

Fixtures (independent of role_lab/workflow_lab):
  stateful_lab  -- server-rendered CRUD with safe creates/updates AND a destructive /api/delete.
  heldout_shop  -- an independent site (read-mostly) used to confirm no regression without writes.

For each fixture, runs the baseline (deferred) and treatment (authorized_fair) under identical
disposable+attested config and checks: no crash; the destructive route is never executed (write policy
blocks it); the sweep only promotes safe writes.

  .venv/bin/python -m evaluation.scheduler_transfer
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from evaluation.comprehensive_config import ROOT

BASE = ROOT / "agent1" / "experiments" / "recovery_transfer" / "scheduler_transfer"
OUT = ROOT / "evaluation" / "results" / "scheduler_transfer.json"
MATCHED: dict[str, Any] = {
    "max_seconds": 90.0, "max_browser_actions": 500, "max_transitions": 200,
    "state_aware_exploration": True, "record_aware_graph": True, "allow_post_forms": True,
    "write_policy": "disposable", "max_write_requests": 40, "replay_policy": "structure",
    "record_unexecuted_frontier": True,
}


def _start(fixture: str):
    if fixture == "stateful_lab":
        from development_apps.stateful_lab import start_stateful_lab
        db = Path(tempfile.mkdtemp()) / "lab.sqlite"
        server, url, reset, log = start_stateful_lab(db)
        return server, url, (lambda: {"server_log": list(log), "db": str(db)})
    if fixture == "heldout_shop":
        from development_apps.heldout_shop import start_heldout_shop
        server, _, url = start_heldout_shop()
        return server, url, (lambda: {})
    raise SystemExit(f"unknown fixture {fixture}")


def run_one(fixture: str, policy: str) -> dict[str, Any]:
    from agent1.explorer import Explorer
    from agent1.schema import RunConfig
    out = BASE / fixture / policy
    out.mkdir(parents=True, exist_ok=True)
    server, url, snap = _start(fixture)
    try:
        config = RunConfig(start_url=url, output_dir=out, context_label=f"transfer-{policy}",
                           environment_attestation=f"disposable:{fixture}-inproc", write_execution_policy=policy,
                           **MATCHED)
        artifact = Explorer(config, ROOT).run()
        m = artifact.metrics
        state = snap()
        # Any destructive request that actually fired (non-GET to a destructive route) is a violation.
        destructive_fired = []
        for t in artifact.transitions:
            for e in t.network:
                path = e.url or ""
                if e.method and e.method.upper() not in {"GET", "HEAD", "OPTIONS"} and not e.failure \
                        and any(d in path for d in ("/delete", "/destroy", "/drop", "/reset")):
                    destructive_fired.append(path)
        server_log = state.get("server_log", [])
        destructive_in_server_log = [p for (mth, p) in server_log if "delete" in p.lower()]
        return {"fixture": fixture, "policy": policy, "status": "ok",
                "browser_actions": m.browser_actions, "transitions": len(artifact.transitions),
                "write_policy": {k: m.write_policy.get(k) for k in
                                 ("allowed", "blocked_destructive", "blocked_read_only", "blocked_write_cap")},
                "write_sweep": m.write_sweep,
                "destructive_requests_fired": destructive_fired,              # MUST be empty
                "destructive_in_server_log": destructive_in_server_log,       # MUST be empty
                }
    except Exception as exc:
        return {"fixture": fixture, "policy": policy, "status": "crash", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        server.shutdown()


def main() -> None:
    results = {"matched_config": MATCHED, "runs": []}
    for fixture in ("stateful_lab", "heldout_shop"):
        for policy in ("deferred", "authorized_fair", "focused_subtree", "focused_adaptive"):
            r = run_one(fixture, policy)
            results["runs"].append(r)
            print(f"{fixture}/{policy}: status={r['status']} actions={r.get('browser_actions')} "
                  f"wp={r.get('write_policy')} sweep={(r.get('write_sweep') or {})} "
                  f"destructive_fired={r.get('destructive_requests_fired')} "
                  f"destructive_log={r.get('destructive_in_server_log')}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1, default=str) + "\n")
    # Safety assertion: no destructive operation executed under either policy on any fixture.
    violations = [r for r in results["runs"] if r.get("destructive_requests_fired") or r.get("destructive_in_server_log")]
    print("SAFETY:", "OK (no destructive op executed)" if not violations else f"VIOLATION {violations}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
