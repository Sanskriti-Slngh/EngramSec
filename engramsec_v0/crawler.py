#!/usr/bin/env python3
"""EngramSec V0: HTTP-only, GET-only, FIFO breadth-first application mapper.

For explicitly authorized local test applications. Does not use benchmark answer files.
"""
import argparse
from collections import defaultdict, deque
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

USER_AGENT = "EngramSecMapper/0.1 (authorized local benchmark exploration)"
IGNORE_EXTENSIONS = {
    ".css", ".js", ".map", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".webp", ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".mov",
    ".pdf", ".zip", ".gz", ".tar", ".7z", ".rar", ".exe", ".dmg",
}
# GET endpoints can have side effects. Skip obvious dangerous names in a baseline crawler.
DANGEROUS_SEGMENTS = {
    "logout", "signout", "delete", "remove", "destroy", "drop", "reset",
    "shutdown", "disable", "unsubscribe", "purge", "clear", "empty",
}
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
MAX_HTML_BYTES = 1_500_000


def canonical_url(raw: str, base: str) -> str | None:
    """Resolve URL against base, remove fragments/tracking, preserve meaningful queries."""
    if not raw or raw.strip().lower().startswith(("javascript:", "mailto:", "tel:", "data:", "#")):
        return None
    try:
        p = urlsplit(urljoin(base, raw.strip()))
        if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
            return None
        host = p.hostname.lower()
        if ":" in host:  # IPv6
            host = f"[{host}]"
        port = f":{p.port}" if p.port is not None else ""
        pathname = p.path or "/"
        pairs = [
            (k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
            if not (k.lower().startswith("utm_") or k.lower() in TRACKING_KEYS)
        ]
        return urlunsplit((p.scheme.lower(), host + port, pathname, urlencode(sorted(pairs)), ""))
    except (ValueError, UnicodeError):
        return None


def origin(url: str) -> tuple[str, str, int | None]:
    p = urlsplit(url)
    return p.scheme, p.hostname or "", p.port


def is_safe_page(url: str, allowed_origin: tuple[str, str, int | None]) -> bool:
    if origin(url) != allowed_origin:
        return False
    path = urlsplit(url).path.lower()
    if Path(path).suffix in IGNORE_EXTENSIONS:
        return False
    parts = re.split(r"[/_.-]+", path)
    if any(part in DANGEROUS_SEGMENTS for part in parts):
        return False
    for key, _ in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        if key.lower() in {"action", "do", "op", "operation"}:
            # Query actions are unknown; don't issue them in the naive crawler.
            return False
    return True


def route_pattern(url: str) -> str:
    """Route *shape*; not an assertion that two pages implement the same feature."""
    p = urlsplit(url)
    parts = []
    for part in p.path.split("/"):
        part = re.sub(r"(?<![A-Za-z])\d+(?![A-Za-z])", "{id}", part)
        parts.append(part)
    path = "/".join(parts) or "/"
    keys = sorted(set(k for k, _ in parse_qsl(p.query, keep_blank_values=True)))
    return path + ("?" + "&".join(keys) if keys else "")


def feature_name(url: str) -> str:
    """Generic URL-path grouping; intentionally not hardcoded to SiyuCMS."""
    p = urlsplit(url)
    parts = [s for s in p.path.split("/") if s]
    if not parts:
        return "home"
    if len(parts) > 1 and parts[0].lower() == "index":
        parts = parts[1:]
    if not parts:
        return "home"
    first = parts[0].lower()
    name = first.rsplit(".", 1)[0] if "." in first else first
    return name if name and name not in ("index", "home") else "home"


def fetch_html(session: requests.Session, url: str, max_bytes: int = MAX_HTML_BYTES) -> dict:
    """GET one allowed URL. Do not auto-follow redirects or download unbounded bodies."""
    started = time.monotonic()
    try:
        with session.get(
            url, timeout=(4, 10), allow_redirects=False, stream=True,
            headers={"Accept": "text/html,application/xhtml+xml"},
        ) as response:
            result = {
                "http_status": response.status_code,
                "content_type": response.headers.get("Content-Type", ""),
                "redirect_to": response.headers.get("Location") if response.is_redirect else None,
                "body": "",
                "truncated": False,
                "error": None,
            }
            if "html" in result["content_type"].lower() and response.status_code == 200:
                chunks = bytearray()
                for chunk in response.iter_content(chunk_size=16384):
                    if not chunk:
                        continue
                    available = max_bytes - len(chunks)
                    if len(chunk) > available:
                        chunks.extend(chunk[:max(0, available)])
                        result["truncated"] = True
                        break
                    chunks.extend(chunk)
                    if len(chunks) >= max_bytes:
                        result["truncated"] = True
                        break
                result["body"] = chunks.decode(response.encoding or "utf-8", errors="replace")
    except requests.RequestException as exc:
        result = {
            "http_status": None, "content_type": "", "redirect_to": None,
            "body": "", "truncated": False, "error": f"{type(exc).__name__}: {exc}",
        }
    result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
    return result


def parse_page(html: str, page_url: str, allowed_origin: tuple[str, str, int | None]) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    # Ignore large inline debug/code blobs by reading structural elements only.
    raw_links = 0
    eligible_links = 0
    unique_links = {}
    for anchor in soup.select("a[href]"):
        raw_links += 1
        link = canonical_url(anchor.get("href", ""), page_url)
        if link and is_safe_page(link, allowed_origin):
            eligible_links += 1
            unique_links.setdefault(link, (anchor.get_text(" ", strip=True) or anchor.get("title", ""))[:100])
    forms = []
    for form in soup.find_all("form"):
        destination = canonical_url(form.get("action", "") or page_url, page_url)
        fields = []
        for field in form.select("input[name], select[name], textarea[name]"):
            name = field.get("name", "")
            if name:
                fields.append({"name": name[:100], "type": field.get("type", field.name)})
        forms.append({
            "method": form.get("method", "GET").upper(),
            "action": destination if destination and origin(destination) == allowed_origin else None,
            "field_names": fields[:40],
            "submitted": False,
        })
    button_labels = []
    for button in soup.select("button, input[type=submit]"):
        label = button.get_text(" ", strip=True) or button.get("aria-label") or button.get("value") or ""
        if label and label[:70] not in button_labels:
            button_labels.append(label[:70])
    return {
        "title": title[:200], "links": unique_links,
        "raw_link_count": raw_links, "eligible_link_count": eligible_links,
        "unique_link_count": len(unique_links),
        "forms": forms, "buttons": button_labels[:30],
    }


def crawl(start_url: str, max_pages: int = 40, max_depth: int = 4, delay: float = 0.25) -> dict:
    start_url = canonical_url(start_url, start_url)
    if start_url is None:
        raise ValueError("Invalid start URL")
    host = urlsplit(start_url).hostname
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("V0 accepts localhost targets only; use an explicitly authorized local target")
    allowed_origin = origin(start_url)
    queue = deque([(start_url, 0)])
    discovered = {start_url: 0}
    visited = {}
    edge_by_pair = {}
    forms = []
    trace = []
    http_requests = 0
    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    session = requests.Session()
    session.trust_env = False  # localhost should not accidentally use an HTTP proxy
    session.headers.update({"User-Agent": USER_AGENT})

    while queue and http_requests < max_pages:
        url, depth = queue.popleft()
        if url in visited:
            continue
        if depth > max_depth:
            continue
        if http_requests > 0 and delay:
            time.sleep(delay)
        response = fetch_html(session, url)
        http_requests += 1
        page = {
            "id": url, "type": "page", "url": url,
            "depth": depth, "feature": feature_name(url),
            "route_pattern": route_pattern(url), "status": "visited",
            "http_status": response["http_status"], "content_type": response["content_type"],
            "elapsed_ms": response["elapsed_ms"], "truncated": response["truncated"],
            "error": response["error"], "title": "", "forms_count": 0,
            "buttons": [], "links_on_page": 0, "eligible_links_on_page": 0,
            "unique_links_on_page": 0,
        }
        new_targets = 0
        if response["redirect_to"]:
            dst = canonical_url(response["redirect_to"], url)
            if dst and is_safe_page(dst, allowed_origin):
                edge_by_pair.setdefault((url, dst), {"source": url, "target": dst, "type": "redirects_to"})
                if dst not in discovered:
                    discovered[dst] = depth
                    queue.append((dst, depth))
                    new_targets += 1
        elif response["body"]:
            extracted = parse_page(response["body"], url, allowed_origin)
            page.update({
                "title": extracted["title"], "forms_count": len(extracted["forms"]),
                "buttons": extracted["buttons"], "links_on_page": extracted["raw_link_count"],
                "eligible_links_on_page": extracted["eligible_link_count"],
                "unique_links_on_page": extracted["unique_link_count"],
            })
            for form in extracted["forms"]:
                forms.append({"page": url, **form})
            for dst, label in extracted["links"].items():
                edge_by_pair.setdefault((url, dst), {
                    "source": url, "target": dst, "type": "links_to", "label": label,
                })
                if dst not in discovered:
                    discovered[dst] = depth + 1
                    if depth + 1 <= max_depth:
                        queue.append((dst, depth + 1))
                    new_targets += 1
        visited[url] = page
        trace.append({
            "step": http_requests, "url": url, "depth": depth,
            "status": response["http_status"], "new_urls": new_targets,
            "elapsed_ms": response["elapsed_ms"],
        })
        print(f"[{http_requests:02d}/{max_pages}] depth={depth} HTTP={response['http_status']} "
              f"new={new_targets:2d} {url}", flush=True)

    nodes = []
    for url, depth in sorted(discovered.items(), key=lambda item: (item[1], item[0])):
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
    metrics = {
        "requests_sent": http_requests,
        "pages_with_http_200_html": sum(
            n.get("http_status") == 200 and "html" in n.get("content_type", "").lower()
            for n in visited.values()
        ),
        "urls_discovered": len(discovered),
        "urls_visited": len(visited),
        "frontier_unvisited": len(discovered) - len(visited),
        "feature_groups_discovered": len(features),
        "route_patterns_visited": len(set(n["route_pattern"] for n in visited.values())),
        "max_depth_visited": max((n["depth"] for n in visited.values()), default=0),
        "links_observed_raw": sum(n.get("links_on_page", 0) for n in visited.values()),
        "links_eligible_raw": sum(n.get("eligible_links_on_page", 0) for n in visited.values()),
        "links_unique_within_page": sum(n.get("unique_links_on_page", 0) for n in visited.values()),
        "forms_observed": len(forms),
        "elapsed_seconds": round(time.monotonic() - t0, 2),
    }
    metrics["duplicate_links_within_pages"] = (
        metrics["links_eligible_raw"] - metrics["links_unique_within_page"]
    )
    metrics["links_filtered_out"] = (
        metrics["links_observed_raw"] - metrics["links_eligible_raw"]
    )
    metrics["new_urls_per_request"] = round(len(discovered) / max(1, http_requests), 3)
    return {
        "schema_version": "0.1", "run_started_utc": started_at,
        "start_url": start_url, "policy": "fifo_breadth_first",
        "limits": {"max_pages": max_pages, "max_depth": max_depth, "delay_seconds": delay},
        "notes": [
            "HTTP GET-only; JavaScript is not executed; forms are never submitted.",
            "Feature groups are URL-path heuristics, not verified semantic features.",
            "Unvisited means discovered but not fetched; undiscovered functionality is unknown.",
            "No benchmark metadata, hidden target files, or vulnerability hints were used.",
        ],
        "metrics": metrics,
        "features": dict(sorted(features.items())),
        "nodes": nodes,
        "edges": list(edge_by_pair.values()),
        "forms": forms,
        "trace": trace,
    }


def save_outputs(graph: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "graph_a.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
    (directory / "metrics.json").write_text(json.dumps(graph["metrics"], indent=2), encoding="utf-8")
    (directory / "trace.jsonl").write_text(
        "".join(json.dumps(step) + "\n" for step in graph["trace"]), encoding="utf-8"
    )
    report = ["# EngramSec V0: Graph A report", "", f"Start URL: `{graph['start_url']}`", "", "## Metrics", ""]
    report.extend(f"- **{k}**: {v}" for k, v in graph["metrics"].items())
    report.extend(["", "## Feature groups (URL heuristics)", ""])
    report.extend(
        f"- **{name}**: {data['visited']}/{data['discovered']} URLs visited"
        for name, data in graph["features"].items()
    )
    (directory / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    # Compact route-template network. Open graph_a.mmd in a Mermaid preview.
    patterns = sorted({node["route_pattern"] for node in graph["nodes"]})
    keys = {p: f"r{i}" for i, p in enumerate(patterns)}
    dotless = lambda x: x.replace('"', "'")[:100]
    mermaid = ["flowchart LR"]
    for pattern in patterns:
        mermaid.append(f'  {keys[pattern]}["{dotless(pattern)}"]')
    seen = set()
    node_routes = {node["id"]: node["route_pattern"] for node in graph["nodes"]}
    for edge in graph["edges"]:
        src = node_routes.get(edge["source"])
        dst = node_routes.get(edge["target"])
        if not src or not dst or src == dst:
            continue
        pair = (src, dst)
        if pair not in seen:
            mermaid.append(f"  {keys[src]} --> {keys[dst]}")
            seen.add(pair)
    (directory / "graph_a.mmd").write_text("\n".join(mermaid) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Authorized localhost application starting URL")
    parser.add_argument("--max-pages", type=int, default=40)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--out", type=Path, default=Path("outputs/v0_bfs"))
    args = parser.parse_args()
    if args.max_pages < 1 or args.max_depth < 0 or args.delay < 0:
        parser.error("Invalid budget/depth/delay")
    graph = crawl(args.url, args.max_pages, args.max_depth, args.delay)
    save_outputs(graph, args.out)
    print("\n=== QUANTITATIVE SUMMARY ===")
    for k, v in graph["metrics"].items():
        print(f"  {k}: {v}")
    print(f"\nFiles saved to: {args.out.resolve()}")


if __name__ == "__main__":
    main()
