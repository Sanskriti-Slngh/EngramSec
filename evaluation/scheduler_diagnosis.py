"""Phase 1 scheduler diagnosis (existing role_lab traces + a read-only terminal-frontier capture).

Answers, per arm, from the agent's own records:
  - safe, eligible write actions discovered but never executed, and WHEN they first became available;
  - what was executed instead after they became available;
  - whether they were prerequisites for other functionality (role_lab: structural check);
  - the cause (priority / budget / restoration failure / safety), separating verified from inferred;
  - how much functionality was still queued when discovery ended.

Verified facts come from the trace (controls, transitions, metrics) and, where present, the read-only
terminal-frontier capture (run with record_unexecuted_frontier). Inferences are labelled.

  .venv/bin/python -m evaluation.scheduler_diagnosis
"""
from __future__ import annotations

import collections
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from evaluation.comprehensive_config import ROOT
from development_apps.role_lab import CAPABILITIES, role_inventory

MATCHED = ROOT / "agent1" / "experiments" / "recovery_transfer" / "role_experiment" / "matched"
DIAGNOSE = ROOT / "agent1" / "experiments" / "recovery_transfer" / "role_experiment" / "diagnose"
OUT = ROOT / "evaluation" / "results" / "scheduler_diagnosis.json"

WRITE_ROUTE_KEY = [("/order/new", "order_create"), ("/admin/settings", "admin_settings_update"),
                   ("/admin/user/", "admin_user_delete"), ("/profile", "profile_update")]
ARM_ROLE = {"anon": "anonymous", "user": "registered_user", "admin": "admin"}


def _write_key(path: str) -> str | None:
    for frag, key in WRITE_ROUTE_KEY:
        if frag == "/admin/user/":
            if "/admin/user/" in path and path.endswith("/delete"):
                return key
        elif path.endswith(frag):
            return key
    return None


def analyze_trace(run: dict, arm: str) -> dict[str, Any]:
    role = ARM_ROLE[arm]
    inv = role_inventory(role)
    obs = run.get("observations", [])
    obs_index = {o["id"]: i for i, o in enumerate(obs)}
    trans = run.get("transitions", [])

    # Safe/blocked write controls discovered, and the first observation index (when they became available).
    discovered: dict[str, dict] = {}
    for i, o in enumerate(obs):
        for c in o.get("controls", []):
            if c.get("kind") != "form_submit":
                continue
            key = _write_key(urlsplit(c.get("target") or "").path)
            if not key:
                continue
            rec = discovered.setdefault(key, {"first_obs_index": i, "safe": bool(c.get("safe")),
                                               "skip_reason": c.get("skip_reason"), "count": 0})
            rec["count"] += 1
            rec["first_obs_index"] = min(rec["first_obs_index"], i)
            if c.get("safe"):
                rec["safe"] = True

    # Executed writes: any transition that fired a non-GET request.
    executed_writes = []
    for t in trans:
        for e in t.get("network", []):
            if (e.get("method") or "GET").upper() not in {"GET", "HEAD", "OPTIONS"} and not e.get("failure"):
                executed_writes.append(urlsplit(e.get("url") or "").path)

    # What was executed, and specifically after the first safe write became available.
    first_write_obs = min((d["first_obs_index"] for d in discovered.values() if d["safe"]), default=None)
    kinds_after = collections.Counter()
    for t in trans:
        src_i = obs_index.get(t.get("source_observation_id"), 0)
        if first_write_obs is not None and src_i >= first_write_obs:
            kinds_after[t.get("action", {}).get("kind")] += 1

    # Prerequisite check (role_lab): would executing a write expose a route the agent had not already
    # mapped? role_lab writes only mutate content on existing routes, so structurally none add a route.
    discovered_routes = {urlsplit(o.get("url") or "").path for o in obs}
    write_unlocks_new_route = False   # role_lab: writes redirect to already-visited routes

    m = run["metrics"]
    safe_writes = {k: v for k, v in discovered.items() if v["safe"]}
    blocked_writes = {k: v for k, v in discovered.items() if not v["safe"]}
    return {
        "arm": arm, "role": role,
        "write_inventory": sorted(k for k in inv if k in dict(WRITE_ROUTE_KEY).values()),
        "safe_writes_discovered": {k: v for k, v in safe_writes.items()},
        "blocked_writes_discovered": {k: v for k, v in blocked_writes.items()},
        "safe_writes_executed": sorted({p for p in executed_writes}),
        "non_get_requests_total": len(executed_writes),
        "first_safe_write_available_at_obs": first_write_obs,
        "total_observations": len(obs),
        "actions_chosen_after_write_available": dict(kinds_after),
        "write_is_prerequisite_for_new_route": write_unlocks_new_route,
        # cause signals (verified from trace)
        "termination_signals": {
            "transitions_observed": m.get("transitions_observed"), "max_transitions": run["config"].get("max_transitions"),
            "browser_actions": m.get("browser_actions"), "max_browser_actions": run["config"].get("max_browser_actions"),
            "elapsed_s": m.get("elapsed_seconds"), "max_seconds": run["config"].get("max_seconds"),
            "transitions_failed": m.get("transitions_failed"), "unsafe_restorations_suppressed": m.get("unsafe_restorations_suppressed"),
            "replay_untested_paths": m.get("replay_untested_paths"),
        },
    }


def load(run_dir: Path) -> dict | None:
    p = run_dir / "run.json"
    return json.loads(p.read_text()) if p.exists() else None


def main() -> None:
    out: dict[str, Any] = {"arms": {}, "terminal_frontier": {}}
    for arm in ("anon", "user", "admin"):
        run = load(MATCHED / arm / "trial_0")
        if run:
            out["arms"][arm] = analyze_trace(run, arm)
        drun = load(DIAGNOSE / arm / "trial_0")
        if drun:
            tf = drun["metrics"].get("unexecuted_frontier") or {}
            # keep only the write-relevant remaining items for readability
            writes = [it for it in tf.get("items", []) if it.get("form_submit")
                      and _write_key(it.get("target_path") or "")]
            out["terminal_frontier"][arm] = {
                "discovery_exit_reason": tf.get("discovery_exit_reason"),
                "exploration_deadline_s": tf.get("exploration_deadline_s"),
                "elapsed_at_exit_s": tf.get("elapsed_at_exit_s"),
                "browser_actions": tf.get("browser_actions"), "max_browser_actions": tf.get("max_browser_actions"),
                "transitions": tf.get("transitions"), "max_transitions": tf.get("max_transitions"),
                "remaining_count": tf.get("remaining_count"), "remaining_form_submits": tf.get("remaining_form_submits"),
                "remaining_write_items": [{"key": _write_key(it["target_path"]), "priority": it["priority"],
                                           "label": it["label"], "target": it["target_path"]} for it in writes],
                "top_remaining_priorities": [it["priority"] for it in tf.get("items", [])[:8]],
            }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, default=str) + "\n")
    for arm, a in out["arms"].items():
        print(f"=== {arm} ({a['role']})")
        print(f"  safe writes discovered: {sorted(a['safe_writes_discovered'])} "
              f"blocked: {sorted(a['blocked_writes_discovered'])}")
        print(f"  non-GET requests fired: {a['non_get_requests_total']}  (writes executed: {a['safe_writes_executed']})")
        print(f"  first safe write available at obs {a['first_safe_write_available_at_obs']}/{a['total_observations']}")
        print(f"  chosen after write available: {a['actions_chosen_after_write_available']}")
        print(f"  restoration failures: {a['termination_signals']['transitions_failed']}  "
              f"replay_untested_paths: {a['termination_signals']['replay_untested_paths']}")
        tf = out["terminal_frontier"].get(arm)
        if tf:
            print(f"  [frontier] exit={tf['discovery_exit_reason']} deadline={tf['exploration_deadline_s']}s "
                  f"exit_at={tf['elapsed_at_exit_s']}s actions={tf['browser_actions']}/{tf['max_browser_actions']} "
                  f"remaining_writes={tf['remaining_write_items']}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
