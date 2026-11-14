"""Perception-bottleneck causal ablation (see AGENT1_PERCEPTION_ABLATION_PREREGISTRATION.md).

Four arms over the frozen Agent 1 (`a9802e3`) and the frozen comprehensive configuration:

  A  production defaults                      (identical to the comprehensive evaluation)
  B  A + robust_readiness=True                (hydration-aware readiness)
  C  A + runtime_listener_observation=revisit (listener-derived controls + handler revisions)
  D  A + both

Development environments only. No WebExploitBench target is accepted. Each trial runs the
frozen agent in a child process (evaluation.comprehensive_eval child) with the arm's
overrides; runtime is measured independently in this driver with both a monotonic and a
wall clock (their difference flags host sleep). Arms are interleaved per trial in a rotating
order so drift cannot align with one arm.

  .venv/bin/python -m evaluation.perception_ablation contracts
  .venv/bin/python -m evaluation.perception_ablation run --phase diagnostic --trials 1
  .venv/bin/python -m evaluation.perception_ablation run --phase scored --trials 3
  .venv/bin/python -m evaluation.perception_ablation summarize
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

from evaluation.comprehensive_config import ROOT, git_revision, tree_clean
from evaluation.comprehensive_eval import (CHILD_TIMEOUT_S, ENVS, RESULTS, External, ResetFailure, run_config_fields,
                                          trial_metrics)

BASE = ROOT / "agent1" / "experiments" / "perception_ablation"
ARMS: dict[str, dict[str, Any]] = {
    "A": {},
    "B": {"robust_readiness": True},
    "C": {"runtime_listener_observation": "revisit"},
    "D": {"robust_readiness": True, "runtime_listener_observation": "revisit"},
}
ARM_NAMES = {"A": "production defaults", "B": "+ robust readiness", "C": "+ listener revisit", "D": "+ both"}
ENV_ORDER = ["stateful_lab", "js_heavy_lab", "replay_lab", "transfer_library", "crawlground"]
ANNOTATED = {"stateful_lab", "js_heavy_lab", "replay_lab"}
SLEEP_GAP_S = 5.0

RESTORE_PATTERNS = {
    "restore_group_mismatch": re.compile(r"^RuntimeError: saved return path restored"),
    "return_path_control_missing": re.compile(r"^RuntimeError: return-path control missing"),
    "unsafe_restoration_refused": re.compile(r"^UnsafeRestoration"),
}


def arm_order(trial: int) -> list[str]:
    """Rotating (Latin-square) order: every arm takes every position once per 4 trials."""
    arms = list(ARMS)
    k = trial % len(arms)
    return arms[k:] + arms[:k]


def arm_fields(arm: str) -> dict[str, Any]:
    return run_config_fields(True, False, ARMS[arm])


# ------------------------------------------------------------------ perception metrics (agent outputs only)
def _ok(t: dict) -> bool:
    return t.get("status") in ("observed", "replay_validated") and not t.get("error")


def perception_metrics(run: dict, graph: dict, export: dict) -> dict[str, Any]:
    obs = run.get("observations", []) + run.get("replay_observations", [])
    by_prov: dict[str, set[str]] = {}
    for o in obs:
        for c in o.get("controls", []):
            by_prov.setdefault(c.get("provenance") or "snapshot", set()).add(c.get("signature") or c.get("id"))
    trans = run.get("transitions", [])
    lt = [t for t in trans if (t["action"].get("provenance") or "snapshot") == "observed_listener"]
    rev = [t for t in trans if t["action"].get("behavior_revision")]
    # listener-derived transitions that executed but changed nothing observable
    no_effect = [t for t in lt if _ok(t) and t.get("result_group_signature") == t.get("source_group_signature")
                 and not t.get("network")]
    errors = Counter((t.get("error") or "").split(":", 1)[0] for t in trans if t.get("error"))
    restore = Counter()
    for t in trans:
        e = t.get("error") or ""
        for name, pat in RESTORE_PATTERNS.items():
            if pat.search(e):
                restore[name] += 1
    # readiness: controls that became enabled/visible while waiting (first vs last sample)
    gained = waited = timeouts = recorded = 0
    for o in obs:
        r = o.get("readiness") or {}
        s = r.get("samples") or []
        if r.get("status", "not_recorded") != "not_recorded":
            recorded += 1
            waited += r.get("duration_ms") or 0
            timeouts += r.get("status") == "timeout"
        if len(s) >= 2:
            gained += max(0, s[-1]["enabled_control_count"] - s[0]["enabled_control_count"])
    # listener observer cost and candidate flow
    le = [o.get("listener_evidence") for o in obs if o.get("listener_evidence")]
    cand_skips: Counter = Counter()
    for e in le:
        cand_skips.update(e.get("skipped") or {})
    listener_cands = {(c.get("css_path"), c.get("label")) for e in le for c in e.get("candidates", [])}
    adv_listener = {((a.get("control") or {}).get("signature")) for a in graph.get("advertised_unexecuted", [])
                    if (a.get("control") or {}).get("provenance") == "observed_listener"}
    executed_listener = {t["action"].get("signature") for t in lt}
    # capabilities by the provenance of their bound affordances
    aff_prov = {a["id"]: (a.get("family") or {}).get("provenance", "snapshot") for a in export["affordances"]}
    cap_prov = Counter()
    for c in export["capabilities"]:
        if c["status"] not in ("observed", "reproduced", "verified"):
            continue
        provs = {aff_prov.get(b["affordance_id"], "snapshot") for b in c.get("bindings", [])}
        cap_prov["listener_only" if provs == {"observed_listener"} else
                 "mixed" if "observed_listener" in provs else "snapshot_or_unbound"] += 1
    # scope: in-browser requests to an origin outside the configured scope, from the agent's own records
    # (symmetric across arms; the router installed by listener observation does not report its count)
    from agent1.state import allowed_origin
    start, aliases = run["config"]["start_url"], run["config"].get("origin_aliases") or []
    events = [e for t in trans for e in t.get("network", [])] + \
             [e for r in run.get("replays", []) for e in r.get("network", [])] + \
             [e for n in run.get("navigation_evidence", []) or [] for e in n.get("network", [])]
    oos = [e for e in events if e.get("url", "").startswith("http") and not allowed_origin(start, e["url"], aliases)]
    m = run["metrics"]
    return {
        "out_of_scope_requests_recorded": len(oos),
        "out_of_scope_requests_completed": sum(1 for e in oos if not e.get("failure") and e.get("status")),
        "observations": len(obs),
        "controls_observed_by_provenance": {k: len(v) for k, v in by_prov.items()},
        "listener_candidates_distinct": len(listener_cands),
        "listener_candidate_skips": dict(cand_skips),
        "listener_controls_executed_distinct": len(executed_listener - {None}),
        "listener_controls_advertised_unexecuted_distinct": len(adv_listener - executed_listener - {None}),
        "listener_transitions": len(lt), "listener_transitions_ok": sum(_ok(t) for t in lt),
        "listener_transitions_failed": sum(1 for t in lt if t.get("error")),
        "listener_transitions_no_effect": len(no_effect),
        "revision_transitions": len(rev), "revision_transitions_ok": sum(_ok(t) for t in rev),
        "listener_observer_ms": round(sum(e.get("elapsed_ms") or 0 for e in le), 1),
        "listener_observer_cdp_calls": sum(e.get("cdp_calls") or 0 for e in le),
        "readiness_recorded_observations": recorded, "readiness_wait_ms": waited,
        "readiness_timeouts": timeouts, "controls_gained_during_readiness": gained,
        "transition_errors": dict(errors), "restoration_failures": dict(restore),
        "restoration_failures_total": sum(restore.values()),
        "capabilities_by_provenance": dict(cap_prov),
        "browser_actions": m.get("browser_actions"), "agent_elapsed_s": m.get("elapsed_seconds"),
    }


def annotated_attribution(env: str, run: dict, ref: dict) -> dict[str, Any]:
    """Which matched annotated capabilities were reached only through listener-derived or revision actions."""
    from agent1.model.importer import import_run_artifact
    from evaluation.active_ab import _gt
    from evaluation.score_acg import map_actions
    gt = _gt(env)
    records = import_run_artifact(run, "run.json", env)
    mapping = map_actions(gt, records)
    unmatched = set(ref.get("unmatched_annotated") or [])
    matched = sorted({c.id for c in gt.capabilities if c.in_scope} - unmatched)
    by_cap: dict[str, list[dict]] = {}
    for t in run.get("transitions", []):
        truth = mapping.get(t["id"])
        if truth and not str(truth).startswith(("ambiguous", "non:")) and _ok(t):
            by_cap.setdefault(truth, []).append(t)
    listener_only = [c for c in matched if by_cap.get(c) and all(
        (t["action"].get("provenance") or "snapshot") == "observed_listener" for t in by_cap[c])]
    revision = [c for c in matched if any(t["action"].get("behavior_revision") for t in by_cap.get(c, []))]
    return {"matched": matched, "matched_only_via_listener_controls": listener_only,
            "matched_with_revision_actions": revision}


# ------------------------------------------------------------------ driver
def run_trial(env: str, arm: str, trial: int, out: Path, ext: External | None, log) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {"env": env, "arm": arm, "trial": trial, "status": "ok", "overrides": ARMS[arm]}
    url = None
    try:
        if ext:
            t0 = time.monotonic()
            try:
                url = ext.setup()
            except Exception as first:
                row["setup_first_attempt_error"] = f"{type(first).__name__}: {str(first)[:300]}"
                ext.teardown()
                url = ext.setup()
            row["setup_seconds"] = round(time.monotonic() - t0, 1)
        cmd = [sys.executable, "-m", "evaluation.comprehensive_eval", "child", "--env", env, "--out", str(out),
               "--overrides", json.dumps(ARMS[arm]), "--label-prefix", f"perception-{arm}"]
        if url:
            cmd += ["--url", url]
        mono0, wall0 = time.monotonic(), time.time()
        try:
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=CHILD_TIMEOUT_S)
            if proc.returncode:
                row.update(status="agent_error", error_tail=(proc.stderr.strip().splitlines() or ["?"])[-1][:300])
        except subprocess.TimeoutExpired:
            row["status"] = "hard_timeout"
        row["driver_monotonic_s"] = round(time.monotonic() - mono0, 2)
        row["driver_wall_s"] = round(time.time() - wall0, 2)
        row["host_sleep_affected"] = row["driver_wall_s"] - row["driver_monotonic_s"] > SLEEP_GAP_S
        if ext and row["status"] == "ok":
            sc = ext.score(out, url)
            if sc:
                (out / "external_score.json").write_text(json.dumps(sc))
        if (out / "run.json").exists():
            from agent1.model.importer import import_run_artifact
            from agent1.model.materialize import materialize
            try:
                row.update(trial_metrics(env, out))
                run = json.loads((out / "run.json").read_text())
                graph = json.loads((out / "graph_a.json").read_text())
                export = materialize(import_run_artifact(run, "run.json", env)).model_dump(mode="json")
                row["perception"] = perception_metrics(run, graph, export)
                if env in ANNOTATED:
                    row["perception"]["annotated"] = annotated_attribution(env, run, row["reference"])
                row["applied_config"] = {k: run["config"].get(k) for k in ("robust_readiness", "runtime_listener_observation",
                                                                            "settle_ms", "readiness_timeout_ms",
                                                                            "interaction_profile", "policy", "max_seconds",
                                                                            "max_browser_actions", "max_transitions")}
            except Exception as exc:
                row.setdefault("metric_errors", []).append(f"{type(exc).__name__}: {str(exc)[:200]}")
    except Exception as exc:                      # recorded, never hidden; the trial is not mapped
        row.update(status="reset_failure" if isinstance(exc, ResetFailure) else "setup_failure",
                   setup_error=f"{type(exc).__name__}: {str(exc)[:300]}")
    finally:
        if ext:
            ext.teardown()
            row["reset"] = {k: v for k, v in ext.reset.items() if k != "mount_profile"}
    (out / "trial.json").write_text(json.dumps(row, default=str))
    p = row.get("perception") or {}
    ref = row.get("reference") or {}
    log(f"{env} {arm} t{trial} {row['status']} actions={p.get('browser_actions')} "
        f"caps={(row.get('capabilities') or {}).get('distinct_capabilities_observed_or_better')} "
        f"recall={ref.get('annotation_recall', ref.get('recall'))} listener_ok={p.get('listener_transitions_ok')} "
        f"gained={p.get('controls_gained_during_readiness')} wall={row.get('driver_wall_s')} sleep={row.get('host_sleep_affected')}")
    return row


def run(phase: str, trials: int, envs: list[str]) -> None:
    if not tree_clean(("agent1",)):
        raise SystemExit("agent1/ has uncommitted changes: the evaluated agent is not frozen")
    for env in envs:
        if env not in ENV_ORDER:
            raise SystemExit(f"{env} is not a preregistered development environment for this ablation")
    base = BASE / phase
    base.mkdir(parents=True, exist_ok=True)
    logf = (base / "run_log.txt").open("a")

    def log(msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True); logf.write(line + "\n"); logf.flush()
    log(f"revision {git_revision()} phase {phase} envs {envs} trials {trials}")
    for env in envs:
        ext = External(env) if ENVS[env]["kind"] != "inproc" else None
        for trial in range(trials):
            for arm in arm_order(trial):
                out = base / env / arm / f"trial_{trial}"
                if (out / "trial.json").exists():
                    prior = json.loads((out / "trial.json").read_text())
                    if ext:
                        ext.seen_ids |= set((prior.get("reset") or {}).get("container_ids") or [])
                        ext.seen_volumes |= set((prior.get("reset") or {}).get("volume_names") or [])
                    continue
                run_trial(env, arm, trial, out, ext, log)


# ------------------------------------------------------------------ summary
def _get(row: dict, path: str):
    cur: Any = row
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


SCALARS = [
    "reference.annotation_recall", "reference.annotation_precision", "reference.false_positives",
    "reference.matched", "reference.recall", "reference.markers_scored",
    "capabilities.distinct_capabilities_observed_or_better", "capabilities.evidence_status.reproduced",
    "capabilities.evidence_status.verified", "capabilities.unidentified",
    "perception.browser_actions", "perception.agent_elapsed_s", "driver_wall_s", "perception.observations",
    "perception.controls_observed_by_provenance.snapshot", "perception.controls_observed_by_provenance.observed_listener",
    "perception.listener_candidates_distinct", "perception.listener_controls_executed_distinct",
    "perception.listener_controls_advertised_unexecuted_distinct",
    "perception.listener_transitions", "perception.listener_transitions_ok", "perception.listener_transitions_failed",
    "perception.listener_transitions_no_effect", "perception.revision_transitions", "perception.revision_transitions_ok",
    "perception.listener_observer_ms", "perception.listener_observer_cdp_calls",
    "perception.readiness_wait_ms", "perception.readiness_timeouts", "perception.controls_gained_during_readiness",
    "perception.restoration_failures_total", "perception.capabilities_by_provenance.listener_only",
    "perception.capabilities_by_provenance.mixed",
    "efficiency.actions_failed", "efficiency.actions_unique_discovery", "efficiency.actions_redundant",
    "safety.state_changing_requests_issued", "safety.destructive_endpoint_hits", "safety.dangerous_controls_skipped",
    "safety.ws_out_of_scope_refused", "safety.unsupported_functional_claims",
    "perception.out_of_scope_requests_recorded", "perception.out_of_scope_requests_completed",
    "capabilities.refusals.scope_refusals", "capabilities.refusals.safety_refusals_total",
]


def summarize(phase: str = "scored") -> dict[str, Any]:
    base = BASE / phase
    out: dict[str, Any] = {"milestone": "Agent 1 perception ablation", "phase": phase,
                           "evaluated_revision": git_revision(), "arms": {a: {"overrides": ARMS[a], "name": ARM_NAMES[a]}
                                                                          for a in ARMS},
                           "environments": {}}
    for env in ENV_ORDER:
        entry: dict[str, Any] = {}
        for arm in ARMS:
            rows = [json.loads(p.read_text()) for p in sorted((base / env / arm).glob("trial_*/trial.json"))]
            if not rows:
                continue
            ok = [r for r in rows if r["status"] == "ok" and "perception" in r]
            stats = {}
            for k in SCALARS:
                vals = [v for r in ok if isinstance(v := _get(r, k), (int, float)) and not isinstance(v, bool)]
                if vals:
                    stats[k] = {"median": round(median(vals), 4), "min": round(min(vals), 4), "max": round(max(vals), 4)}
            a: dict[str, Any] = {
                "trials": [{"trial": r["trial"], "status": r["status"], "host_sleep_affected": r.get("host_sleep_affected"),
                            **({"error_tail": r["error_tail"]} if r.get("error_tail") else {}),
                            **({"metric_errors": r["metric_errors"]} if r.get("metric_errors") else {})} for r in rows],
                "metrics": stats,
                "deterministic_action_sequences": len({r.get("action_sequence_digest") for r in ok}) == 1 if ok else None,
                "capability_key_sets_identical": len({json.dumps(r.get("capability_keys")) for r in ok}) == 1 if ok else None,
                "applied_config": ok[0].get("applied_config") if ok else None,
                "transition_errors_per_trial": [_get(r, "perception.transition_errors") for r in ok],
                "restoration_failures_per_trial": [_get(r, "perception.restoration_failures") for r in ok],
                "listener_candidate_skips_per_trial": [_get(r, "perception.listener_candidate_skips") for r in ok],
                "reset_integrity": [{k: (r.get("reset") or {}).get(k) for k in ("teardown_exit", "mount_profile_matches_frozen",
                                                                                 "residual_containers_after_teardown")}
                                    for r in rows] if rows and rows[0].get("reset") else None,
            }
            if env in ANNOTATED and ok:
                a["matched_per_trial"] = [_get(r, "perception.annotated.matched") for r in ok]
                a["matched_only_via_listener_controls_per_trial"] = [
                    _get(r, "perception.annotated.matched_only_via_listener_controls") for r in ok]
                a["matched_with_revision_actions_per_trial"] = [_get(r, "perception.annotated.matched_with_revision_actions")
                                                                for r in ok]
                a["missed_attribution_trial0"] = _get(ok[0], "reference.missed_attribution")
            if env == "transfer_library" and ok:
                a["functionality_per_trial"] = [_get(r, "reference.functionality") for r in ok]
                a["transfer_counts_per_trial"] = [{k: _get(r, f"reference.{k}") for k in
                                                  ("documents_reached_2xx", "static_fetched_2xx", "functionality_executed",
                                                   "functionality_replay_validated")} for r in ok]
            if env == "crawlground" and ok:
                a["markers_by_category_per_trial"] = [_get(r, "reference.by_category") for r in ok]
            entry[arm] = a
        if entry:
            out["environments"][env] = entry
    path = RESULTS / f"perception_ablation_{phase}.json"
    path.write_text(json.dumps(out, indent=1, default=str) + "\n")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--phase", choices=["diagnostic", "scored"], required=True)
    r.add_argument("--trials", type=int, required=True)
    r.add_argument("--envs", default=",".join(ENV_ORDER))
    s = sub.add_parser("summarize")
    s.add_argument("--phase", choices=["diagnostic", "scored"], default="scored")
    sub.add_parser("contracts")
    args = ap.parse_args()
    if args.cmd == "run":
        run(args.phase, args.trials, args.envs.split(","))
    elif args.cmd == "summarize":
        summarize(args.phase)
    else:
        for arm in ARMS:
            f = arm_fields(arm)
            print(arm, ARM_NAMES[arm], {k: f[k] for k in ("robust_readiness", "runtime_listener_observation", "settle_ms",
                                                          "policy", "max_seconds", "max_browser_actions",
                                                          "max_transitions") if k in f})


if __name__ == "__main__":
    main()
