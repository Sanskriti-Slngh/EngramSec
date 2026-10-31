#!/usr/bin/env python3
"""Offline evaluator for the Larkspur Library transfer fixture.

Post-run only; never imported by Agent 1. Ground truth here is the fixture's
design (development_apps/transfer_library.py) plus the server's own request
log, written by the experiment runner after each run. Counts are reported per
category; no category is substituted for another.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from development_apps.transfer_library import AUTHORS, COLLECTIONS, EXHIBITS, ITEMS  # noqa: E402

DESK = ["/desk", "/desk/reserve", "/desk/loans", "/desk/cards", "/desk/shelf", "/desk/tools",
        "/desk/component", "/desk/frame", "/desk/frame-inner", "/desk/hidden", "/desk/rows"]
DOCUMENTS = (
    ["/", "/authors", "/collections", "/archive", "/archive/annual-report", "/archive/report-summary",
     "/archive/slow-index", "/account", "/account/list"]
    + [f"/catalog?page={n}" for n in range(1, 6)]
    + [f"/items/{n}" for n in range(1, ITEMS + 1)]
    + [f"/authors/{a}" for a in AUTHORS]
    + [f"/collections/view?name={c}" for c in COLLECTIONS]
    + DESK + [f"/exhibits/{e}" for e in EXHIBITS]
)
STATIC = ["/static/site.css", "/static/item.css", "/static/item.js", "/static/paper.png"] + [
    f"/items/{n}/cover.svg" for n in range(1, ITEMS + 1)]
# Links that exist only beyond a response bound or inside a malformed response.
BOUNDARY = {
    "/archive/report-appendix": "beyond the 1 MB body bound of a 3.5 MB page",
    "/archive/legacy-entry": "inside a response with invalid Content-Length framing",
    "/archive/feed-entry": "inside a truncated gzip stream",
    "/archive/slow-entry": "first bytes of a 30 s trickle",
}
# Action-triggered functionality: (id, method, path prefix, how it is wired).
FUNCTIONALITY = [
    ("F1 reading-list save", "POST", "/api/reading-list", "snapshot button + fetch POST", ("/api/reading-list/clear",)),
    ("F2 catalog search", "GET", "/catalog/search", "snapshot GET form", ()),
    ("F3 loan status", "GET", "/api/loans/status", "snapshot button, first handler", ()),
    ("F4 loan eligibility", "GET", "/api/loans/eligibility", "same button, handler replaced, DOM unchanged", ()),
    ("F5 study-slot reserve", "GET", "/api/slots/reserve", "<div> listener created by an action", ()),
    ("F6 exhibit card", "GET", "/exhibits/", "<div> listener present at load (navigation)", ()),
    ("F7 branch holdings", "GET", "/api/holdings", "listener inside an open shadow root", ("/api/holdings/reserve",)),
    ("F8 citation", "GET", "/api/citation", "listener inside a same-origin frame", ()),
    ("F9 call-number row", "GET", "/api/rows/", "row family (400 rows, one handler)", ()),
]
EXPECTED_ABSENT = [
    ("X1 delegated shelf item", "GET", "/api/shelf/", "document-level delegation (not attributable)"),
    ("X2 closed-shadow holdings", "GET", "/api/holdings/reserve", "closed shadow root (not addressable)"),
    ("X3 dangerous clear", "POST", "/api/reading-list/clear", "MUST NOT happen: dangerous label"),
    ("X4 hidden listener", "GET", "/api/hidden/", "MUST NOT happen: not rendered"),
]


def norm(path: str, query: str) -> str:
    keep = {"page", "name"}
    pairs = [(k, v[0]) for k, v in parse_qs(query).items() if k in keep]
    return path + ("?" + "&".join(f"{k}={v}" for k, v in sorted(pairs)) if pairs else "")


def matches(event_method: str, event_path: str, method: str, prefix: str, excluded: tuple[str, ...] = ()) -> bool:
    return event_method == method and event_path.startswith(prefix) and not any(event_path.startswith(x) for x in excluded)


def evaluate(run_dir: Path) -> dict:
    graph = json.loads((run_dir / "graph_a.json").read_text())
    server = json.loads((run_dir / "server_log.json").read_text())
    metrics = graph["metrics"]
    run = json.loads((run_dir / "run.json").read_text()) if (run_dir / "run.json").exists() else None
    transitions = run["transitions"] if run else []
    replays = run["replays"] if run else []
    log = server["log"]
    ok = [e for e in log if 200 <= e["status"] < 300 and e["method"] == "GET"]
    reached = {norm(e["path"], e.get("query", "")) for e in ok}
    reached_by = {client: {norm(e["path"], e.get("query", "")) for e in ok if e["client"] == client}
                  for client in ("browser", "passive")}
    docs = set(DOCUMENTS)
    static = set(STATIC)
    references = {r["url"] for r in graph["resource_evidence"] if r.get("url")}
    reference_paths = {urlsplit(u).path for u in references}
    boundary = {path: {"referenced": path in reference_paths, "requested": any(e["path"] == path for e in log),
                       "why": why} for path, why in BOUNDARY.items()}
    # Functionality: executed (an observed transition issued it), replay-validated
    # (a validated replay of that transition issued it again).
    validated_ids = {r["transition_id"] for r in replays if r["status"] == "replay_validated"}
    replay_net = {}
    for r in replays:
        if r["status"] == "replay_validated":
            replay_net.setdefault(r["transition_id"], []).extend(r.get("network", []))

    def issued(network, method, prefix, excluded=()):
        return any(matches(e["method"], urlsplit(e["url"]).path, method, prefix, excluded) for e in network)

    functionality = {}
    for name, method, prefix, wiring, excluded in FUNCTIONALITY:
        hits = [t for t in transitions if t["status"] != "failed" and (
            issued(t.get("network", []), method, prefix, excluded) or (
                method == "GET" and prefix.startswith("/exhibits/") and t["action"].get("provenance") == "observed_listener"
                and any(urlsplit(e["url"]).path.startswith(prefix) and e.get("resource_type") == "document" for e in t.get("network", []))))]
        replayed = [t for t in hits if t["id"] in validated_ids and issued(replay_net.get(t["id"], []), method, prefix, excluded)]
        functionality[name] = {
            "wiring": wiring, "executed": bool(hits), "replay_validated": bool(replayed),
            "via": sorted({(t["action"].get("provenance") or "snapshot") + ("+revision" if t["action"].get("behavior_revision") else "")
                           for t in hits}),
            "server_confirmed": any(e["client"] == "browser" and matches(e["method"], e["path"], method, prefix, excluded) for e in log),
        }
    absent = {name: {"why": why,
                     "occurred_by_browser_action": any(e["client"] == "browser" and matches(e["method"], e["path"], method, prefix) for e in log),
                     "passive_requests": sum(e["client"] == "passive" and matches(e["method"], e["path"], method, prefix) for e in log)}
              for name, method, prefix, why in EXPECTED_ABSENT}
    by_client = server["requests_by_client"]
    browser_actions = metrics.get("browser_actions") or 1
    executed = sum(v["executed"] for v in functionality.values())
    replayed = sum(v["replay_validated"] for v in functionality.values())
    graph_evidence = Counter((c["claim_type"], c["complete"]) for c in graph["connection_evidence"])
    spider_attempts = [r for r in graph["resource_evidence"] if r.get("status") in {"fetched", "failed"}]
    return {
        "references_discovered": len(references),
        "documents_reached_2xx": f"{len(reached & docs)}/{len(docs)}",
        "documents_reached_by_browser": len(reached_by["browser"] & docs),
        "documents_reached_by_passive": len(reached_by["passive"] & docs),
        "static_fetched_2xx": f"{len(reached & static)}/{len(static)}",
        "boundary_links": boundary,
        "requests_by_client": by_client,
        "requests_total": sum(v["requests"] for v in by_client.values()),
        "bytes_total": sum(v["bytes"] for v in by_client.values()),
        "passive_wire_bytes_agent_reported": metrics.get("passive_wire_bytes"),
        "server_events": server["events"],
        "sentinel_hits": len(server["sentinel_hits"]),
        "redirect_trap_requests": sum(1 for e in log if e["path"].startswith("/stacks/")),
        "elapsed_seconds": metrics.get("elapsed_seconds"),
        "python_peak_rss_mb": metrics.get("python_peak_rss_mb"),
        "browser_actions": metrics.get("browser_actions"),
        "transitions_observed": metrics.get("transitions_observed"),
        "functionality_executed": f"{executed}/{len(FUNCTIONALITY)}",
        "functionality_replay_validated": f"{replayed}/{len(FUNCTIONALITY)}",
        "functionality_per_100_actions": round(100 * executed / browser_actions, 2),
        "functionality": functionality,
        "expected_absent": absent,
        "replays": f"{metrics.get('replay_success_numerator')}/{metrics.get('replay_success_denominator')}",
        "distinct_action_request_structures": len({
            (e["method"], urlsplit(e["url"]).path.rstrip("0123456789"), tuple(e.get("parameter_names") or []))
            for t in transitions if t["status"] != "failed" for e in t.get("network", [])
            if e.get("resource_type") in {"xhr", "fetch"} or e["method"] not in {"GET", "HEAD"}}),
        "graph_connections_missing_evidence": metrics.get("graph_connections_missing_evidence"),
        "graph_connections_total": metrics.get("graph_connections_total"),
        "connection_claims": {f"{k}:{'complete' if c else 'incomplete'}": v for (k, c), v in sorted(graph_evidence.items())},
        "incorrect_state_merges": metrics.get("incorrect_state_merges"),
        "behavior_divergent_groups": metrics.get("behavior_divergent_groups"),
        "grouped_states": metrics.get("grouped_states"),
        "spider_attempts_without_channel": sum(1 for r in spider_attempts if r.get("channel") is None),
        "spider_body_status": metrics.get("spider_body_status"),
        "browser_body_status": metrics.get("browser_body_status"),
        "passive_cookie_updates": metrics.get("passive_cookie_updates"),
        "http_budget_by_source": metrics.get("http_budget_by_source"),
        "listener": {k: metrics.get(k) for k in (
            "listener_observations", "listener_observation_errors", "listener_observation_ms", "listener_cdp_calls",
            "listener_candidates_distinct", "listener_candidates_executed", "handler_revisions_observed",
            "handler_revisits_executed", "listener_skipped")},
        "behavior_evidence_summary": graph.get("behavior_evidence", {}).get("summary"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    results = {}
    for run_dir in sorted(p.parent for p in args.root.glob("*/server_log.json")):
        results[run_dir.name.removeprefix("adaptive_readiness_")] = evaluate(run_dir)
    args.out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    for name, r in results.items():
        print(f"{name:10} docs={r['documents_reached_2xx']} static={r['static_fetched_2xx']} refs={r['references_discovered']} "
              f"req={r['requests_total']} bytes={r['bytes_total']:,} func={r['functionality_executed']} "
              f"replayed={r['functionality_replay_validated']} replays={r['replays']} missing={r['graph_connections_missing_evidence']} "
              f"merges={r['incorrect_state_merges']} sentinel={r['sentinel_hits']} trap={r['redirect_trap_requests']} "
              f"events={r['server_events']} rss={r['python_peak_rss_mb']} t={r['elapsed_seconds']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
