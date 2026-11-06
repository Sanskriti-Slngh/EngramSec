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
        # Write-policy runs (after the enforcement fix): read-only is the frozen configuration, now
        # enforced at request level; disposable allows bounded, logged, non-destructive writes and is
        # attested by this harness only after the target's reset integrity has been verified.
        VARIANTS[f"wxb_{_t}_policy_read_only"] = {"env": _t, "run_config": {**_frozen["run_config"],
                                                                             "write_policy": "read_only"}}
        VARIANTS[f"wxb_{_t}_policy_disposable"] = {"env": _t, "run_config": {
            **_frozen["run_config"], "allow_post_forms": True, "write_policy": "disposable"}, "attest": True}
# Functional re-evaluation (post-diagnosis, not blind): generous general budgets and depth,
# deployment corrections, well-known discovery, attested disposable writes (destructive blocked).
FUNCTIONAL = {"max_seconds": 1800.0, "max_browser_actions": 2000, "max_transitions": 800,
              "max_total_http_requests": 20000, "max_resource_fetches": 2000, "max_resource_document_fetches": 1400,
              "max_resource_script_fetches": 400, "max_resource_stylesheet_fetches": 200,
              "max_resource_asset_fetches": 400, "max_resource_fetches_per_observation": 30, "max_resource_depth": 8,
              "passive_document_max_depth": 8, "hard_max_resource_depth": 12, "well_known_discovery": True,
              "allow_post_forms": True, "write_policy": "disposable", "max_write_requests": 100}
if WXB_CONFIG.exists():
    for _t in WXB_TARGETS:
        VARIANTS[f"wxb_{_t}_functional"] = {"env": _t, "run_config": {**_frozen["run_config"], **FUNCTIONAL},
                                            "attest": True, "deployment_fixes": True}
        # Authenticated-exploration pair: same functional budget and deployment fixes; the only
        # difference is the provisioned login. Anonymous is the matched control for the authenticated run.
        VARIANTS[f"wxb_{_t}_auth_anon"] = {"env": _t, "run_config": {**_frozen["run_config"], **FUNCTIONAL},
                                           "attest": True, "deployment_fixes": True}
        VARIANTS[f"wxb_{_t}_auth_login"] = {"env": _t, "run_config": {**_frozen["run_config"], **FUNCTIONAL},
                                            "attest": True, "deployment_fixes": True, "authenticate": True,
                                            "require_auth": True}
for _base in ("crawlmaze_integrated_180", "crawlground_integrated_readonly_600"):
    VARIANTS[f"{_base}_policy_read_only"] = {"env": HISTORICAL[_base]["env"],
                                             "run_config": {**HISTORICAL[_base]["run_config"], "write_policy": "read_only"}}


def run_trial(variant: str, trial: int, code_root: Path, label: str, log) -> dict[str, Any]:
    spec = VARIANTS[variant]
    env = spec["env"]
    out = BASE / label / variant / f"trial_{trial}"
    out.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {"variant": variant, "env": env, "trial": trial, "label": label, "status": "ok",
                           "code_root": str(code_root), "code_revision": _rev(code_root)}
    # WebExploitBench: official targetctl, loopback-only check and the frozen reset-integrity profile.
    ext = External(env, require_profile=env in WXB_TARGETS)
    ext.prefer_html_entry = bool(spec.get("deployment_fixes"))
    url = None
    try:
        url = ext.setup()
        run_config = dict(spec["run_config"])
        if spec.get("deployment_fixes"):
            run_config.update(deployment_fixes(ext, url))
            row["deployment_fixes"] = {"entry_choice": getattr(ext, "entry_choice", None),
                                       "origin_aliases": run_config.get("origin_aliases"),
                                       "host_map": run_config.get("host_map")}
        if spec.get("attest"):
            # Only reached after ext.setup() verified the reset-integrity profile (it raises otherwise).
            if not (ext.reset or {}).get("mount_profile_matches_frozen"):
                raise ResetFailure("disposable write policy requires a verified reset-integrity profile")
            run_config["environment_attestation"] = f"disposable:targetctl-reset-verified:{env}"
            row["attestation"] = run_config["environment_attestation"]
        if spec.get("authenticate"):
            # Provision a session OUTSIDE the agent; the agent receives only the storage-state file.
            from evaluation.auth_provision import provision
            attested = bool((ext.reset or {}).get("mount_profile_matches_frozen"))
            auth = provision(env, url, attested_disposable=attested, aliases=run_config.get("origin_aliases"))
            row["auth"] = auth.public()
            if auth.status == "authenticated":
                run_config["storage_state_path"] = str(auth.storage_state_path)
            else:
                # Record the access barrier instead of exploring as if the frontier were complete.
                row["auth_barrier"] = auth.barrier
                if spec.get("require_auth"):
                    row.update(status="auth_unavailable", setup_error=f"authentication unavailable: {auth.barrier}")
                    (out / "trial.json").write_text(json.dumps(row, default=str))
                    return row
        cmd = [sys.executable, str(ROOT / "evaluation" / "recovery_child.py"), "--out", str(out), "--url", url,
               "--config", json.dumps(run_config), "--code-root", str(code_root)]
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
        if row.get("auth", {}).get("status") == "authenticated":
            # The login is a prerequisite of everything the authenticated run maps: co-locate it with
            # Graph A as an authored prerequisite (no secrets; account_ref is opaque).
            (out / "auth_prerequisite.json").write_text(json.dumps(row["auth"]["prerequisite"], indent=1))
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


def deployment_fixes(ext: External, url: str) -> dict[str, Any]:
    """General deployment corrections, decided from the running deployment only:
    every URL the official targetctl printed is an approved origin; a single-label host the entry
    page links to is aliased to the loopback URL only if serving that Host header through loopback
    returns the application (an internal service name, never a public domain)."""
    import re
    import urllib.request
    from urllib.parse import urlsplit
    aliases = [u.rstrip("/") for u in getattr(ext, "urls", []) if u.rstrip("/") != url.rstrip("/")]
    host_map: dict[str, str] = {}
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            html = r.read(2_000_000).decode("utf-8", "replace")
    except Exception:
        html = ""
    hosts = {m.group(1).lower() for m in re.finditer(r"""href=["']https?://([A-Za-z0-9_-]+)(?::80)?/""", html)}
    for host in sorted(hosts - {"localhost"}):
        req = urllib.request.Request(url, headers={"Host": host})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                ok = r.status < 400 and "html" in (r.headers.get("Content-Type") or "").lower()
        except Exception:
            ok = False
        if ok:
            origin = f"http://{host}"
            host_map[origin] = url.rstrip("/")
            aliases.append(origin)
    out: dict[str, Any] = {}
    if aliases:
        out["origin_aliases"] = sorted(set(aliases))
    if host_map:
        out["host_map"] = host_map
    return out


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
