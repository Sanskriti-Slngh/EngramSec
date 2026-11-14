"""Small development-app transfer check for the recovery fix (one trial per arm per fixture).

Baseline: the integrated 61/91 configuration (180 s / 300 actions / 120 transitions). Fix: the
same plus restoration_policy="contract", restoration_shortcut="direct_url", well_known_discovery.
In-process fixtures with their own references: replay_lab (annotations), heldout_shop (surface
truth), volatile_lab (server-side function ledger).

  .venv/bin/python -m evaluation.fix_dev_regression
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from evaluation.comprehensive_config import ROOT
from evaluation.comprehensive_eval import CHILD_TIMEOUT_S, trial_metrics

BASE = ROOT / "agent1" / "experiments" / "recovery_transfer" / "dev_regression"
CONFIGS = json.loads((ROOT / "evaluation" / "recovery_historical_configs.json").read_text())
# The child sets its own context label; the historical value (`anonymous`) would collide with it.
_strip = lambda cfg: {k: v for k, v in cfg.items() if k != "context_label"}
ARMS = {"baseline": _strip(CONFIGS["crawlmaze_integrated_180"]["run_config"]),
        "fix": _strip(CONFIGS["crawlmaze_integrated_180_fix"]["run_config"])}
FIXTURES = ["replay_lab", "heldout_shop", "volatile_lab"]


def run_one(env: str, arm: str) -> dict[str, Any]:
    out = BASE / env / arm
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "evaluation.comprehensive_eval", "child", "--env", env, "--out", str(out),
           "--overrides", json.dumps(ARMS[arm]), "--label-prefix", f"recovery-{arm}"]
    t0 = time.monotonic()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=CHILD_TIMEOUT_S)
    row: dict[str, Any] = {"env": env, "arm": arm, "status": "ok" if proc.returncode == 0 else "agent_error",
                           "driver_monotonic_s": round(time.monotonic() - t0, 2)}
    if proc.returncode:
        row["error_tail"] = proc.stderr.strip().splitlines()[-3:]
        return row
    m = trial_metrics(env, out)
    run = json.loads((out / "run.json").read_text())
    meta = json.loads((out / "child_meta.json").read_text())
    rc = run["metrics"].get("restoration_contract") or {}
    row.update({
        "reference": m.get("reference"),
        "capabilities": m["capabilities"]["distinct_capabilities_observed_or_better"],
        "capabilities_reproduced": m["capabilities"]["evidence_status"].get("reproduced"),
        "browser_actions": run["metrics"]["browser_actions"], "elapsed_s": run["metrics"]["elapsed_seconds"],
        "restoration_actions": run["metrics"].get("restoration_actions"),
        "failed_transitions": run["metrics"].get("transitions_failed"),
        "direct_url": rc.get("direct_url"), "contract_accepted": rc.get("accepted", 0),
        "contract_refused_by_reason": rc.get("refused_by_reason"),
        "safety": m.get("safety"),
        "functions_executed": sorted((meta.get("server_state") or {}).get("functions") or {}) if env == "volatile_lab" else None,
    })
    return row


def main() -> None:
    rows = []
    for env in FIXTURES:
        for arm in ARMS:
            row = run_one(env, arm)
            rows.append(row)
            ref = row.get("reference") or {}
            print(f"{time.strftime('%H:%M:%S')} {env} {arm} {row['status']} actions={row.get('browser_actions')} "
                  f"caps={row.get('capabilities')} reproduced={row.get('capabilities_reproduced')} "
                  f"recall={ref.get('annotation_recall', ref.get('recall'))} "
                  f"fn={len(row['functions_executed']) if row.get('functions_executed') is not None else None}",
                  flush=True)
    path = ROOT / "evaluation" / "results" / "recovery_fix_dev_regression.json"
    path.write_text(json.dumps(rows, indent=1, default=str) + "\n")


if __name__ == "__main__":
    main()
