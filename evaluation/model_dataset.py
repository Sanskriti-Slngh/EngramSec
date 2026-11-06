"""Labelled action examples from Agent 1's own exploration traces (development fixtures only).

Question each example answers: did executing this already-observed, safety-approved action
reveal genuinely new functionality? The label comes only from the agent's own outcome, in
trace order within its run:

    positive  the result reached a route pattern not seen before in the run, or issued a
              request structure (method + route pattern + parameter names) not seen before,
              or showed a form schema not seen before
    negative  otherwise (the action executed but revealed nothing new)

Benchmark traces never enter the dataset: only runs positively identified as development
fixtures or the operator's own application are used (path names), and anything on the
Crawlground (3456) or Crawl Maze (3460) ports or naming a WebExploitBench target is
excluded. No benchmark scorer, marker or ground truth is read.

  .venv/bin/python -m evaluation.model_dataset          # writes the dataset + a summary
"""
from __future__ import annotations

import glob
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from evaluation.comprehensive_config import ROOT

DEV_ENVS = {"stateful_lab", "js_heavy_lab", "replay_lab", "transfer_library", "volatile_lab", "heldout_shop",
            "coverage_lab", "phase2_lab", "hybrid_lab", "restoration_lab", "whiteboard"}
EXCLUDE_TOKENS = ("crawlground", "crawl_maze", "crawlmaze", "maze", "wxb", "prestashop", "comfyui", "siyucms",
                  "jetlinks", "white-jotter", "whitejotter", "validation_")
EXCLUDE_PORTS = {3456, 3460}
OUT = ROOT / "agent1" / "experiments" / "model_scaling" / "dataset"


def app_of(path: str) -> str | None:
    low = path.lower()
    if any(tok in low for tok in EXCLUDE_TOKENS):
        return None
    parts = path.split("/")
    env = next((p for p in parts if p in DEV_ENVS), None)
    if env is None and "whiteboard" in low:
        env = "whiteboard"
    return env


def route(url: str) -> str:
    from agent1.state import route_pattern
    return route_pattern(url or "").split("?")[0]


def structure(e: dict[str, Any]) -> str | None:
    method = (e.get("method") or "GET").upper()
    rt = e.get("resource_type") or ""
    if e.get("failure") or not (method != "GET" or rt in ("xhr", "fetch") or e.get("parameter_names")):
        return None
    return f"{method} {route(e.get('url', ''))} {sorted(e.get('parameter_names') or [])}"


def examples_from_run(run: dict[str, Any], app: str, run_path: str) -> list[dict[str, Any]]:
    port = urlsplit(run.get("config", {}).get("start_url", "")).port
    if port in EXCLUDE_PORTS:
        return []
    obs = {o["id"]: o for o in run.get("observations", [])}
    seen_routes: set[str] = set()
    seen_structs: set[str] = set()
    seen_forms: set[str] = set()
    out = []
    trans = sorted(run.get("transitions", []), key=lambda t: t.get("started_at") or "")
    first = run.get("observations", [{}])[0] if run.get("observations") else {}
    if first:
        seen_routes.add(first.get("route_pattern", "").split("?")[0])
    history: list[str] = []
    for t in trans:
        if t.get("status") not in ("observed", "replay_validated"):
            continue
        src, res = obs.get(t["source_observation_id"]), obs.get(t.get("result_observation_id"))
        if not src or not res:
            continue
        a = t["action"]
        new_route = res.get("route_pattern", "").split("?")[0] not in seen_routes
        structs = {s for e in t.get("network", []) if (s := structure(e))}
        new_struct = bool(structs - seen_structs)
        forms = {json.dumps([f.get("method"), route(f.get("action", "")),
                             sorted(x.get("name", "") for x in f.get("fields", []))]) for f in res.get("forms", [])}
        new_form = bool(forms - seen_forms)
        label = int(new_route or new_struct or new_form)
        candidates = [c for c in src.get("controls", []) if c.get("safe")]
        out.append({
            "app": app, "run": run_path, "label": label,
            "why": [k for k, v in (("new_route", new_route), ("new_request_structure", new_struct),
                                   ("new_form", new_form)) if v],
            "group": f"{run_path}#{src.get('group_signature')}",
            "page": {"title": (src.get("title") or "")[:120], "route": src.get("route_pattern", "")[:160],
                     "text": (src.get("text_excerpt") or "")[:600]},
            "action": {"id": a.get("control_id"), "kind": a.get("kind"), "label": (a.get("label") or "")[:100],
                       "target_route": route(a.get("target") or "") if a.get("target") else None,
                       "method": a.get("method"), "interaction": a.get("interaction"),
                       "fields": [f.get("name") for f in a.get("fields", [])][:12]},
            "candidates": len(candidates),
            "history": {"steps": len(history), "routes_seen": len(seen_routes), "recent_actions": history[-6:],
                        "visited_routes": sorted(seen_routes)[:40]},
            "dedup_key": hashlib.sha1(json.dumps([app, src.get("route_pattern"), a.get("kind"), a.get("label"),
                                                  route(a.get("target") or ""), label]).encode()).hexdigest()[:16],
        })
        seen_routes.add(res.get("route_pattern", "").split("?")[0])
        seen_structs |= structs
        seen_forms |= forms
        history.append(f"{a.get('kind')}:{(a.get('label') or '')[:40]}")
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    used = Counter()
    for p in sorted(glob.glob(str(ROOT / "agent1" / "experiments" / "**" / "run.json"), recursive=True)):
        rel = str(Path(p).relative_to(ROOT))
        app = app_of(rel)
        if not app:
            continue
        try:
            run = json.loads(Path(p).read_text())
        except Exception:
            continue
        ex = examples_from_run(run, app, rel)
        if ex:
            used[app] += 1
            rows.extend(ex)
    distinct = {r["dedup_key"]: r for r in rows}
    with (OUT / "examples.jsonl").open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = {
        "runs_used_by_app": dict(used), "examples": len(rows), "distinct_examples": len(distinct),
        "positives": sum(r["label"] for r in rows),
        "distinct_positives": sum(r["label"] for r in distinct.values()),
        "distinct_by_app": dict(Counter(r["app"] for r in distinct.values())),
        "distinct_positive_by_app": dict(Counter(r["app"] for r in distinct.values() if r["label"])),
        "groups_with_both_labels": sum(1 for g, labels in _groups(rows).items() if len(labels) == 2),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


def _groups(rows: list[dict[str, Any]]) -> dict[str, set[int]]:
    g: dict[str, set[int]] = {}
    for r in rows:
        g.setdefault(r["group"], set()).add(r["label"])
    return g


if __name__ == "__main__":
    main()
