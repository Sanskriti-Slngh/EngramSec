"""Stage 1: matched A/B of the opt-in deterministic subtree-scheduling policy on two held-out
breadth-starved variants.

Arms (all share the frozen MATCHED + adaptive_protected budget; the only differences are the opt-in
scheduling flags, which reorder item selection inside the existing focus loop under the SAME sweep budget
and replay floor):

  A        frozen focused_adaptive / adaptive_protected   (baseline; flags off)
  capcap   + focus_to_budget                              (ablation: lift the fixed 12-step focus cap)
  rotate   + focus_to_budget + fair_subtree_rotation      (ablation: add fair hub rotation)
  full     + the above + focus_stagnation_limit=2         (B: the full opt-in policy)

Three deterministic trials per arm per variant, same 140 s wall-clock. No model tokens, no core-explorer
change beyond the opt-in flags, no safety/scope/replay-floor change.

  .venv/bin/python -m evaluation.stage1_scheduling_benchmark
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from evaluation.comprehensive_config import ROOT
from development_apps.breadth_starved_variants import VARIANTS, start_variant, _truth, Spec, Truth

BASE = ROOT / "agent1" / "experiments" / "recovery_transfer" / "stage1_scheduling"
OUT = ROOT / "evaluation" / "results" / "stage1_scheduling_benchmark.json"

MATCHED: dict[str, Any] = {
    "max_seconds": 140.0, "max_browser_actions": 600, "max_transitions": 300,
    "state_aware_exploration": True, "record_aware_graph": True, "interaction_profile": "extended",
    "typed_resource_spider": False, "allow_post_forms": True, "write_policy": "disposable",
    "max_write_requests": 60, "replay_policy": "structure", "replay_structure_attempts": 2,
    "acg_evidence": True, "record_unexecuted_frontier": True, "restoration_shortcut": "direct_url",
    "write_execution_policy": "focused_adaptive", "write_sweep_replay_floor": 0.25,
}

ARMS: dict[str, dict[str, Any]] = {
    "A":      {},
    "capcap": {"focus_to_budget": True},
    "rotate": {"fair_subtree_rotation": True},
    "full":   {"fair_subtree_rotation": True, "focus_stagnation_limit": 2},
}
SAMPLE_K = 2


def cap_of_path(spec: Spec, path: str) -> str | None:
    """Evaluation-side mirror of the variant server's capability recording."""
    parts = [p for p in path.split("/") if p]
    leaf_to_section = {leaf: sec for sec, leaf in spec.sections.items()}
    if not parts:
        return "home"
    p0 = parts[0]
    if p0 in spec.sections and len(parts) == 1:
        return f"{p0}_index"
    if p0 in leaf_to_section and len(parts) == 2:
        return f"{leaf_to_section[p0]}_item"
    if p0 in spec.hubs:
        ch = spec.hubs[p0]
        if len(parts) == 1:
            return f"{p0}_index"
        if len(parts) == 2 and parts[1] in ch:
            return f"{p0}_{parts[1]}"
        if len(parts) == 3 and parts[1] in ch and parts[2] in ch[parts[1]]:
            return f"{p0}_{parts[1]}_{parts[2]}"
    if p0 == spec.ambiguous:
        if len(parts) == 1:
            return f"{p0}_index"
        if len(parts) == 2:
            return f"{p0}_item"
        if len(parts) == 3 and parts[2] == "changelog":
            try:
                n = int(parts[1])
            except ValueError:
                return None
            if n in spec.release_ids:
                return f"{p0}_release_{n}_changelog"
    return None


def hub_of(spec: Spec, cap: str) -> str | None:
    for h in spec.hubs:
        if cap == f"{h}_index" or cap.startswith(f"{h}_"):
            return h
    if cap.startswith(f"{spec.ambiguous}_"):
        return spec.ambiguous
    return None


def _rpat(path: str) -> str:
    return "/" + "/".join("*" if re.fullmatch(r"\d+", s) else s for s in path.split("/") if s)


def _is_breadth_template(spec: Spec, rp: str) -> bool:
    first = rp.strip("/").split("/")[0] if rp.strip("/") else ""
    return first in spec.sections or first in {leaf for leaf in spec.sections.values()}


def _dur(tx) -> float | None:
    try:
        return (datetime.fromisoformat(tx["ended_at"])
                - datetime.fromisoformat(tx["started_at"])).total_seconds()
    except Exception:
        return None


def run_trial(variant: str, arm: str, trial: int) -> dict[str, Any]:
    from agent1.explorer import Explorer
    from agent1.exporter import write_outputs
    from agent1.schema import RunConfig
    out = BASE / variant / arm / f"trial_{trial}"
    out.mkdir(parents=True, exist_ok=True)
    server, url, state, _ = start_variant(variant)
    try:
        config = RunConfig(start_url=url, output_dir=out, context_label=f"stage1-{arm}",
                           environment_attestation=f"disposable:{variant}-inproc",
                           **MATCHED, **ARMS[arm])
        t0 = time.monotonic()
        artifact = Explorer(config, ROOT).run()
        write_outputs(artifact, out)
        (out / "server_state.json").write_text(json.dumps(state.snapshot(), indent=1, default=str))
        (out / "trial.json").write_text(json.dumps(
            {"variant": variant, "arm": arm, "trial": trial, "status": "ok",
             "wall_seconds": round(time.monotonic() - t0, 2),
             "write_sweep": artifact.metrics.write_sweep}, default=str))
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        (out / "trial.json").write_text(json.dumps(
            {"variant": variant, "arm": arm, "trial": trial, "status": "crash",
             "error": f"{type(exc).__name__}: {exc}"}))
        return {"status": "crash", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        server.shutdown()


def collect(variant: str, arm: str, trial: int) -> dict[str, Any]:
    spec: Spec = VARIANTS[variant]
    truth: Truth = _truth(spec)
    out = BASE / variant / arm / f"trial_{trial}"
    run = json.loads((out / "run.json").read_text())
    srv = json.loads((out / "server_state.json").read_text())
    row = json.loads((out / "trial.json").read_text())
    m = run["metrics"]
    executed = set(srv.get("functions", {})) & truth.inventory

    def cov(s):
        return len(executed & s)

    depth = 0
    for c in executed:
        d = 3 if (c.count("_") >= 2 or c.endswith("_changelog")) else (2 if c in truth.deep_functional else 1)
        depth = max(depth, d)

    # per-hub coverage (executed deep caps under each hub) and inventory per hub
    hub_cov: dict[str, list[int]] = {}
    for h in list(spec.hubs) + [spec.ambiguous]:
        inv = {c for c in truth.deep_functional if hub_of(spec, c) == h}
        hub_cov[h] = [len(executed & inv), len(inv)]

    # timeline from transitions (ordered by started_at): caps vs wall-time + time-to-first per hub
    txs = sorted(run.get("transitions", []), key=lambda t: t.get("started_at") or "")
    t_start = None
    first_hub_s: dict[str, float] = {}
    first_deep_s = None
    tmpl_count = Counter()
    tmpl_time = defaultdict(float)
    durs = []
    time_points: list[tuple[float, str]] = []  # (elapsed_s, cap) first-seen only
    seen_caps_t: set[str] = set()
    for t in txs:
        st = t.get("started_at")
        if st and t_start is None:
            t_start = datetime.fromisoformat(st)
        tgt = (t.get("action") or {}).get("target") or ""
        path = re.sub(r"^https?://[^/]+", "", tgt).split("?")[0] or "/"
        rp = _rpat(path)
        tmpl_count[rp] += 1
        dv = _dur(t)
        if dv is not None:
            durs.append(dv)
            tmpl_time[rp] += dv
        cap = cap_of_path(spec, path)
        if st and t_start is not None:
            el = round((datetime.fromisoformat(st) - t_start).total_seconds(), 2)
            if cap in truth.inventory and cap not in seen_caps_t:
                seen_caps_t.add(cap)
                time_points.append((el, cap))
            if cap in truth.deep_functional and first_deep_s is None:
                first_deep_s = el
            h = hub_of(spec, cap) if cap else None
            if h and h not in first_hub_s:
                first_hub_s[h] = el

    # coverage AUC over REQUESTS (server log order; a request-ordered / "over actions" axis) and over TIME
    reqs = srv.get("log_paths", [])
    auc_req = _auc_over_requests(spec, truth, reqs)
    auc_time = _auc_over_time(time_points, len(truth.inventory), m.get("elapsed_seconds"))

    # breadth waste
    import statistics as _st
    avg_all = _st.mean(durs) if durs else 0
    wasted_act = 0
    wasted_time = 0.0
    for rp, c in tmpl_count.items():
        if _is_breadth_template(spec, rp) and c > SAMPLE_K:
            extra = c - SAMPLE_K
            avg = (tmpl_time[rp] / c) if tmpl_time[rp] else avg_all
            wasted_act += extra
            wasted_time += extra * avg

    reproduced = sum(1 for t in txs if t.get("status") == "replay_validated")
    missed = sorted(truth.inventory - executed)
    sweep = row.get("write_sweep") or {}
    return {
        "variant": variant, "arm": arm, "trial": trial,
        "executed_total": len(executed), "inventory": len(truth.inventory),
        "executed_always": cov(truth.always_reachable), "always_total": len(truth.always_reachable),
        "deep_reached": cov(truth.deep_functional), "deep_total": len(truth.deep_functional),
        "executed_tdistinct": cov(truth.template_distinct_deep), "tdistinct_total": len(truth.template_distinct_deep),
        "executed_semantic": cov(truth.semantic_only_deep), "semantic_total": len(truth.semantic_only_deep),
        "max_workflow_depth": depth,
        "hub_coverage": hub_cov,
        "time_to_first_hub_s": {h: first_hub_s.get(h) for h in list(spec.hubs) + [spec.ambiguous]},
        "time_to_first_deep_s": first_deep_s,
        "auc_over_requests": auc_req, "auc_over_time": auc_time,
        "breadth_wasted_actions": wasted_act, "breadth_wasted_time_s": round(wasted_time, 1),
        "total_browser_actions": m.get("browser_actions"),
        "restoration_actions": m.get("restoration_actions"),
        "root_reloads": m.get("root_reloads"),
        "http_requests": m.get("observed_http_requests") or m.get("http_requests"),
        "server_requests": len(reqs),
        "replays_validated": reproduced, "replay_attempts": m.get("replay_attempts"),
        "replay_failures": m.get("replay_failures"),
        "transitions_failed": m.get("transitions_failed"),
        "unsafe_restorations_suppressed": m.get("unsafe_restorations_suppressed"),
        "elapsed_s": m.get("elapsed_seconds"), "wall_seconds": row.get("wall_seconds"),
        "state_changing_requests": m.get("state_changing_requests_issued", 0)
            or (m.get("write_policy") or {}).get("allowed", 0),
        "focus_steps": sweep.get("focus_steps"), "adaptive_seeds": sweep.get("adaptive_seeds"),
        "stagnant_roots": sweep.get("stagnant_roots"),
        "missed": missed,
    }


def _auc_over_requests(spec: Spec, truth: Truth, reqs: list[str]) -> dict[str, Any]:
    if not reqs:
        return {"auc_norm": None, "final": 0, "n": 0}
    seen: set[str] = set()
    area = 0
    for i, p in enumerate(reqs):
        cap = cap_of_path(spec, p)
        if cap in truth.inventory:
            seen.add(cap)
        area += len(seen)  # caps present during this request step (rectangle of width 1)
    inv = len(truth.inventory)
    return {"auc_norm": round(area / (inv * len(reqs)), 4), "final": len(seen), "n": len(reqs)}


def _auc_over_time(points: list[tuple[float, str]], inv: int, elapsed: float | None) -> dict[str, Any]:
    if not points or not elapsed:
        return {"auc_norm": None, "final": len(points)}
    pts = sorted(points)
    area = 0.0
    prev_t = 0.0
    count = 0
    for el, _ in pts:
        area += count * (el - prev_t)
        prev_t = el
        count += 1
    area += count * (max(elapsed, prev_t) - prev_t)  # hold final coverage to end of run
    total = max(elapsed, prev_t)
    return {"auc_norm": round(area / (inv * total), 4) if total else None, "final": count}


def cap_parent_path(spec: Spec, cap: str) -> tuple[str | None, str | None]:
    """(own path, IMMEDIATE-parent path) for a deep cap, so a miss can be classed as stranded (parent
    reached, link was observable) vs undiscovered (immediate parent never reached)."""
    for h, children in spec.hubs.items():
        if cap == f"{h}_index":
            return f"/{h}", "/"
        for c, grandkids in children.items():
            if cap == f"{h}_{c}":
                return f"/{h}/{c}", f"/{h}"
            for g in grandkids:
                if cap == f"{h}_{c}_{g}":
                    return f"/{h}/{c}/{g}", f"/{h}/{c}"
    amb = spec.ambiguous
    m = re.fullmatch(rf"{re.escape(amb)}_release_(\d+)_changelog", cap)
    if m:
        n = m.group(1)
        return f"/{amb}/{n}/changelog", f"/{amb}/{n}"
    return None, None


def diagnose(variant: str, arm: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    spec: Spec = VARIANTS[variant]
    truth: Truth = _truth(spec)
    missed = set(rows[0]["missed"])
    for r in rows[1:]:
        missed &= set(r["missed"])
    # paths actually reached (from the server arrival log of trial 0 — every GET that landed)
    srv0 = json.loads((BASE / variant / arm / "trial_0" / "server_state.json").read_text())
    reached_paths = {p.rstrip("/") or "/" for p in srv0.get("log_paths", [])}

    def parent_reached(cap: str) -> bool:
        _, par = cap_parent_path(spec, cap)
        if par is None:
            return False
        return (par.rstrip("/") or "/") in reached_paths

    classes = {"tdistinct_stranded": [], "tdistinct_undiscovered": [],
               "semantic_stranded": [], "semantic_undiscovered": [], "other": []}
    for c in sorted(missed):
        pr = parent_reached(c)
        if c in truth.template_distinct_deep:
            classes["tdistinct_stranded" if pr else "tdistinct_undiscovered"].append(c)
        elif c in truth.semantic_only_deep:
            classes["semantic_stranded" if pr else "semantic_undiscovered"].append(c)
        else:
            classes["other"].append(c)
    counts = {k: len(v) for k, v in classes.items()}
    return {"stable_missed": sorted(missed), "classes": classes, "counts": counts}


def main() -> None:
    results: dict[str, Any] = {"config": MATCHED, "arms": ARMS, "sample_k": SAMPLE_K,
                               "variants": {}}
    for variant in sorted(VARIANTS):
        results["variants"][variant] = {"arms": {}}
        for arm in ARMS:
            for trial in range(3):
                r = run_trial(variant, arm, trial)
                print(f"{variant}/{arm} t{trial}: {r['status']}"
                      + (f" {r.get('error','')}" if r["status"] != "ok" else ""))
            rows = [collect(variant, arm, t) for t in range(3)]
            med = lambda k: sorted(x[k] for x in rows)[1]
            results["variants"][variant]["arms"][arm] = {
                "trials": rows,
                "median": {k: med(k) for k in ("executed_total", "deep_reached",
                           "executed_tdistinct", "executed_semantic", "total_browser_actions",
                           "restoration_actions", "root_reloads")},
                "diagnosis": diagnose(variant, arm, rows),
            }
            md = results["variants"][variant]["arms"][arm]["median"]
            auc = sorted(x["auc_over_requests"]["auc_norm"] or 0 for x in rows)[1]
            print(f"  == {variant}/{arm}: exec~{md['executed_total']}/{rows[0]['inventory']} "
                  f"deep~{md['deep_reached']}/{rows[0]['deep_total']} "
                  f"(td {md['executed_tdistinct']}/{rows[0]['tdistinct_total']}, "
                  f"sem {md['executed_semantic']}/{rows[0]['semantic_total']}) "
                  f"actions~{md['total_browser_actions']} restore~{md['restoration_actions']} "
                  f"aucReq~{auc} statechg={rows[0]['state_changing_requests']} "
                  f"txfail={rows[0]['transitions_failed']}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1, default=str) + "\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
