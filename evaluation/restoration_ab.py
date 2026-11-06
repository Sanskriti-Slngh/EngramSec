"""State-tolerant restoration A/B (see AGENT1_STATE_RESTORATION_PREREGISTRATION.md).

Two arms over the same agent revision and the same configuration:

  A  strict restoration (production default: restored state group must match)
  B  A + restoration_policy="contract" (agent1/restoration.py)

Both arms use the best previously evaluated perception configuration (perception
ablation arm C: runtime_listener_observation="revisit", readiness off) on top of the
comprehensive primary configuration (FROZEN + INSTRUMENTATION): 180 s / 500 actions /
100 transitions, legacy coverage policy, fresh mode, no POST forms, no model calls.

Every rejected or accepted restoration is also classified by an author-declared oracle
(``oracle``), independent of the contract code, from the recorded saved and restored
observations: safe volatile state, unsafe (wrong record / changed target), irreproducible
server-state change, or unclassified.

  .venv/bin/python -m evaluation.restoration_ab contracts
  .venv/bin/python -m evaluation.restoration_ab run --phase diagnostic --trials 1
  .venv/bin/python -m evaluation.restoration_ab run --phase scored --trials 3
  .venv/bin/python -m evaluation.restoration_ab summarize --phase scored
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

from evaluation.comprehensive_config import ROOT, git_revision, tree_clean
from evaluation.comprehensive_eval import (CHILD_TIMEOUT_S, ENVS, RESULTS, External, ResetFailure, run_config_fields,
                                          trial_metrics)
from evaluation.perception_ablation import perception_metrics

BASE = ROOT / "agent1" / "experiments" / "restoration_ab"
PERCEPTION = {"runtime_listener_observation": "revisit"}          # perception ablation arm C
ARMS: dict[str, dict[str, Any]] = {"A": dict(PERCEPTION), "B": {**PERCEPTION, "restoration_policy": "contract"}}
ARM_NAMES = {"A": "strict restoration", "B": "restoration contract"}
ENV_ORDER = ["volatile_lab", "stateful_lab", "replay_lab", "js_heavy_lab", "crawlground"]
ANNOTATED = {"stateful_lab", "js_heavy_lab", "replay_lab"}
SLEEP_GAP_S = 5.0
RESTORE_ERRORS = {
    "group_mismatch": re.compile(r"^RuntimeError: saved return path restored"),
    "contract_refused": re.compile(r"^RestorationRefused"),
    "unsafe_restoration_refused": re.compile(r"^UnsafeRestoration"),
    "return_path_control_missing": re.compile(r"^RuntimeError: return-path control missing"),
    "different_record_instance": re.compile(r"^RuntimeError: saved return path restored a different record"),
    "registered_control_absent": re.compile(r"^RuntimeError: registered control was not present"),
}


def arm_order(trial: int) -> list[str]:
    return ["A", "B"] if trial % 2 == 0 else ["B", "A"]


def arm_fields(arm: str) -> dict[str, Any]:
    return run_config_fields(True, False, ARMS[arm])


# ------------------------------------------------------------------ oracle (author-declared, contract-independent)
VOLATILE_TASKS = {"Calibrate sensors", "Rotate keys", "Archive logs", "Audit badges", "Patch firmware", "Review alerts"}
CURRENT_RECORD = re.compile(r"Current record: (Harbor survey|Quarry ledger)")
SCOREBOARD = re.compile(r"\d{4}-\d\d-\d\dT[\d:.]+Z|\d+%?|[✓·—]")


def _controls(o: dict) -> set[tuple[str, str]]:
    return {(c["label"], c.get("target") or "") for c in o["controls"] if c.get("safe")
            and (c.get("provenance") or "snapshot") == "snapshot"}


def _after(text: str, label: str, n: int) -> tuple[str, ...] | None:
    m = re.search(re.escape(label) + r"\s*" + r" ".join([r"(\S+)"] * n), text)
    return m.groups() if m else None


def _segment(text: str, label: str, labels: set[str]) -> str | None:
    """Text from ``label`` to the next row label (rendered cells are not separated in innerText)."""
    start = text.find(label)
    if start < 0:
        return None
    rest = text[start + len(label):]
    cut = min([i for other in labels if other != label and (i := rest.find(other)) >= 0] or [len(rest)])
    return rest[:cut]


def oracle(env: str, e: dict, r: dict, action: dict) -> str:
    """Is acting from the restored page ``r`` safe for ``action`` recorded in ``e``? (offline, from records)"""
    if e["url"] != r["url"] or e.get("session_markers") != r.get("session_markers") \
            or e.get("session_context") != r.get("session_context"):
        return "unsafe:different_context"
    forms = lambda o: [(f["method"], f["action"], [(x.get("name"), x.get("input_type")) for x in f["fields"]])
                       for f in o["forms"]]
    if forms(e) != forms(r):
        return "unsafe:form_changed"
    target = (action["label"], action.get("target") or "")
    if target not in {(c["label"], c.get("target") or "") for c in r["controls"] if c.get("safe")}:
        return "unsafe:target_unavailable"
    route = e["route_pattern"]
    et, rt = e.get("meaningful_text", ""), r.get("meaningful_text", "")
    if env == "volatile_lab":
        if route == "/clock":
            return "safe_volatile"
        if route == "/showcase":
            return "unsafe:carousel_target" if action["label"].startswith("Learn about slide") else "safe_volatile"
        if route == "/board":
            if action["label"] in VOLATILE_TASKS:
                row = lambda t: _segment(t, action["label"], VOLATILE_TASKS)
                return "safe_volatile" if row(et) == row(rt) else "unsafe:target_row_changed"
            return "safe_volatile"
        if route == "/desk":
            cur = lambda t: (CURRENT_RECORD.search(t) or [None, None])[1]
            return "safe_volatile" if cur(et) == cur(rt) else "unsafe:wrong_record"
    if env == "crawlground" and route == "/results":
        if SCOREBOARD.sub("#", et) != SCOREBOARD.sub("#", rt):
            return "unclassified"
        row = lambda t: _after(t, action["label"], 3)
        if row(et) is not None and row(et) != row(rt):
            return "unsafe:target_row_changed"
        return "safe_volatile"                    # only scoreboard tokens differ; the target row is unchanged
    added, missing = _controls(r) - _controls(e), _controls(e) - _controls(r)
    missing = {m for m in missing if m[0] not in rt}   # a label still rendered in the page is not removed
    if added or missing:
        return "server_state_changed"
    return "unclassified"


def restoration_metrics(env: str, run: dict, meta: dict) -> dict[str, Any]:
    obs = {o["id"]: o for o in run.get("observations", [])}
    trans = run.get("transitions", [])
    errors: Counter = Counter()
    for t in trans:
        e = t.get("error") or ""
        for name, pat in RESTORE_ERRORS.items():
            if pat.search(e):
                errors[name] += 1
                break
    attempts = [t for t in trans if t.get("restoration_attempted")]
    ok = lambda t: t.get("status") in ("observed", "replay_validated") and not t.get("error")
    rc = (run.get("metrics") or {}).get("restoration_contract") or {}
    decisions = rc.get("decisions") or []
    # Oracle over every strict rejection: arm A's mismatches (from the failed transitions), arm B's evaluations.
    by_obs_time = sorted(run.get("observations", []), key=lambda o: o["recorded_at"])
    graded: list[dict[str, Any]] = []
    if decisions:
        for d in decisions:
            e, r = obs.get(d.get("expected_observation_id")), obs.get(d.get("restored_observation_id"))
            act = next((t["action"] for t in trans if t["action"].get("signature") == d["action_signature"]), None)
            if e and r and act:
                graded.append({"accepted": d["accepted"], "oracle": oracle(env, e, r, act), "tier": d["tier"],
                               "reasons": d["reasons"], "label": d["action_label"], "route": e["route_pattern"]})
    else:
        for t in trans:
            m = re.search(r"restored (\w+), expected (\w+)", t.get("error") or "")
            if not m:
                continue
            e = obs.get(t["source_observation_id"])
            cands = [o for o in by_obs_time if o["group_signature"] == m.group(1) and o["recorded_at"] <= t["ended_at"]]
            if e and cands:
                graded.append({"accepted": False, "oracle": oracle(env, e, cands[-1], t["action"]),
                               "label": t["action"]["label"], "route": e["route_pattern"]})
    oc = Counter(g["oracle"].split(":")[0] for g in graded)
    accepted_unsafe = [g for g in graded if g["accepted"] and g["oracle"].startswith("unsafe")]
    accepted_server = [g for g in graded if g["accepted"] and g["oracle"] == "server_state_changed"]
    safe = [g for g in graded if g["oracle"] == "safe_volatile"]
    # Independent audit of accepted restorations: same URL, session and title in the recorded pair.
    audit_fail = 0
    for d in decisions:
        if d["accepted"]:
            e, r = obs.get(d.get("expected_observation_id")), obs.get(d.get("restored_observation_id"))
            if not (e and r) or (e["url"], e.get("session_markers"), e.get("session_context"), e["title"]) != (
                    r["url"], r.get("session_markers"), r.get("session_context"), r["title"]):
                audit_fail += 1
    # Writes replayed while restoring (prerequisite steps), and repeated known-mutating GETs.
    restore_writes = sum(1 for t in trans for step in t.get("prerequisite_network") or [] for ev in step.get("network") or []
                         if ev.get("method", "GET").upper() not in {"GET", "HEAD", "OPTIONS"} and not ev.get("failure"))
    server = meta.get("server_state") or {}
    out: dict[str, Any] = {
        "restoration_attempts": len(attempts),
        "restoration_successes": sum(1 for t in attempts if ok(t)),
        "restoration_errors": dict(errors),
        "restoration_failures_total": sum(errors.values()),
        "contract": {k: v for k, v in rc.items() if k != "decisions"},
        "strict_rejections_graded": len(graded),
        "oracle_classes": dict(oc),
        "oracle_detail": dict(Counter(g["oracle"] for g in graded)),
        "safe_volatile_rejections": len(safe),
        "safe_volatile_accepted": sum(1 for g in safe if g["accepted"]),
        "accepted_oracle_unsafe": len(accepted_unsafe),
        "accepted_oracle_unsafe_examples": accepted_unsafe[:5],
        "accepted_oracle_server_state_changed": len(accepted_server),
        "accepted_audit_failures": audit_fail,
        "refused_safe_examples": [g for g in safe if not g["accepted"]][:8],
        "writes_replayed_during_restoration": restore_writes,
        "routes_reached": len({o["route_pattern"] for o in run.get("observations", [])}),
        "replay_validated_transitions": sum(1 for t in trans if t.get("status") == "replay_validated"),
    }
    if env == "crawlground":
        out["test_pages_reached"] = len({o["route_pattern"] for o in run.get("observations", [])
                                         if o["route_pattern"].startswith("/test/")})
    if env == "volatile_lab":
        functions = server.get("functions") or {}
        out["functions_executed"] = sorted(functions)
        out["functions_executed_count"] = len(functions)
        # Wrong record: an annotation made for a record other than the one on the page the action was planned from.
        planned = {d["restored_observation_id"]: d["expected_observation_id"] for d in decisions if d["accepted"]}
        names = {"Harbor survey": 1, "Quarry ledger": 2}
        wrong = 0
        for t in trans:
            if t["action"].get("label") == "Annotate current" and ok(t):
                e = obs.get(planned.get(t["source_observation_id"], t["source_observation_id"]))
                shown = names.get((CURRENT_RECORD.search((e or {}).get("meaningful_text", "")) or [None, None])[1])
                requested = {int(q) for ev in t.get("network") or [] for q in re.findall(r"record=(\d+)", ev["url"])}
                if requested and shown not in requested:
                    wrong += 1
        out["wrong_record_annotations"] = wrong
        out["server_annotations"] = server.get("annotations")
    if env == "stateful_lab":
        reqs = meta.get("_server_requests") or []
        out["known_mutating_get_requests"] = sum(1 for m, p in reqs if m == "GET" and p == "/counter")
    return out


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
               "--overrides", json.dumps(ARMS[arm]), "--label-prefix", f"restoration-{arm}"]
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
                meta = json.loads((out / "child_meta.json").read_text()) if (out / "child_meta.json").exists() else {}
                if (out / "server_requests.json").exists():
                    meta["_server_requests"] = json.loads((out / "server_requests.json").read_text())
                export = materialize(import_run_artifact(run, "run.json", env)).model_dump(mode="json")
                p = perception_metrics(run, graph, export)
                row["scope"] = {k: p[k] for k in ("out_of_scope_requests_recorded", "out_of_scope_requests_completed")}
                row["cost"] = {"browser_actions": p["browser_actions"], "agent_elapsed_s": p["agent_elapsed_s"],
                               "observations": p.get("observations")}
                row["restoration"] = restoration_metrics(env, run, meta)
                row["applied_config"] = {k: run["config"].get(k) for k in (
                    "restoration_policy", "restoration_sample_interval_ms", "runtime_listener_observation",
                    "robust_readiness", "policy", "max_seconds", "max_browser_actions", "max_transitions",
                    "allow_post_forms", "exploration_mode")}
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
    rs, ref = row.get("restoration") or {}, row.get("reference") or {}
    log(f"{env} {arm} t{trial} {row['status']} actions={(row.get('cost') or {}).get('browser_actions')} "
        f"caps={(row.get('capabilities') or {}).get('distinct_capabilities_observed_or_better')} "
        f"recall={ref.get('annotation_recall', ref.get('recall'))} restore_fail={rs.get('restoration_failures_total')} "
        f"safe_acc={rs.get('safe_volatile_accepted')}/{rs.get('safe_volatile_rejections')} "
        f"unsafe_acc={rs.get('accepted_oracle_unsafe')} fn={rs.get('functions_executed_count')} "
        f"tp={rs.get('test_pages_reached')} wall={row.get('driver_wall_s')} sleep={row.get('host_sleep_affected')}")
    return row


EXPECTED_AGENT_TREE: str | None = "5b3fe75d02ebc86b0a586f16083308bf6cd171fb"   # agent1/ at 7c05be8


def agent_tree() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD:agent1"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def run(phase: str, trials: int, envs: list[str]) -> None:
    if not tree_clean(("agent1",)):
        raise SystemExit("agent1/ has uncommitted changes: the evaluated agent is not fixed")
    if EXPECTED_AGENT_TREE and agent_tree() != EXPECTED_AGENT_TREE:
        raise SystemExit(f"agent1 tree {agent_tree()} differs from the preregistered {EXPECTED_AGENT_TREE}")
    for env in envs:
        if env not in ENV_ORDER:
            raise SystemExit(f"{env} is not a preregistered development environment for this experiment")
    base = BASE / phase
    base.mkdir(parents=True, exist_ok=True)
    logf = (base / "run_log.txt").open("a")

    def log(msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True); logf.write(line + "\n"); logf.flush()
    log(f"revision {git_revision()} agent tree {agent_tree()} phase {phase} envs {envs} trials {trials}")
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
    "reference.annotation_recall", "reference.annotation_precision", "reference.false_positives", "reference.matched",
    "reference.recall", "reference.markers_scored",
    "capabilities.distinct_capabilities_observed_or_better", "capabilities.evidence_status.reproduced",
    "capabilities.evidence_status.verified",
    "restoration.restoration_attempts", "restoration.restoration_successes", "restoration.restoration_failures_total",
    "restoration.strict_rejections_graded", "restoration.safe_volatile_rejections", "restoration.safe_volatile_accepted",
    "restoration.accepted_oracle_unsafe", "restoration.accepted_oracle_server_state_changed",
    "restoration.accepted_audit_failures", "restoration.writes_replayed_during_restoration",
    "restoration.contract.evaluations", "restoration.contract.accepted", "restoration.contract.refused",
    "restoration.contract.evaluation_ms", "restoration.contract.region_capture.ms",
    "restoration.routes_reached", "restoration.test_pages_reached", "restoration.functions_executed_count",
    "restoration.wrong_record_annotations", "restoration.replay_validated_transitions",
    "restoration.known_mutating_get_requests",
    "cost.browser_actions", "cost.agent_elapsed_s", "driver_wall_s", "driver_monotonic_s",
    "efficiency.actions_failed",
    "safety.state_changing_requests_issued", "safety.state_changing_requests_in_replay",
    "safety.destructive_endpoint_hits", "safety.dangerous_controls_skipped",
    "scope.out_of_scope_requests_recorded", "scope.out_of_scope_requests_completed",
]


def summarize(phase: str = "scored") -> dict[str, Any]:
    base = BASE / phase
    out: dict[str, Any] = {"milestone": "Agent 1 state-tolerant restoration A/B", "phase": phase,
                           "evaluated_revision": git_revision(), "agent_tree": agent_tree(),
                           "arms": {a: {"overrides": ARMS[a], "name": ARM_NAMES[a]} for a in ARMS}, "environments": {}}
    for env in ENV_ORDER:
        entry: dict[str, Any] = {}
        for arm in ARMS:
            rows = [json.loads(p.read_text()) for p in sorted((base / env / arm).glob("trial_*/trial.json"))]
            if not rows:
                continue
            ok = [r for r in rows if r["status"] == "ok" and "restoration" in r]
            stats = {}
            for k in SCALARS:
                vals = [v for r in ok if isinstance(v := _get(r, k), (int, float)) and not isinstance(v, bool)]
                if vals:
                    stats[k] = {"median": round(median(vals), 4), "min": round(min(vals), 4), "max": round(max(vals), 4),
                                "values": vals}
            a: dict[str, Any] = {
                "trials": [{"trial": r["trial"], "status": r["status"], "host_sleep_affected": r.get("host_sleep_affected"),
                            **({"error_tail": r["error_tail"]} if r.get("error_tail") else {}),
                            **({"metric_errors": r["metric_errors"]} if r.get("metric_errors") else {})} for r in rows],
                "metrics": stats,
                "applied_config": ok[0].get("applied_config") if ok else None,
                "restoration_errors_per_trial": [_get(r, "restoration.restoration_errors") for r in ok],
                "oracle_detail_per_trial": [_get(r, "restoration.oracle_detail") for r in ok],
                "contract_refused_by_reason_per_trial": [_get(r, "restoration.contract.refused_by_reason") for r in ok],
                "contract_accepted_by_tier_per_trial": [_get(r, "restoration.contract.accepted_by_tier") for r in ok],
                "contract_tolerated_per_trial": [_get(r, "restoration.contract.tolerated") for r in ok],
                "refused_safe_examples_trial0": _get(ok[0], "restoration.refused_safe_examples") if ok else None,
                "accepted_oracle_unsafe_examples": [x for r in ok for x in (_get(r, "restoration.accepted_oracle_unsafe_examples") or [])],
                "reset_integrity": [{k: (r.get("reset") or {}).get(k) for k in ("teardown_exit", "mount_profile_matches_frozen",
                                                                                 "residual_containers_after_teardown")}
                                    for r in rows] if rows and rows[0].get("reset") else None,
            }
            if env in ANNOTATED and ok:
                a["missed_attribution_trial0"] = _get(ok[0], "reference.missed_attribution")
            if env == "crawlground" and ok:
                a["markers_by_category_per_trial"] = [_get(r, "reference.by_category") for r in ok]
            if env == "volatile_lab" and ok:
                a["functions_per_trial"] = [_get(r, "restoration.functions_executed") for r in ok]
            entry[arm] = a
        if entry:
            out["environments"][env] = entry
    path = RESULTS / f"restoration_ab_{phase}.json"
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
            print(arm, ARM_NAMES[arm], {k: f.get(k) for k in ("restoration_policy", "runtime_listener_observation",
                                                              "robust_readiness", "policy", "max_seconds",
                                                              "max_browser_actions", "max_transitions")})


if __name__ == "__main__":
    main()
