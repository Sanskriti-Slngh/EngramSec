"""Recovery of historical crawler results and transfer to public WebExploitBench targets.

Part 1 reruns each historical configuration *verbatim* (copied from the historical
run.json into evaluation/recovery_historical_configs.json) on the current agent, with
no evaluation overrides. New RunConfig fields take their defaults. Scoring is
post-run only (Crawlground results.json from a fresh container; Crawl Maze expected
paths via experiments/score_crawlmaze_posthoc.py).

Part 3 runs one frozen general-purpose configuration on the five public WebExploitBench
targets, one at a time, through the official targetctl (loopback-only check). The
agent never receives benchmark metadata; reachability is computed by a separate
post-run evaluator (evaluation/wxb_reachability.py) only after all runs are frozen.

  .venv/bin/python -m evaluation.recovery_transfer run --variant crawlground_serious_600 --trials 3
  .venv/bin/python -m evaluation.recovery_transfer run --variant <name> --trials N [--code-root <worktree>]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from evaluation.comprehensive_config import ROOT, git_revision
from evaluation.comprehensive_eval import CHILD_TIMEOUT_S, External, ResetFailure

BASE = ROOT / "agent1" / "experiments" / "recovery_transfer"
HISTORICAL = json.loads((ROOT / "evaluation" / "recovery_historical_configs.json").read_text())
SLEEP_GAP_S = 5.0

# Part 3: the frozen general-purpose configuration (set before any WebExploitBench run; see the report).
WXB_TARGETS = ["prestashop", "comfyui", "siyucms", "jetlinks", "white-jotter"]
VARIANTS: dict[str, dict[str, Any]] = {k: v for k, v in HISTORICAL.items()}
WXB_CONFIG = ROOT / "evaluation" / "wxb_frozen_config.json"      # written once, before any WebExploitBench run
if WXB_CONFIG.exists():
    _frozen = json.loads(WXB_CONFIG.read_text())
    for _t in WXB_TARGETS:
        VARIANTS[f"wxb_{_t}"] = {"env": _t, "run_config": _frozen["run_config"], "frozen_from": _frozen["frozen_from"]}


def run_trial(variant: str, trial: int, code_root: Path, label: str, log) -> dict[str, Any]:
    spec = VARIANTS[variant]
    env = spec["env"]
    out = BASE / label / variant / f"trial_{trial}"
    out.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {"variant": variant, "env": env, "trial": trial, "label": label, "status": "ok",
                           "code_root": str(code_root), "code_revision": _rev(code_root)}
    # WebExploitBench: official targetctl, loopback-only check and the frozen reset-integrity profile.
    ext = External(env, require_profile=env in WXB_TARGETS)
    url = None
    try:
        url = ext.setup()
        cmd = [sys.executable, str(ROOT / "evaluation" / "recovery_child.py"), "--out", str(out), "--url", url,
               "--config", json.dumps(spec["run_config"]), "--code-root", str(code_root)]
        mono0, wall0 = time.monotonic(), time.time()
        import os
        env_vars = dict(os.environ, PYTHONPATH=str(code_root))
        try:
            proc = subprocess.run(cmd, cwd=code_root, capture_output=True, text=True,
                                  timeout=max(CHILD_TIMEOUT_S, spec["run_config"]["max_seconds"] * 2.5), env=env_vars)
            if proc.returncode:
                row.update(status="agent_error", error_tail=(proc.stderr.strip().splitlines() or ["?"])[-3:])
        except subprocess.TimeoutExpired:
            row["status"] = "hard_timeout"
        row["driver_monotonic_s"] = round(time.monotonic() - mono0, 2)
        row["driver_wall_s"] = round(time.time() - wall0, 2)
        row["host_sleep_affected"] = row["driver_wall_s"] - row["driver_monotonic_s"] > SLEEP_GAP_S
        if row["status"] == "ok":
            row["score"] = ext.score(out, url)
            if env == "crawlground":       # per-test outcome for the post-run miss audit (git-ignored)
                import urllib.request
                with urllib.request.urlopen(url + "results.json", timeout=10) as resp:
                    (out / "crawlground_results.json").write_bytes(resp.read())
            run = json.loads((out / "run.json").read_text())
            m = run["metrics"]
            row["agent"] = {k: m.get(k) for k in ("browser_actions", "elapsed_seconds", "transitions_observed",
                                                   "transitions_attempted", "transitions_failed", "replay_attempts",
                                                   "replay_successes", "root_reloads", "restoration_actions",
                                                   "live_state_reuses", "resource_fetches_attempted",
                                                   "readiness_wait_ms", "model_calls")}
            row["agent"]["code_revision"] = run.get("code_revision")
            row["applied_config"] = {k: run["config"].get(k) for k in spec["run_config"]}
            row["config_matches_historical"] = all(run["config"].get(k) == v for k, v in spec["run_config"].items())
            if env in WXB_TARGETS:
                from evaluation.comprehensive_eval import trial_metrics
                try:
                    row["discovery_metrics"] = trial_metrics(env, out)
                except Exception as exc:
                    row["metric_errors"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    except Exception as exc:
        row.update(status="reset_failure" if isinstance(exc, ResetFailure) else "setup_failure",
                   setup_error=f"{type(exc).__name__}: {str(exc)[:300]}")
    finally:
        ext.teardown()
        if env in WXB_TARGETS:
            row["reset"] = {k: v for k, v in ext.reset.items() if k != "mount_profile"}
    (out / "trial.json").write_text(json.dumps(row, default=str))
    s = row.get("score") or {}
    headline = (f"{s.get('markers_scored')}/{s.get('denominator')}" if "markers_scored" in s else
                f"{(s.get('score') or {}).get('coverage_total', {}).get('any_fetch')}/{s.get('denominator')}" if s else None)
    log(f"{label} {variant} t{trial} {row['status']} result={headline} actions={(row.get('agent') or {}).get('browser_actions')} "
        f"elapsed={(row.get('agent') or {}).get('elapsed_seconds')} wall={row.get('driver_wall_s')} "
        f"sleep={row.get('host_sleep_affected')} {row.get('error_tail') or row.get('setup_error') or ''}")
    return row


def _rev(root: Path) -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain", "agent1"], cwd=root, capture_output=True, text=True).stdout
    return r.stdout.strip() + ("+dirty" if dirty.strip() else "")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--variant", required=True)
    r.add_argument("--trials", type=int, default=1)
    r.add_argument("--start-trial", type=int, default=0)
    r.add_argument("--label", default="current")
    r.add_argument("--code-root", type=Path, default=ROOT)
    args = ap.parse_args()
    base = BASE / args.label
    base.mkdir(parents=True, exist_ok=True)
    logf = (base / "run_log.txt").open("a")

    def log(msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True); logf.write(line + "\n"); logf.flush()
    log(f"driver revision {git_revision()} code {args.code_root} variant {args.variant}")
    for t in range(args.start_trial, args.start_trial + args.trials):
        run_trial(args.variant, t, args.code_root.resolve(), args.label, log)


if __name__ == "__main__":
    main()
