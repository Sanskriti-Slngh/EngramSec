"""Stage 2: controlled A/B of the opt-in `eager_child_expansion` restoration saver.

A = frozen focused_adaptive / adaptive_protected (eager off).
B = A + eager_child_expansion (bounded batch of a verified GET parent's distinct children in one browser
    session, one history return between children, instead of a fresh context + parent restore per child).

Coverage A/B (ground-truth measurable): breadth_starved_lab, atlas, orchard -- 3 deterministic trials each.
Transfer / safety check (independent apps; no capability ground truth): workflow_lab, stateful_lab,
heldout_shop -- 1 deterministic trial each arm, asserting no destructive/state-changing regression, replay
preserved, and no incorrect restorations. No model tokens; the only config change is the opt-in flag.

  .venv/bin/python -m evaluation.stage2_restoration_benchmark
"""
from __future__ import annotations

import json
import re
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from evaluation.comprehensive_config import ROOT
from evaluation.stage0_breadth_benchmark import MATCHED, cap_of_path as cap_breadth
from development_apps import breadth_starved_lab as bsl
from evaluation.stage1_scheduling_benchmark import cap_of_path as cap_variant, hub_of as hub_variant
from development_apps.breadth_starved_variants import VARIANTS, start_variant, _truth

BASE = ROOT / "agent1" / "experiments" / "recovery_transfer" / "stage2_restoration"
OUT = ROOT / "evaluation" / "results" / "stage2_restoration_benchmark.json"
ARMS = {"A": {}, "B": {"eager_child_expansion": True}}
SAMPLE_K = 2


# ----- fixture descriptors (coverage, ground-truth measurable) -----
def _bsl_hubs():
    return (["reports", "settings", "ops", "updates"])


def _bsl_hub_of(cap: str) -> str | None:
    for h in ("reports", "settings", "ops"):
        if cap == f"{h}_index" or cap.startswith(f"{h}_"):
            return h
    if cap.startswith("release_") or cap in ("updates_index", "updates_item"):
        return "updates"
    return None


COVERAGE = {
    "breadth_starved_lab": {
        "start": lambda: bsl.start_breadth_starved_lab(),
        "truth": lambda: {"inv": bsl.FUNCTIONAL_CAPABILITIES, "always": bsl.ALWAYS_REACHABLE,
                          "deep": bsl.DEEP_FUNCTIONAL, "td": bsl.TEMPLATE_DISTINCT_DEEP,
                          "sem": bsl.SEMANTIC_ONLY_DEEP},
        "cap_of_path": cap_breadth,
        "hub_of": _bsl_hub_of, "hubs": _bsl_hubs(),
    },
}
for _v in sorted(VARIANTS):
    def _mk(v):
        spec = VARIANTS[v]
        t = _truth(spec)
        return {
            "start": (lambda v=v: start_variant(v)[:3]),
            "truth": (lambda t=t: {"inv": t.inventory, "always": t.always_reachable, "deep": t.deep_functional,
                                   "td": t.template_distinct_deep, "sem": t.semantic_only_deep}),
            "cap_of_path": (lambda p, spec=spec: cap_variant(spec, p)),
            "hub_of": (lambda c, spec=spec: hub_variant(spec, c)),
            "hubs": list(spec.hubs) + [spec.ambiguous],
        }
    COVERAGE[_v] = _mk(_v)


def _dur(t) -> float:
    try:
        return (datetime.fromisoformat(t["ended_at"]) - datetime.fromisoformat(t["started_at"])).total_seconds()
    except Exception:
        return 0.0


def _path_of(u: str) -> str:
    return re.sub(r"^https?://[^/]+", "", u or "").split("?")[0] or "/"


def run_trial(fixture: str, arm: str, trial: int) -> dict[str, Any]:
    from agent1.explorer import Explorer
    from agent1.exporter import write_outputs
    from agent1.schema import RunConfig
    out = BASE / fixture / arm / f"trial_{trial}"
    out.mkdir(parents=True, exist_ok=True)
    server, url, state = COVERAGE[fixture]["start"]()
    try:
        config = RunConfig(start_url=url, output_dir=out, context_label=f"stage2-{arm}",
                           environment_attestation=f"disposable:{fixture}-inproc", **MATCHED, **ARMS[arm])
        t0 = time.monotonic()
        artifact = Explorer(config, ROOT).run()
        write_outputs(artifact, out)
        (out / "server_state.json").write_text(json.dumps(state.snapshot(), indent=1, default=str))
        (out / "trial.json").write_text(json.dumps(
            {"fixture": fixture, "arm": arm, "trial": trial, "status": "ok",
             "wall_seconds": round(time.monotonic() - t0, 2)}, default=str))
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        (out / "trial.json").write_text(json.dumps(
            {"fixture": fixture, "arm": arm, "trial": trial, "status": "crash",
             "error": f"{type(exc).__name__}: {exc}"}))
        return {"status": "crash", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        server.shutdown()


def collect(fixture: str, arm: str, trial: int) -> dict[str, Any]:
    desc = COVERAGE[fixture]
    truth = desc["truth"]()
    out = BASE / fixture / arm / f"trial_{trial}"
    run = json.loads((out / "run.json").read_text())
    srv = json.loads((out / "server_state.json").read_text())
    row = json.loads((out / "trial.json").read_text())
    m = run["metrics"]
    executed = set(srv.get("functions", {})) & truth["inv"]

    def cov(s):
        return len(executed & s)

    hub_cov = {}
    for h in desc["hubs"]:
        inv = {c for c in truth["deep"] if desc["hub_of"](c) == h}
        hub_cov[h] = [len(executed & inv), len(inv)]

    # timeline: caps over wall-time (first-seen) and restoration wall-time
    txs = sorted(run.get("transitions", []), key=lambda t: t.get("started_at") or "")
    t0 = None
    time_points = []
    seen_t = set()
    restore_wall = 0.0
    first_deep = None
    for t in txs:
        st = t.get("started_at")
        if st and t0 is None:
            t0 = datetime.fromisoformat(st)
        path = _path_of((t.get("action") or {}).get("target"))
        cap = desc["cap_of_path"](path)
        if t.get("restoration_attempted"):
            restore_wall += _dur(t)
        if st and t0 is not None:
            el = round((datetime.fromisoformat(st) - t0).total_seconds(), 2)
            if cap in truth["inv"] and cap not in seen_t:
                seen_t.add(cap)
                time_points.append((el, cap))
            if cap in truth["deep"] and first_deep is None:
                first_deep = el

    reqs = srv.get("log_paths", [])
    auc_req = _auc_req(desc, truth, reqs)
    auc_time = _auc_time(time_points, len(truth["inv"]), m.get("elapsed_seconds"))

    reproduced = sum(1 for t in txs if t.get("status") == "replay_validated")
    elapsed = m.get("elapsed_seconds") or 1.0
    # restoration browser actions WITHOUT double counting: restoration_actions already counts replay/goto/
    # history-return steps; root_reloads are SEPARATE goto_start occurrences (not in restoration_actions).
    disc_reloads = m.get("discovery_root_reloads", 0)
    restoration_browser_actions = m.get("restoration_actions", 0) + disc_reloads
    return {
        "fixture": fixture, "arm": arm, "trial": trial,
        "executed_total": len(executed), "inventory": len(truth["inv"]),
        "deep_reached": cov(truth["deep"]), "deep_total": len(truth["deep"]),
        "executed_tdistinct": cov(truth["td"]), "tdistinct_total": len(truth["td"]),
        "executed_semantic": cov(truth["sem"]), "semantic_total": len(truth["sem"]),
        "hub_coverage": hub_cov,
        "auc_over_requests": auc_req, "auc_over_time": auc_time, "time_to_first_deep_s": first_deep,
        "caps_per_minute": round(len(executed) / (elapsed / 60.0), 2),
        # cost / restoration
        "total_browser_actions": m.get("browser_actions"),
        "restoration_actions": m.get("restoration_actions"),
        "root_reloads": m.get("root_reloads"),
        "discovery_root_reloads": disc_reloads,
        "verification_root_reloads": m.get("verification_root_reloads"),
        "restoration_browser_actions": restoration_browser_actions,
        "restoration_wall_s": round(restore_wall, 1),
        "http_requests": m.get("observed_http_requests"),
        "elapsed_s": m.get("elapsed_seconds"), "wall_seconds": row.get("wall_seconds"),
        # eager mechanism
        "eager_batches": m.get("eager_batches", 0), "eager_children": m.get("eager_children_expanded", 0),
        "eager_parent_returns": m.get("eager_parent_returns", 0),
        "eager_returns_rejected": m.get("eager_returns_rejected", 0),
        # replay / correctness / safety
        "replays_validated": reproduced, "replay_attempts": m.get("replay_attempts"),
        "replay_failures": m.get("replay_failures"),
        "transitions_failed": m.get("transitions_failed"),
        "unsafe_restorations_suppressed": m.get("unsafe_restorations_suppressed"),
        "state_changing_requests": (m.get("write_policy") or {}).get("allowed", 0),
    }


def _auc_req(desc, truth, reqs):
    if not reqs:
        return {"auc_norm": None, "final": 0}
    seen = set()
    area = 0
    for p in reqs:
        c = desc["cap_of_path"](p)
        if c in truth["inv"]:
            seen.add(c)
        area += len(seen)
    return {"auc_norm": round(area / (len(truth["inv"]) * len(reqs)), 4), "final": len(seen)}


def _auc_time(points, inv, elapsed):
    if not points or not elapsed:
        return {"auc_norm": None, "final": len(points)}
    pts = sorted(points)
    area = 0.0
    prev = 0.0
    cnt = 0
    for el, _ in pts:
        area += cnt * (el - prev)
        prev = el
        cnt += 1
    area += cnt * (max(elapsed, prev) - prev)
    return {"auc_norm": round(area / (inv * max(elapsed, prev)), 4), "final": cnt}


# ----- transfer / safety (independent apps, no capability ground truth) -----
TRANSFER_MATCHED = dict(MATCHED)


def _start_transfer(fixture: str):
    if fixture == "workflow_lab":
        from development_apps.workflow_lab import start_workflow_lab
        server, url, state = start_workflow_lab()
        return server, url, (lambda: {})
    if fixture == "stateful_lab":
        from development_apps.stateful_lab import start_stateful_lab
        db = Path(tempfile.mkdtemp()) / "lab.sqlite"
        server, url, reset, log = start_stateful_lab(db)
        return server, url, (lambda: {"server_log": list(log)})
    if fixture == "heldout_shop":
        from development_apps.heldout_shop import start_heldout_shop
        server, _thread, url = start_heldout_shop()
        return server, url, (lambda: {})
    raise SystemExit(fixture)


def run_transfer(fixture: str, arm: str) -> dict[str, Any]:
    from agent1.explorer import Explorer
    from agent1.schema import RunConfig
    out = BASE / "transfer" / fixture / arm
    out.mkdir(parents=True, exist_ok=True)
    server, url, snap = _start_transfer(fixture)
    try:
        config = RunConfig(start_url=url, output_dir=out, context_label=f"stage2t-{arm}",
                           environment_attestation=f"disposable:{fixture}-inproc", **TRANSFER_MATCHED, **ARMS[arm])
        artifact = Explorer(config, ROOT).run()
        m = artifact.metrics
        st = snap()
        destructive = []
        for t in artifact.transitions:
            for e in t.network:
                if (e.method and e.method.upper() not in {"GET", "HEAD", "OPTIONS"} and not e.failure
                        and any(d in (e.url or "") for d in ("/delete", "/destroy", "/drop", "/reset"))):
                    destructive.append(e.url)
        server_log = st.get("server_log", [])
        destructive_log = [p for (mth, p) in server_log if "delete" in str(p).lower()]
        reproduced = sum(1 for t in artifact.transitions if t.status == "replay_validated")
        return {
            "fixture": fixture, "arm": arm, "status": "ok",
            "browser_actions": m.browser_actions, "transitions": len(artifact.transitions),
            "restoration_actions": m.restoration_actions, "root_reloads": m.root_reloads,
            "eager_batches": m.eager_batches, "eager_children": m.eager_children_expanded,
            "eager_parent_returns": m.eager_parent_returns, "eager_returns_rejected": m.eager_returns_rejected,
            "replays_validated": reproduced, "replay_failures": m.replay_failures,
            "transitions_failed": m.transitions_failed,
            "unsafe_restorations_suppressed": m.unsafe_restorations_suppressed,
            "state_changing_allowed": (m.write_policy or {}).get("allowed", 0),
            "blocked_destructive": (m.write_policy or {}).get("blocked_destructive", 0),
            "destructive_requests_fired": destructive,          # MUST be empty
            "destructive_in_server_log": destructive_log,       # MUST be empty
        }
    except Exception as exc:  # noqa: BLE001
        return {"fixture": fixture, "arm": arm, "status": "crash", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        server.shutdown()


def _med(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def main() -> None:
    results: dict[str, Any] = {"config": MATCHED, "arms": ARMS, "coverage": {}, "transfer": []}
    for fixture in COVERAGE:
        results["coverage"][fixture] = {}
        for arm in ARMS:
            for trial in range(3):
                r = run_trial(fixture, arm, trial)
                print(f"{fixture}/{arm} t{trial}: {r['status']}"
                      + (f" {r.get('error','')}" if r["status"] != "ok" else ""))
            rows = [collect(fixture, arm, t) for t in range(3)]
            agg = {k: _med([r[k] for r in rows]) for k in
                   ("executed_total", "deep_reached", "executed_tdistinct", "executed_semantic",
                    "total_browser_actions", "restoration_actions", "root_reloads",
                    "restoration_browser_actions", "restoration_wall_s", "http_requests",
                    "replays_validated", "transitions_failed", "eager_batches", "eager_children",
                    "eager_parent_returns", "eager_returns_rejected", "caps_per_minute",
                    "state_changing_requests")}
            agg["auc_req"] = _med([r["auc_over_requests"]["auc_norm"] or 0 for r in rows])
            agg["auc_time"] = _med([r["auc_over_time"]["auc_norm"] or 0 for r in rows])
            results["coverage"][fixture][arm] = {"trials": rows, "median": agg}
            print(f"  == {fixture}/{arm}: exec~{agg['executed_total']}/{rows[0]['inventory']} "
                  f"deep~{agg['deep_reached']}/{rows[0]['deep_total']} "
                  f"(td {agg['executed_tdistinct']}, sem {agg['executed_semantic']}) | "
                  f"restore_act~{agg['restoration_actions']} restore_wall~{agg['restoration_wall_s']}s "
                  f"actions~{agg['total_browser_actions']} capspm~{agg['caps_per_minute']} | "
                  f"eager b/c/r/rej {agg['eager_batches']}/{agg['eager_children']}/"
                  f"{agg['eager_parent_returns']}/{agg['eager_returns_rejected']} | "
                  f"replay~{agg['replays_validated']} txfail~{agg['transitions_failed']} "
                  f"statechg~{agg['state_changing_requests']} aucReq~{agg['auc_req']}")
    for fixture in ("workflow_lab", "stateful_lab", "heldout_shop"):
        for arm in ARMS:
            r = run_transfer(fixture, arm)
            results["transfer"].append(r)
            print(f"  ~~ transfer {fixture}/{arm}: {r.get('status')} "
                  f"eager_children={r.get('eager_children')} rej={r.get('eager_returns_rejected')} "
                  f"replay={r.get('replays_validated')} txfail={r.get('transitions_failed')} "
                  f"statechg={r.get('state_changing_allowed')} destructive={r.get('destructive_requests_fired')}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1, default=str) + "\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
