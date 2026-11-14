"""Stage 0 baseline: run the frozen focused_adaptive (adaptive_protected) explorer on the breadth-starved
fixture and measure whether functional coverage is genuinely starved by breadth.

Reuses the depth_verification MATCHED budget and the adaptive_protected arm (no core-explorer change). Runs
three matched deterministic trials in-process (sequential, each with a fresh server), then diagnoses every
missed capability. No model tokens are spent.

  .venv/bin/python -m evaluation.stage0_breadth_benchmark
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from evaluation.comprehensive_config import ROOT
from development_apps.breadth_starved_lab import (
    start_breadth_starved_lab, FUNCTIONAL_CAPABILITIES, ALWAYS_REACHABLE, DEEP_FUNCTIONAL,
    TEMPLATE_DISTINCT_DEEP, SEMANTIC_ONLY_DEEP, SECTIONS, REPORTS, SETTINGS, OPS, RELEASE_IDS)

BASE = ROOT / "agent1" / "experiments" / "recovery_transfer" / "stage0_breadth"
OUT = ROOT / "evaluation" / "results" / "stage0_breadth_benchmark.json"

# Identical to depth_verification_ab MATCHED + adaptive_protected arm (the frozen config).
MATCHED: dict[str, Any] = {
    "max_seconds": 140.0, "max_browser_actions": 600, "max_transitions": 300,
    "state_aware_exploration": True, "record_aware_graph": True, "interaction_profile": "extended",
    "typed_resource_spider": False, "allow_post_forms": True, "write_policy": "disposable",
    "max_write_requests": 60, "replay_policy": "structure", "replay_structure_attempts": 2,
    "acg_evidence": True, "record_unexecuted_frontier": True, "restoration_shortcut": "direct_url",
    "write_execution_policy": "focused_adaptive", "write_sweep_replay_floor": 0.25,
}
SAMPLE_K = 2  # a perfect breadth detector keeps this many samples per breadth template

LEAF = {leaf: sec for sec, leaf in SECTIONS.items()}  # item path segment -> section


def cap_of_path(path: str) -> str | None:
    """Map a landing path to the capability its server records (evaluation-side mirror of the fixture)."""
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "home"
    p0 = parts[0]
    if p0 in SECTIONS and len(parts) == 1:
        return f"{p0}_index"
    if p0 in LEAF and len(parts) == 2:
        return f"{LEAF[p0]}_item"
    if p0 == "reports":
        if len(parts) == 1: return "reports_index"
        if len(parts) == 2 and parts[1] in REPORTS: return f"reports_{parts[1]}"
        if len(parts) == 3 and parts[1] in REPORTS and parts[2] in REPORTS[parts[1]]:
            return f"reports_{parts[1]}_{parts[2]}"
    if p0 == "settings":
        if len(parts) == 1: return "settings_index"
        if len(parts) == 2 and parts[1] in SETTINGS: return f"settings_{parts[1]}"
        if len(parts) == 3 and parts[1] in SETTINGS and parts[2] in SETTINGS[parts[1]]:
            return f"settings_{parts[1]}_{parts[2]}"
    if p0 == "ops":
        if len(parts) == 1: return "ops_index"
        if len(parts) == 2 and parts[1] in OPS: return f"ops_{parts[1]}"
        if len(parts) == 3 and parts[1] in OPS and parts[2] in OPS[parts[1]]:
            return f"ops_{parts[1]}_{parts[2]}"
    if p0 == "updates":
        if len(parts) == 1: return "updates_index"
        if len(parts) == 2: return "updates_item"
        if len(parts) == 3 and parts[2] == "changelog":
            try: n = int(parts[1])
            except ValueError: return None
            if n in RELEASE_IDS: return f"release_{n}_changelog"
    return None


def _rpat(path: str) -> str:
    out = []
    for s in [s for s in path.split("/") if s]:
        out.append("*" if re.fullmatch(r"\d+", s) else s)
    return "/" + "/".join(out)


def _is_breadth_template(rp: str) -> bool:
    # non-functional templates: section indexes and their item template
    first = rp.strip("/").split("/")[0] if rp.strip("/") else ""
    if first in SECTIONS or first in LEAF:
        return True
    return False


def _dur(tx) -> float | None:
    try:
        return (datetime.fromisoformat(tx["ended_at"]) - datetime.fromisoformat(tx["started_at"])).total_seconds()
    except Exception:
        return None


def run_trial(trial: int) -> dict[str, Any]:
    from agent1.explorer import Explorer
    from agent1.exporter import write_outputs
    from agent1.schema import RunConfig
    out = BASE / f"trial_{trial}"
    out.mkdir(parents=True, exist_ok=True)
    server, url, state = start_breadth_starved_lab()
    try:
        config = RunConfig(start_url=url, output_dir=out, context_label="stage0",
                           environment_attestation="disposable:breadth_starved-inproc", **MATCHED)
        t0 = time.monotonic()
        artifact = Explorer(config, ROOT).run()
        write_outputs(artifact, out)
        (out / "server_state.json").write_text(json.dumps(state.snapshot(), indent=1, default=str))
        m = artifact.metrics
        (out / "trial.json").write_text(json.dumps({
            "trial": trial, "status": "ok", "wall_seconds": round(time.monotonic() - t0, 2),
            "unexecuted_frontier": m.unexecuted_frontier}, default=str))
        return {"trial": trial, "status": "ok"}
    except Exception as exc:  # noqa: BLE001
        (out / "trial.json").write_text(json.dumps({"trial": trial, "status": "crash",
                                                    "error": f"{type(exc).__name__}: {exc}"}))
        return {"trial": trial, "status": "crash", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        server.shutdown()


def collect(trial: int) -> dict[str, Any]:
    out = BASE / f"trial_{trial}"
    run = json.loads((out / "run.json").read_text())
    srv = json.loads((out / "server_state.json").read_text())
    row = json.loads((out / "trial.json").read_text())
    m = run["metrics"]
    executed = set(srv.get("functions", {})) & FUNCTIONAL_CAPABILITIES

    # coverage by class
    def cov(s): return len(executed & s)
    # workflow depth reached (max path depth among executed deep caps)
    depth = 0
    for c in executed:
        d = 3 if (c.count("_") >= 2 or c.endswith("_changelog")) else (2 if c in DEEP_FUNCTIONAL else 1)
        depth = max(depth, d)

    # transitions ordered by time; breadth spend + time-to-first-deep
    txs = sorted(run.get("transitions", []), key=lambda t: t.get("started_at") or "")
    tmpl_count = Counter(); tmpl_time = defaultdict(float); durs = []
    first_deep_s = None; t_start = None
    for t in txs:
        st = t.get("started_at")
        if st and t_start is None: t_start = datetime.fromisoformat(st)
        tgt = (t.get("action") or {}).get("target") or ""
        path = re.sub(r"^https?://[^/]+", "", tgt).split("?")[0] or "/"
        rp = _rpat(path)
        tmpl_count[rp] += 1
        dv = _dur(t)
        if dv is not None: durs.append(dv); tmpl_time[rp] += dv
        # first deep workflow discovered: landing route is a deep functional cap
        cap = cap_of_path(path)
        if first_deep_s is None and cap in DEEP_FUNCTIONAL and st and t_start is not None:
            first_deep_s = round((datetime.fromisoformat(st) - t_start).total_seconds(), 1)

    wasted_act = 0; wasted_time = 0.0; breadth_templates = []
    import statistics as _st
    avg_all = _st.mean(durs) if durs else 0
    for rp, c in tmpl_count.items():
        if _is_breadth_template(rp) and c > SAMPLE_K:
            extra = c - SAMPLE_K
            avg = (tmpl_time[rp] / c) if tmpl_time[rp] else avg_all
            wasted_act += extra; wasted_time += extra * avg
            breadth_templates.append((rp, c))

    reproduced = sum(1 for t in txs if t.get("status") == "replay_validated")
    missed = sorted(FUNCTIONAL_CAPABILITIES - executed)
    return {
        "trial": trial,
        "executed_total": len(executed), "inventory": len(FUNCTIONAL_CAPABILITIES),
        "executed_always": cov(ALWAYS_REACHABLE), "always_total": len(ALWAYS_REACHABLE),
        "executed_tdistinct_deep": cov(TEMPLATE_DISTINCT_DEEP), "tdistinct_total": len(TEMPLATE_DISTINCT_DEEP),
        "executed_semantic_deep": cov(SEMANTIC_ONLY_DEEP), "semantic_total": len(SEMANTIC_ONLY_DEEP),
        "deep_reached": cov(DEEP_FUNCTIONAL), "deep_total": len(DEEP_FUNCTIONAL),
        "max_workflow_depth": depth,
        "breadth_wasted_actions": wasted_act, "breadth_wasted_time_s": round(wasted_time, 1),
        "total_tx_time_s": round(sum(durs), 1), "median_tx_s": round(_st.median(durs), 2) if durs else None,
        "time_to_first_deep_s": first_deep_s,
        "top_breadth_templates": sorted(breadth_templates, key=lambda x: -x[1])[:6],
        "replays_validated": reproduced, "replay_attempts": m.get("replay_attempts"),
        "replay_failures": m.get("replay_failures"), "transitions_failed": m.get("transitions_failed"),
        "unsafe_restorations_suppressed": m.get("unsafe_restorations_suppressed"),
        "total_browser_actions": m.get("browser_actions"), "elapsed_s": m.get("elapsed_seconds"),
        "http_requests": (m.get("http_requests") or m.get("requests")),
        "state_changing_requests": m.get("state_changing_requests_issued", 0)
            or (m.get("write_policy") or {}).get("allowed", 0),
        "wall_seconds": row.get("wall_seconds"),
        "missed": missed,
    }


def diagnose_missed(trials: list[dict[str, Any]]) -> dict[str, Any]:
    """For the stable missed set: classify each missed deep cap by whether its parent area was reached
    (discovered-but-stranded -> recoverable by breadth-reclaimed budget) vs never discovered."""
    missed = set(trials[0]["missed"])
    for t in trials[1:]:
        missed &= set(t["missed"])  # stable across trials
    run = json.loads((BASE / "trial_0" / "run.json").read_text())
    reached_paths = set()
    for t in run.get("transitions", []):
        if t.get("status") in (None, "ok", "replay_validated") or t.get("result_observation_id"):
            tgt = (t.get("action") or {}).get("target") or ""
            reached_paths.add(re.sub(r"^https?://[^/]+", "", tgt).split("?")[0])
    srv = set(json.loads((BASE / "trial_0" / "server_state.json").read_text()).get("functions", {}))

    def parent_reached(cap: str) -> bool:
        # the cap's parent index/hub was executed -> the cap's link was observable
        if cap.startswith("reports_"): return "reports_index" in srv
        if cap.startswith("settings_"): return "settings_index" in srv
        if cap.startswith("ops_"): return "ops_index" in srv
        if cap.startswith("release_"): return "updates_index" in srv
        return False

    classes = {"tdistinct_stranded": [], "tdistinct_undiscovered": [],
               "semantic_stranded": [], "semantic_undiscovered": [], "other": []}
    for c in sorted(missed):
        is_sem = c in SEMANTIC_ONLY_DEEP
        is_td = c in TEMPLATE_DISTINCT_DEEP
        pr = parent_reached(c)
        if is_td: classes["tdistinct_stranded" if pr else "tdistinct_undiscovered"].append(c)
        elif is_sem: classes["semantic_stranded" if pr else "semantic_undiscovered"].append(c)
        else: classes["other"].append(c)
    return {"stable_missed": sorted(missed), "classes": classes}


def main() -> None:
    results: dict[str, Any] = {"config": MATCHED, "fixture": "breadth_starved_lab",
                               "inventory": len(FUNCTIONAL_CAPABILITIES), "sample_k": SAMPLE_K, "trials": []}
    for trial in range(3):
        r = run_trial(trial)
        print(f"trial {trial}: {r['status']}")
    rows = [collect(t) for t in range(3)]
    results["trials"] = rows
    results["diagnosis"] = diagnose_missed(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1, default=str) + "\n")
    for r in rows:
        print(f"  t{r['trial']}: exec={r['executed_total']}/{r['inventory']} "
              f"deep={r['deep_reached']}/{r['deep_total']} (td {r['executed_tdistinct_deep']}/{r['tdistinct_total']}, "
              f"sem {r['executed_semantic_deep']}/{r['semantic_total']}) depth={r['max_workflow_depth']} "
              f"breadth_wasted={r['breadth_wasted_actions']}act/{r['breadth_wasted_time_s']}s "
              f"t1stDeep={r['time_to_first_deep_s']}s replay={r['replays_validated']} "
              f"txfail={r['transitions_failed']} actions={r['total_browser_actions']} "
              f"statechg={r['state_changing_requests']}")
    print("diagnosis:", json.dumps(results["diagnosis"]["classes"], default=str))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
