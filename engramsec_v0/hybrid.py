#!/usr/bin/env python3
"""EngramSec V1: deterministic, bounded BFS/DFS hybrid for authorized localhost sites.

Requires crawler.py (unchanged V0) in the same directory. Makes only HTTP GET
requests, never submits forms, and never accesses benchmark source files.
"""
import argparse
from collections import defaultdict, deque
from datetime import datetime, timezone
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
from crawler import (
    USER_AGENT, canonical_url, origin, is_safe_page, route_pattern,
    feature_name, fetch_html, parse_page, save_outputs,
)


def signature(form):
    """Structural form identity; not semantic equivalence."""
    return (
        form.get("method", "GET"), form.get("action"),
        tuple((f.get("name", ""), f.get("type", "")) for f in form.get("field_names", [])),
    )


def crawl_hybrid(start_url: str, max_pages: int = 40, max_depth: int = 4,
                 delay: float = 0.25, probe_hops: int = 2,
                 immediate_redirect: bool = True) -> dict:
    if max_pages < 1 or max_depth < 0 or delay < 0 or probe_hops < 0:
        raise ValueError("Invalid budget, depth, delay, or probe length")
    start_url = canonical_url(start_url, start_url)
    if not start_url:
        raise ValueError("Invalid URL")
    if urlsplit(start_url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("V1 only accepts explicitly authorized localhost targets")
    allowed = origin(start_url)
    if not is_safe_page(start_url, allowed):
        raise ValueError("Unsafe starting URL")

    # FIFO exploration remains the default. Short DFS probes can temporarily
    # preempt it, but ALL newly discovered URLs remain in the global frontier.
    bfs = deque([(start_url, 0)])
    probes = []  # LIFO tuples: (url, depth, further_probe_hops, selection_reason)
    discovered = {start_url: 0}
    visited = {}
    visited_patterns = set()
    visited_features = set()
    distinct_forms = set()
    edge_by_pair = {}
    forms = []
    trace = []
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": USER_AGENT})
    t0 = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()

    while (probes or bfs) and len(trace) < max_pages:
        if probes:
            url, depth, remaining, selected_by = probes.pop()
        else:
            url, depth = bfs.popleft()
            remaining, selected_by = probe_hops, "bfs"
        if url in visited or depth > max_depth:
            continue
        if trace and delay:
            time.sleep(delay)
        response = fetch_html(session, url)
        page = {
            "id": url, "type": "page", "url": url, "depth": depth,
            "feature": feature_name(url), "route_pattern": route_pattern(url),
            "status": "visited", "http_status": response["http_status"],
            "content_type": response["content_type"], "elapsed_ms": response["elapsed_ms"],
            "truncated": response["truncated"], "error": response["error"],
            "title": "", "forms_count": 0, "buttons": [], "links_on_page": 0,
            "eligible_links_on_page": 0, "unique_links_on_page": 0,
        }
        patterns_before = set(visited_patterns)
        new_routes_from_this_page = set()
        new_form_signatures = 0
        new_targets = 0
        eligible_child_urls = []
        redirect_target = None

        if response["redirect_to"]:
            dst = canonical_url(response["redirect_to"], url)
            if dst and is_safe_page(dst, allowed):
                redirect_target = dst
                edge_by_pair.setdefault((url, dst), {"source": url, "target": dst, "type": "redirects_to"})
                if dst not in discovered:
                    discovered[dst] = depth  # redirect is not a link-click depth
                    bfs.append((dst, depth))
                    new_targets += 1
        elif response["body"]:
            extracted = parse_page(response["body"], url, allowed)
            page.update({
                "title": extracted["title"],
                "forms_count": len(extracted["forms"]),
                "buttons": extracted["buttons"],
                "links_on_page": extracted["raw_link_count"],
                "eligible_links_on_page": extracted["eligible_link_count"],
                "unique_links_on_page": extracted["unique_link_count"],
            })
            for form in extracted["forms"]:
                forms.append({"page": url, **form})
                sig = signature(form)
                if sig not in distinct_forms:
                    distinct_forms.add(sig)
                    new_form_signatures += 1
            for dst, label in extracted["links"].items():
                edge_by_pair.setdefault((url, dst), {
                    "source": url, "target": dst, "type": "links_to", "label": label,
                })
                if dst not in discovered:
                    discovered[dst] = depth + 1
                    if depth + 1 <= max_depth:
                        bfs.append((dst, depth + 1))
                    new_targets += 1
                if depth + 1 <= max_depth and dst not in visited:
                    eligible_child_urls.append(dst)
                pattern = route_pattern(dst)
                if pattern not in patterns_before:
                    new_routes_from_this_page.add(pattern)

        visited[url] = page
        visited_patterns.add(page["route_pattern"])
        visited_features.add(page["feature"])
        probe_candidate = None
        reason = ""

        # Follow a real 3xx Location promptly, without treating it as a new
        # link depth or dropping it from the global FIFO queue.
        if immediate_redirect and redirect_target and redirect_target not in visited:
            probes.append((redirect_target, discovered[redirect_target],
                           max(remaining - 1, 0), "follow_redirect"))
            probe_candidate, reason = redirect_target, "follow_redirect"

        # Otherwise explore at most one promising child, for at most
        # --probe-hops consecutive steps. Never probe out of the homepage.
        elif depth > 0 and remaining > 0 and eligible_child_urls and (
            new_form_signatures > 0 or new_targets > 0
        ):
            # Signals are available *before* fetching the candidate: URL route
            # template and feature path. We never infer a form from an unseen page.
            # Scores break ties by discovery order, making runs deterministic.
            def priority(dst):
                return (
                    int(route_pattern(dst) not in visited_patterns),
                    int(feature_name(dst) not in visited_features),
                )
            candidate = max(eligible_child_urls, key=priority)
            probes.append((candidate, discovered[candidate], remaining - 1,
                           "novel_form" if new_form_signatures else "new_url"))
            probe_candidate = candidate
            reason = "novel_form" if new_form_signatures else "new_url"

        trace.append({
            "step": len(trace) + 1, "url": url, "depth": depth,
            "status": response["http_status"], "new_urls": new_targets,
            "elapsed_ms": response["elapsed_ms"], "selection": selected_by,
            "new_distinct_forms": new_form_signatures,
            "new_child_route_patterns": len(new_routes_from_this_page),
            "probe_target": probe_candidate, "probe_reason": reason,
        })
        print(
            f"[{len(trace):02d}/{max_pages}] {selected_by:>15} depth={depth} "
            f"HTTP={response['http_status']} +urls={new_targets:2d} "
            f"+forms={new_form_signatures} {url}", flush=True,
        )

    nodes = []
    for url, depth in sorted(discovered.items(), key=lambda x: (x[1], x[0])):
        if url in visited:
            nodes.append(visited[url])
        else:
            nodes.append({
                "id": url, "type": "page", "url": url, "depth": depth,
                "feature": feature_name(url), "route_pattern": route_pattern(url),
                "status": "discovered_not_visited", "http_status": None,
            })
    features = defaultdict(lambda: {"discovered": 0, "visited": 0, "example_urls": []})
    for node in nodes:
        f = features[node["feature"]]
        f["discovered"] += 1
        f["visited"] += (node["status"] == "visited")
        if len(f["example_urls"]) < 5:
            f["example_urls"].append(node["url"])

    m = {
        "requests_sent": len(trace),
        "pages_with_http_200_html": sum(
            n.get("http_status") == 200 and "html" in n.get("content_type", "").lower()
            for n in visited.values()
        ),
        "urls_discovered": len(discovered),
        "urls_visited": len(visited),
        "frontier_unvisited": len(discovered) - len(visited),
        "feature_groups_discovered": len(features),
        "route_patterns_visited": len(visited_patterns),
        "max_depth_visited": max((n["depth"] for n in visited.values()), default=0),
        "links_observed_raw": sum(n.get("links_on_page", 0) for n in visited.values()),
        "links_eligible_raw": sum(n.get("eligible_links_on_page", 0) for n in visited.values()),
        "links_unique_within_page": sum(n.get("unique_links_on_page", 0) for n in visited.values()),
        "forms_observed": len(forms),
        "distinct_form_signatures": len(distinct_forms),
        "probe_requests": sum(e["selection"] != "bfs" for e in trace),
        "elapsed_seconds": round(time.monotonic() - t0, 2),
    }
    m["duplicate_links_within_pages"] = m["links_eligible_raw"] - m["links_unique_within_page"]
    m["links_filtered_out"] = m["links_observed_raw"] - m["links_eligible_raw"]
    m["new_urls_per_request"] = round((len(discovered) - 1) / max(1, len(trace)), 3)
    return {
        "schema_version": "0.1", "run_started_utc": started_at,
        "start_url": start_url, "policy": "bounded_novelty_probe_hybrid",
        "limits": {
            "max_pages": max_pages, "max_depth": max_depth,
            "delay_seconds": delay, "probe_hops": probe_hops,
            "immediate_redirect": immediate_redirect,
        },
        "notes": [
            "HTTP GET only, no JavaScript, no form submissions.",
            "BFS frontier with at most one immediate child probe per page and bounded probe length.",
            "Redirects are followed within the same allowed origin, never cross-origin.",
            "URL route patterns and form signatures are structural proxies, not verified capabilities.",
            "No benchmark source, verifier files, or challenge metadata are accessed.",
        ],
        "metrics": m,
        "features": dict(sorted(features.items())),
        "nodes": nodes, "edges": list(edge_by_pair.values()),
        "forms": forms, "trace": trace,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", required=True)
    p.add_argument("--max-pages", type=int, default=40)
    p.add_argument("--max-depth", type=int, default=4)
    p.add_argument("--delay", type=float, default=0.25)
    p.add_argument("--probe-hops", type=int, default=2)
    p.add_argument("--immediate-redirect", action=argparse.BooleanOptionalAction,
                   default=True, help="Follow a redirect ahead of global BFS queue")
    p.add_argument("--out", type=Path, default=Path("outputs/v1_hybrid"))
    a = p.parse_args()
    try:
        graph = crawl_hybrid(a.url, a.max_pages, a.max_depth, a.delay,
                             a.probe_hops, a.immediate_redirect)
    except ValueError as exc:
        p.error(str(exc))
    save_outputs(graph, a.out)
    print("\n=== HYBRID SUMMARY ===")
    for name, value in graph["metrics"].items():
        print(f"  {name}: {value}")
    print("Saved to:", a.out.resolve())


if __name__ == "__main__":
    main()
