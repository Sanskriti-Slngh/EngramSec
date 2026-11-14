"""Phase 3 diagnosis: where ComfyUI's HTTP budget goes (frozen traces only; no reruns).

Reads existing ComfyUI run.json artifacts and decomposes the observed HTTP requests to answer the
milestone's questions: unique vs repeated, by resource type, by producing component, identical
resources refetched, and whether the stop was a real resource limit or redundant refetching. The
same decomposition runs on any run.json, so it is not ComfyUI-specific.

  .venv/bin/python -m evaluation.comfyui_request_breakdown
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from evaluation.comprehensive_config import ROOT

RUNS = {
    "frozen_600s": "agent1/experiments/recovery_transfer/wxb/wxb_comfyui/trial_0/run.json",
    "generous_budget": "agent1/experiments/recovery_transfer/wxb_functional/wxb_comfyui_functional/trial_0/run.json",
}
STATIC = re.compile(r"\.(js|mjs|css|png|jpg|jpeg|gif|svg|webp|woff2?|ttf|eot|ico|map)(?:$|\?)", re.I)
STATIC_TYPES = {"script", "stylesheet", "font", "image"}


def _events(run: dict) -> list[dict]:
    ev = [e for t in run.get("transitions", []) for e in t.get("network", [])]
    ev += [e for n in run.get("navigation_evidence", []) for e in n.get("network", [])]
    return ev


def analyze(run: dict) -> dict[str, Any]:
    m = run["metrics"]
    ev = _events(run)
    paths = [urlsplit(e["url"]).path for e in ev if e.get("url")]
    uniq = set(paths)
    by_type = collections.Counter(e.get("resource_type") for e in ev)
    repeats = collections.Counter(paths)
    static_events = [p for p, e in zip(paths, ev)
                     if STATIC.search(p) or e.get("resource_type") in STATIC_TYPES]
    # repeated static assets: same path fetched more than once (the waste)
    static_paths = collections.Counter(p for p in static_events)
    wasted = sum(n - 1 for n in static_paths.values())        # refetches beyond the first
    return {
        "budget": {
            "total_http_requests_cap": (m.get("effective_resource_budgets") or {}).get("total_http_requests"),
            "observed_http_requests": m.get("observed_http_requests"),
            "total_http_budget_used": m.get("total_http_budget_used"),
            "http_budget_by_source": m.get("http_budget_by_source"),
            "browser_actions": m.get("browser_actions"),
            "resource_fetches_attempted": m.get("resource_fetches_attempted"),
            "resource_fetches_succeeded": m.get("resource_fetches_succeeded"),
        },
        "stored_events": len(ev),
        "unique_paths": len(uniq),
        "repeat_ratio": round(len(paths) / max(1, len(uniq)), 1),
        "by_resource_type": dict(by_type.most_common()),
        "static_asset_events": len(static_events),
        "static_asset_share": round(len(static_events) / max(1, len(paths)), 3),
        "static_refetches_wasted": wasted,
        "static_refetch_share_of_stored": round(wasted / max(1, len(paths)), 3),
        "top_repeated": [[n, p] for p, n in repeats.most_common(15)],
        "notes": run.get("notes", []),
    }


def main() -> None:
    out: dict[str, Any] = {}
    for label, rel in RUNS.items():
        p = ROOT / rel
        if not p.exists():
            continue
        a = analyze(json.loads(p.read_text()))
        out[label] = a
        b = a["budget"]
        print(f"=== {label}: actions={b['browser_actions']} observed_http={b['observed_http_requests']} "
              f"cap={b['total_http_requests_cap']}")
        print(f"    by_source={b['http_budget_by_source']}")
        print(f"    stored={a['stored_events']} unique={a['unique_paths']} repeat={a['repeat_ratio']}x "
              f"static_share={a['static_asset_share']} wasted_refetches={a['static_refetches_wasted']} "
              f"({a['static_refetch_share_of_stored']:.0%} of stored)")
        print(f"    by_type={a['by_resource_type']}")
    (ROOT / "evaluation" / "results" / "comfyui_request_breakdown.json").write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
