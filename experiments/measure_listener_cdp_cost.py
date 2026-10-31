#!/usr/bin/env python3
"""Large-DOM cost of runtime listener observation (offline measurement).

For synthetic pages of N elements (nested, realistic-ish markup) with a given
share of elements carrying a click listener, measures:
  * the raw DOMDebugger.getEventListeners(document, depth -1, pierce) call:
    latency, listener count, response size, Python allocation peak;
  * ListenerObserver.observe(): first observation and an unchanged repeat
    (incremental reuse), and after one action that adds a listener element.
Every page is served from a data URL-free local route; nothing leaves the host.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import tracemalloc
from pathlib import Path

from playwright.sync_api import sync_playwright

from agent1.explorer import SNAPSHOT_SELECTOR
from agent1.listeners import ListenerObserver

BUILD = """([n, share]) => {
  document.body.innerHTML = '';
  const root = document.createElement('main'); document.body.append(root);
  let parent = root, made = 0, listeners = 0;
  const every = share > 0 ? Math.round(1 / share) : 0;
  while (made < n) {
    const section = document.createElement('section'); parent.append(section); made++;
    for (let i = 0; i < 9 && made < n; i++) {
      const el = document.createElement(i % 3 ? 'div' : 'span');
      el.textContent = 'Item ' + made; el.style.padding = '1px'; section.append(el); made++;
      if (every && made % every === 0) { el.addEventListener('click', () => {}); listeners++; }
      if (made % 7 === 0) el.addEventListener('mouseover', () => {});
    }
    if (made % 500 < 10) parent = section;  // some nesting depth
  }
  const add = document.createElement('button'); add.id = 'add'; add.textContent = 'Add';
  add.onclick = () => { const d = document.createElement('div'); d.textContent = 'New action';
    d.addEventListener('click', () => {}); document.body.prepend(d); };
  document.body.prepend(add);
  return listeners;
}"""


def measure(page, n: int, share: float, repeats: int) -> dict:
    page.goto("about:blank")
    page.set_content("<!doctype html><title>dom</title><body></body>")
    created = page.evaluate(BUILD, [n, share])
    cdp = page.context.new_cdp_session(page)
    cdp.send("DOM.getDocument", {"depth": 0})
    doc = cdp.send("Runtime.evaluate", {"expression": "document", "objectGroup": "m"})["result"]["objectId"]
    raw_ms, sizes, peaks, count = [], [], [], 0
    for _ in range(repeats):
        tracemalloc.start()
        started = time.perf_counter()
        result = cdp.send("DOMDebugger.getEventListeners", {"objectId": doc, "depth": -1, "pierce": True})
        raw_ms.append((time.perf_counter() - started) * 1000)
        peaks.append(tracemalloc.get_traced_memory()[1] / 1e6)
        tracemalloc.stop()
        sizes.append(len(json.dumps(result)))
        count = len(result["listeners"])
    observer = ListenerObserver(SNAPSHOT_SELECTOR, max_dom_elements=None)  # guard off: measure the mechanism
    first = observer.observe(page, "navigation:start")
    repeat = observer.observe(page, None)
    page.click("#add")
    after = observer.observe(page, "click:add")
    dom_size = page.evaluate("document.querySelectorAll('*').length")
    cdp.detach()

    def summary(s):
        return {"ms": s.elapsed_ms, "cdp_calls": s.cdp_calls, "described": s.described_nodes,
                "reused": s.reused_nodes, "truncated": s.truncated, "listener_nodes": s.listener_nodes,
                "candidates": len(s.candidates), "error": s.error}
    return {
        "elements": dom_size, "click_listener_elements": created, "listener_records": count,
        "enumeration_ms_median": round(statistics.median(raw_ms), 1),
        "enumeration_ms_max": round(max(raw_ms), 1),
        "response_bytes": sizes[-1], "python_alloc_peak_mb": round(max(peaks), 2),
        "observe_first": summary(first), "observe_unchanged": summary(repeat), "observe_after_action": summary(after),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[100, 1_000, 10_000, 50_000])
    ap.add_argument("--shares", type=float, nargs="+", default=[0.01, 0.1])
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        for n in args.sizes:
            for share in args.shares:
                row = {"target_elements": n, "click_listener_share": share} | measure(page, n, share, args.repeats)
                rows.append(row)
                print(json.dumps({k: row[k] for k in ("elements", "click_listener_share", "listener_records",
                                                       "enumeration_ms_median", "response_bytes", "python_alloc_peak_mb")}
                                 | {"first_ms": row["observe_first"]["ms"], "unchanged_ms": row["observe_unchanged"]["ms"],
                                    "after_ms": row["observe_after_action"]["ms"]}), flush=True)
        browser_version = browser.version
        browser.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"browser": f"chromium {browser_version}", "rows": rows}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
