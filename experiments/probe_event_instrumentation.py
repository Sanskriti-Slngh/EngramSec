#!/usr/bin/env python3
"""Passive feasibility probe for event-driven browser instrumentation.

Re-opens states that a finished Agent 1 run already reached (from its Graph A),
with an init script that records (a) elements given input listeners through
addEventListener and (b) URLs handed to JS navigation/network APIs. Nothing is
clicked, typed or submitted. Reports how much of that is invisible to Agent 1's
snapshot extractor and to the run's recorded requests/references.

This is a measurement for deciding whether to build the architecture; it does not
feed Agent 1 and never reads evaluator answers.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import sync_playwright

HOOK = r"""
(() => {
  const log = window.__engramProbe = {listeners: [], urls: []};
  const note = (api, value) => { try { log.urls.push([api, String(value)]); } catch (e) {} };
  const INPUT = new Set(['click','dblclick','mousedown','mouseup','pointerdown','pointerup','keydown','keyup','submit','change','input','touchstart','contextmenu']);
  const add = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, fn, opts) {
    if (INPUT.has(type) && this instanceof Element) log.listeners.push([this, type]);
    return add.call(this, type, fn, opts);
  };
  const wrap = (obj, name, api, idx = 0) => {
    const orig = obj[name];
    if (typeof orig !== 'function') return;
    obj[name] = function (...args) { note(api, args[idx] && args[idx].url ? args[idx].url : args[idx]); return orig.apply(this, args); };
  };
  wrap(window, 'fetch', 'fetch');
  wrap(XMLHttpRequest.prototype, 'open', 'xhr', 1);
  wrap(window, 'open', 'window.open');
  wrap(History.prototype, 'pushState', 'pushState', 2);
  wrap(History.prototype, 'replaceState', 'replaceState', 2);
  wrap(Location.prototype, 'assign', 'location.assign');
  wrap(Location.prototype, 'replace', 'location.replace');
  if (navigator.sendBeacon) wrap(Navigator.prototype, 'sendBeacon', 'sendBeacon');
  for (const C of ['WebSocket', 'EventSource', 'Worker', 'SharedWorker']) {
    const Orig = window[C];
    if (!Orig) continue;
    window[C] = new Proxy(Orig, {construct(t, args) { note(C, args[0]); return new t(...args); }});
  }
})();
"""

# Mirrors the semantic part of Agent 1's snapshot control selector.
SNAPSHOT_SELECTOR = (
    "a[href],button,input,select,textarea,summary,[role=button],[role=link],[role=tab],[role=menuitem],"
    "[onclick],[ondblclick],[oncontextmenu],[onmouseover],[onmouseenter],[onfocus],[onkeydown],"
    "[tabindex],[contenteditable],[data-action],[aria-controls],[popovertarget]"
)

COLLECT = """
sel => {
  const log = window.__engramProbe || {listeners: [], urls: []};
  const hidden = new Set();
  for (const [el, type] of log.listeners) {
    if (!el.isConnected || el === document.body || el === document.documentElement) continue;
    if (!el.matches(sel) && !el.closest(sel)) hidden.add(el);
  }
  return {listener_elements: new Set(log.listeners.map(x => x[0])).size, listener_only: hidden.size,
          urls: log.urls, hrefs: [...document.querySelectorAll('a[href]')].map(a => a.href)};
}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-states", type=int, default=60)
    parser.add_argument("--dwell-ms", type=int, default=1500)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_text())
    origin = urlsplit(graph["nodes"]["states"][0]["url"]).netloc
    states = sorted({s["url"] for s in graph["nodes"]["states"] if urlsplit(s["url"]).netloc == origin})[: args.max_states]
    known: set[str] = set()
    for item in graph.get("resource_evidence", []):
        if item.get("url"):
            known.add(urlsplit(item["url"]).path)
    for container in (graph.get("navigation_evidence", []), graph["nodes"].get("actions_evidence", []), graph.get("replays", [])):
        for entry in container:
            for event in entry.get("network", []):
                known.add(urlsplit(event["url"]).path)
            for step in entry.get("prerequisite_network", []):
                for event in step.get("network", []):
                    known.add(urlsplit(event["url"]).path)
    rows, api_urls = [], {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for url in states:
            context = browser.new_context()
            # Passive probe: only same-origin traffic is allowed out.
            context.route("**/*", lambda route, req: route.continue_() if urlsplit(req.url).netloc == origin else route.abort())
            context.add_init_script(HOOK)
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=10_000)
                page.wait_for_timeout(args.dwell_ms)
                data = page.evaluate(COLLECT, SNAPSHOT_SELECTOR)
            except Exception as exc:  # noqa: BLE001 - probe records and continues
                rows.append({"state_path": urlsplit(url).path, "error": type(exc).__name__})
                context.close()
                continue
            for api, value in data["urls"]:
                target = urljoin(url, value)
                if urlsplit(target).netloc == origin:
                    api_urls.setdefault(urlsplit(target).path, set()).add(api)
            rows.append({"state_path": urlsplit(url).path, "listener_elements": data["listener_elements"],
                         "listener_only_elements": data["listener_only"], "js_api_calls": len(data["urls"])})
            context.close()
        browser.close()
    unseen = {path: sorted(apis) for path, apis in api_urls.items() if path not in known}
    summary = {
        "states_probed": len(states),
        "states_with_listener_only_elements": sum(1 for r in rows if r.get("listener_only_elements")),
        "listener_only_elements_total": sum(r.get("listener_only_elements", 0) for r in rows),
        "states_with_js_api_calls": sum(1 for r in rows if r.get("js_api_calls")),
        "same_origin_js_api_paths": len(api_urls),
        "js_api_paths_absent_from_run_graph": len(unseen),
        "absent_paths_by_api": {api: sum(api in apis for apis in unseen.values())
                                for api in sorted({a for apis in unseen.values() for a in apis})},
        "errors": sum(1 for r in rows if "error" in r),
    }
    args.out.write_text(json.dumps({"summary": summary, "per_state": rows}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
