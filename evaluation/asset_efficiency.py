"""Phase 4 comparison: static-asset dedup (resource_cache) on a module-heavy SPA fixture.

Baseline (resource_cache off) vs treatment (resource_cache on), everything else matched, on
development_apps/asset_storm_lab (no ComfyUI-specific rules). The HTTP budget is deliberately small so
the asset storm is binding. The point is NOT fewer requests for their own sake: we measure whether the
freed budget buys more EXECUTED/REPRODUCED functional capability, and that safety is unchanged.

  .venv/bin/python -m evaluation.asset_efficiency            # 3 trials/arm
  .venv/bin/python -m evaluation.asset_efficiency --trials 2
  .venv/bin/python -m evaluation.asset_efficiency child --arm cache --trial 0 --out DIR
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from evaluation.comprehensive_config import ROOT

BASE = ROOT / "agent1" / "experiments" / "recovery_transfer" / "asset_efficiency"
OUT = ROOT / "evaluation" / "results" / "asset_efficiency.json"

MATCHED: dict[str, Any] = {
    "max_seconds": 120.0, "max_browser_actions": 400, "max_transitions": 160,
    "max_total_http_requests": 1500, "typed_resource_spider": True, "max_resource_fetches": 200,
    "max_resource_depth": 2, "state_aware_exploration": True, "record_aware_graph": True,
    "interaction_profile": "extended", "replay_policy": "structure",
}
ARMS = {"baseline": False, "cache": True}


def run_child(arm: str, trial: int, out: Path, seconds: float | None) -> None:
    from development_apps.asset_storm_lab import FUNCTIONAL_CAPABILITIES, start_asset_storm_lab
    from agent1.explorer import Explorer
    from agent1.exporter import write_outputs
    from agent1.schema import RunConfig

    out.mkdir(parents=True, exist_ok=True)
    server, url, state = start_asset_storm_lab()
    try:
        cfg = dict(MATCHED, resource_cache=ARMS[arm])
        if seconds is not None:
            cfg["max_seconds"] = seconds
        config = RunConfig(start_url=url, output_dir=out, context_label=f"asset-{arm}", **cfg)
        t0 = time.monotonic()
        explorer = Explorer(config, ROOT)
        artifact = explorer.run()
        write_outputs(artifact, out)
        (out / "server_state.json").write_text(json.dumps(state.snapshot(), indent=1, default=str))
        (out / "trial.json").write_text(json.dumps({
            "arm": arm, "trial": trial, "status": "ok", "wall_seconds": round(time.monotonic() - t0, 2),
            "functional_inventory": sorted(FUNCTIONAL_CAPABILITIES)}, default=str))
    finally:
        server.shutdown()


def collect(out: Path, arm: str, trial: int) -> dict[str, Any]:
    from development_apps.asset_storm_lab import FUNCTIONAL_CAPABILITIES
    tp = out / "trial.json"
    if not tp.exists():
        return {"arm": arm, "trial": trial, "status": "missing"}
    row = json.loads(tp.read_text())
    run = json.loads((out / "run.json").read_text())
    m = run["metrics"]
    server = json.loads((out / "server_state.json").read_text())
    executed = set(server.get("functions", {})) & FUNCTIONAL_CAPABILITIES
    reproduced = sum(1 for t in run.get("transitions", []) if t.get("status") == "replay_validated")
    return {
        "arm": arm, "trial": trial, "status": "ok",
        "observed_http": m.get("observed_http_requests"),
        "http_cap": run["config"].get("max_total_http_requests"),
        "http_budget_used": m.get("total_http_budget_used"),
        "resource_cache": m.get("resource_cache") or {"enabled": False},
        # server-side asset waste (ground truth): refetches of identical assets beyond the first
        "asset_requests_total": server.get("asset_requests_total"),
        "asset_paths_unique": server.get("asset_paths_unique"),
        "asset_refetch_waste": server.get("asset_refetch_waste"),
        # functional outcomes (the real objective)
        "functional_executed": sorted(executed), "functional_executed_count": len(executed),
        "functional_inventory_size": len(FUNCTIONAL_CAPABILITIES),
        "functional_recall": round(len(executed) / len(FUNCTIONAL_CAPABILITIES), 3),
        "replay_validated_transitions": reproduced,
        "browser_actions": m.get("browser_actions"), "elapsed_s": m.get("elapsed_seconds"),
        "wall_seconds": row.get("wall_seconds"),
        # safety
        "scope_blocked": m.get("total_http_budget_blocked"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("child")
    c.add_argument("--arm", required=True)
    c.add_argument("--trial", type=int, required=True)
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--seconds", type=float, default=None)
    ap.add_argument("--trials", type=int, default=3)
    args = ap.parse_args()

    if args.cmd == "child":
        run_child(args.arm, args.trial, args.out, args.seconds)
        return

    results: dict[str, Any] = {"matched_config": MATCHED, "arms": {}}
    for arm in ARMS:
        rows = []
        for trial in range(args.trials):
            out = BASE / arm / f"trial_{trial}"
            cmd = [sys.executable, "-m", "evaluation.asset_efficiency", "child", "--arm", arm,
                   "--trial", str(trial), "--out", str(out)]
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600,
                                  env=dict(__import__("os").environ, PYTHONPATH=str(ROOT)))
            if proc.returncode:
                rows.append({"arm": arm, "trial": trial, "status": "child_error",
                             "error_tail": (proc.stderr.strip().splitlines() or ["?"])[-4:]})
                print(f"{arm} t{trial} CHILD_ERROR {(proc.stderr.strip().splitlines() or ['?'])[-1][:160]}")
                continue
            r = collect(out, arm, trial)
            rows.append(r)
            print(f"{arm} t{trial}: http={r['observed_http']}/{r['http_cap']} "
                  f"cache_hits={r['resource_cache'].get('hits')} asset_waste={r['asset_refetch_waste']} "
                  f"func_exec={r['functional_executed_count']}/{r['functional_inventory_size']} "
                  f"replay={r['replay_validated_transitions']} actions={r['browser_actions']}")
        results["arms"][arm] = rows
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1, default=str) + "\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
