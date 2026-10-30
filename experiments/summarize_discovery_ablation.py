#!/usr/bin/env python3
"""Offline comparison of the discovery ablation (arms A-D) on Crawl Maze.

Post-run only; never imported by Agent 1. The raw score is the historical
strict-2xx `any_fetch` definition over all 91 expected paths. Supported-case
recall (84 paths, see CRAWLMAZE_64_MISSING_ROOT_CAUSES.md) and any-status
request-surface discovery are reported as separate columns, never substituted.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from audit_crawlmaze_missing import FACTS, RunEvidence, norm, ok

CATEGORIES = ("html", "javascript", "css", "headers", "misc")


def category(path: str) -> str:
    return path.split("/")[2] if path.startswith("/test/") else "javascript"


def summarize(run_dir: Path, expected: list[str]) -> tuple[dict, dict]:
    run = RunEvidence(run_dir)
    graph = run.graph
    metrics = run.metrics
    supported = [p for p in expected if FACTS[p]["supported"] == "yes"]
    hits = {p for p in expected if run.reached(p)}
    sent_any = {p for p in expected if p in hits or run.events_by_path.get(norm(p))
                or any(r.get("status") in {"fetched", "failed"} for r in run.refs_by_path.get(norm(p), []))}
    observed = sent_any | {p for p in expected if run.refs_by_path.get(norm(p))}
    # Parent (container) funnel over distinct containers of supported cases.
    containers = sorted({FACTS[p]["container"] for p in supported})
    funnel = Counter()
    for c in containers:
        key = norm(c)
        refs = run.refs_by_path.get(key, [])
        visited = bool(run.states_by_path.get(key))
        fetched = any(r.get("status") == "fetched" and ok(r.get("http_status")) for r in refs) or any(
            ok(e.get("status")) for e in run.events_by_path.get(key, []))
        admitted = any(r.get("queue_decision") in {"admitted", "speculative_admitted"} for r in refs)
        discovered = bool(refs) or key in run.control_targets or visited or fetched
        funnel["discovered"] += discovered
        funnel["admitted_to_spider"] += admitted
        funnel["fetched_or_loaded_2xx"] += fetched
        funnel["browser_visited"] += visited
        funnel["reached_any_way"] += fetched or visited
    # Safe controls executed vs unexecuted (distinct signatures).
    safe_controls = {c["signature"] for o in run.run["observations"] for c in o.get("controls", []) if c.get("safe")}
    executed = {t["action"]["signature"] for t in run.run["transitions"]}
    replay_actions = sum(r.get("browser_actions") or 0 for r in run.run.get("replays", []))
    statuses = Counter(r.get("status") for r in graph.get("resource_evidence", []))
    decisions = Counter(r.get("queue_decision") for r in graph.get("resource_evidence", []))
    # Graph A evidence audit.
    refs = graph.get("resource_evidence", [])
    spider_attempts = [r for r in refs if r.get("status") in {"fetched", "failed"}]
    surfaces = graph.get("request_surfaces", [])
    non_get_observed = {s["url"] for s in surfaces if s["method"] not in {"GET", "UNKNOWN"}
                        and not s["sent_by"] and s["observed_as"]}
    spider_get_urls = {s["url"] for s in surfaces if s["method"] == "GET" and any(x.startswith("spider_") for x in s["sent_by"])}
    browser_urls = {norm(urlsplit(o["url"]).path) for o in run.run["observations"]}
    transition_urls = {norm(urlsplit((run.obs.get(t.get("result_observation_id")) or {}).get("url", "")).path)
                       for t in run.run["transitions"]}
    passive_paths = {norm(urlsplit(r["url"]).path) for r in spider_attempts if r.get("channel") == "passive_document"}
    validated = {r["transition_id"] for r in run.run.get("replays", []) if r.get("status") == "replay_validated"}
    evidence_audit = {
        "spider_attempts_without_channel_label": sum(1 for r in spider_attempts if r.get("channel") is None),
        "passive_only_documents_as_ui_transitions": len((passive_paths - browser_urls) & transition_urls),
        "spider_get_for_observed_only_non_get_surface": len(non_get_observed & spider_get_urls),
        "surfaces_marked_replay_verified": sum(1 for s in surfaces if s.get("in_replay_validated_workflow")),
        "replay_validated_transitions": len(validated),
        "observed_only_records_with_spider_attempt": sum(
            1 for r in refs if str(r.get("queue_decision", "")).startswith("observed_only_")
            and any(a.get("url") == r.get("url") for a in spider_attempts)),
    }
    row = {
        "evidence_audit": evidence_audit,
        "raw_2xx_91": len(hits),
        "supported_2xx_84": len(hits & set(supported)),
        "request_surface_any_status_91": len(sent_any),
        "observed_or_sent_91": len(observed),
        "by_category": {c: f"{sum(1 for p in hits if category(p) == c)}/{sum(1 for p in expected if category(p) == c)}" for c in CATEGORIES},
        "parent_funnel_supported_containers": {"containers": len(containers), **funnel},
        "safe_controls_distinct": len(safe_controls),
        "safe_controls_executed": len(safe_controls & executed),
        "safe_controls_unexecuted": len(safe_controls - executed),
        "browser_actions": metrics.get("browser_actions"),
        "transitions_observed": metrics.get("transitions_observed"),
        "restoration_actions": metrics.get("restoration_actions"),
        "discovery_root_reloads": metrics.get("discovery_root_reloads"),
        "verification_root_reloads": metrics.get("verification_root_reloads"),
        "replay_browser_actions": replay_actions,
        "replays_validated": metrics.get("replay_success_numerator"),
        "replays_attempted": metrics.get("replay_success_denominator"),
        "untested_transitions": metrics.get("replay_untested_paths"),
        "http_total": metrics.get("total_http_budget_used"),
        "http_by_source": metrics.get("http_budget_by_source"),
        "http_blocked": metrics.get("total_http_budget_blocked"),
        "http_overrun": metrics.get("http_redirect_budget_overrun"),
        "resource_status_counts": dict(statuses),
        "observed_only_decisions": {k: v for k, v in decisions.items() if str(k).startswith("observed_only_")},
        "request_surface_summary": graph.get("request_surface_summary"),
        "graph_connections_missing_evidence": metrics.get("graph_connections_missing_evidence"),
        "graph_connections_total": metrics.get("graph_connections_total"),
        "incorrect_state_merges": metrics.get("incorrect_state_merges"),
        "effective_resource_budgets": metrics.get("effective_resource_budgets"),
        "elapsed_seconds": metrics.get("elapsed_seconds"),
    }
    # How each hit was reached: channel and the general extraction mechanism.
    attribution = {}
    for p in hits:
        key = norm(p)
        browser = any(ok(e.get("status")) for e in run.events_by_path.get(key, []))
        refs = run.refs_by_path.get(key, [])
        channels = sorted({r.get("channel") or "typed_resource" for r in refs if r.get("status") == "fetched" and ok(r.get("http_status"))})
        sources = sorted({f"{r.get('source_type')}:{r.get('source')}|{r.get('confidence') or 'observed_literal'}" for r in refs})
        attribution[p] = {"browser_2xx": browser, "spider_channels": channels, "extracted_by": sources}
    return row, {"hits": sorted(hits), "attribution": attribution}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--expected", type=Path, default=Path("/private/tmp/security-crawl-maze/blueprints/utils/resources/expected-results.json"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    expected = json.loads(args.expected.read_text())
    rows, details = {}, {}
    for run_dir in sorted(p.parent for p in args.root.glob("*/graph_a.json")):
        name = run_dir.name.removeprefix("adaptive_readiness_")
        rows[name], details[name] = summarize(run_dir, expected)
    baseline = next((n for n in rows if n.startswith("A")), None)
    deltas = {}
    if baseline:
        base_hits = set(details[baseline]["hits"])
        for name, d in details.items():
            gained = sorted(set(d["hits"]) - base_hits)
            lost = sorted(base_hits - set(d["hits"]))
            mechanisms = Counter()
            for p in gained:
                a = d["attribution"][p]
                via = "browser" if a["browser_2xx"] else "+".join(a["spider_channels"]) or "?"
                mech = sorted({s.split("|")[0].split(":", 1)[1] + ("" if s.endswith("observed_literal") else f" ({s.split('|')[1]})")
                               for s in a["extracted_by"]})
                mechanisms[f"{via} via {', '.join(mech[:2]) or 'browser load'}"] += 1
            deltas[name] = {"gained_vs_A": len(gained), "lost_vs_A": len(lost), "gain_mechanisms": dict(mechanisms)}
    payload = {"note": "Offline evaluator; strict-2xx raw score is the historical definition.",
               "rows": rows, "deltas_vs_A": deltas}
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    for name, r in rows.items():
        f = r["parent_funnel_supported_containers"]
        print(f"{name:6} raw={r['raw_2xx_91']:2}/91 sup={r['supported_2xx_84']:2}/84 any={r['request_surface_any_status_91']:2} "
              f"obs={r['observed_or_sent_91']:2} cat={r['by_category']} parents(disc/adm/fetch/visit/any)="
              f"{f['discovered']}/{f['admitted_to_spider']}/{f['fetched_or_loaded_2xx']}/{f['browser_visited']}/{f['reached_any_way']} of {f['containers']} "
              f"http={r['http_total']} replay={r['replays_validated']}/{r['replays_attempted']} missing={r['graph_connections_missing_evidence']}")
    for name, d in deltas.items():
        print(name, d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
