#!/usr/bin/env python3
"""Deterministic runtime-interaction probe (diagnostic; not integrated into Agent 1).

Six synthetic pages exercise runtime control creation. For each page the probe
performs the first, visibly advertised click and then compares:
  (a) Agent 1's existing snapshot controls (BrowserSession.observe),
  (b) Chromium DevTools DOMDebugger.getEventListeners on a bounded node set,
  (c) a bounded MutationObserver record of added elements.
Nothing outside the local fixture is contacted.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright  # noqa: E402

from agent1.explorer import BrowserSession  # noqa: E402
from agent1.schema import RunConfig  # noqa: E402

PAGES = {
    "creates_button": """<button id=go onclick="var b=document.createElement('button');b.textContent='Open details';
        b.onclick=()=>fetch('/api/details');document.body.append(b)">Show</button>""",
    "creates_div_listener": """<button id=go onclick="var d=document.createElement('div');d.textContent='Open details';
        d.addEventListener('click',()=>fetch('/api/details'));document.body.append(d)">Show</button>""",
    "redefines_handler": """<button id=go onclick="this.onclick=()=>fetch('/api/second')">Step</button>""",
    "delegation": """<ul id=list><li><span class=item data-id=1>Alpha</span></li><li><span class=item data-id=2>Beta</span></li></ul>
        <button id=go onclick="document.getElementById('list').insertAdjacentHTML('beforeend','<li><span class=item data-id=3>Gamma</span></li>')">More</button>
        <script>document.addEventListener('click',e=>{const t=e.target.closest('.item');if(t)fetch('/api/item/'+t.dataset.id)})</script>""",
    "listener_removed": """<button id=go onclick="var b=document.createElement('button');b.id='temp';b.textContent='Temporary';
        const f=()=>fetch('/api/temp');b.addEventListener('click',f);document.body.append(b);
        setTimeout(()=>{b.removeEventListener('click',f);b.remove()},300)">Show</button>""",
    "delayed_control": """<button id=go onclick="setTimeout(()=>{var b=document.createElement('button');b.textContent='Late action';
        b.onclick=()=>fetch('/api/late');document.body.append(b)},1200)">Arm</button>""",
}

MUTATIONS = """
window.__probeAdded = [];
new MutationObserver(records => { for (const r of records) for (const n of r.addedNodes)
  if (n.nodeType === 1 && window.__probeAdded.length < 200) window.__probeAdded.push(n.tagName.toLowerCase() + ':' + (n.textContent || '').trim().slice(0, 40)); })
  .observe(document, {childList: true, subtree: true});
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        name = self.path.strip("/").split("?")[0]
        body = f"<!doctype html><title>{name}</title><body>{PAGES.get(name, '')}</body>".encode() if name in PAGES else b"{}"
        self.send_response(200 if name in PAGES or self.path.startswith("/api/") else 404)
        self.send_header("Content-Type", "text/html" if name in PAGES else "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def listeners(page, cdp) -> list[dict]:
    """Click/pointer listeners on up to 300 elements plus document/window."""
    found = []
    document = cdp.send("DOM.getDocument", {"depth": -1})
    ids = cdp.send("DOM.querySelectorAll", {"nodeId": document["root"]["nodeId"], "selector": "*"})["nodeIds"][:300]
    targets = [("document", cdp.send("Runtime.evaluate", {"expression": "document"})["result"]["objectId"]),
               ("window", cdp.send("Runtime.evaluate", {"expression": "window"})["result"]["objectId"])]
    for node_id in ids:
        obj = cdp.send("DOM.resolveNode", {"nodeId": node_id})["object"]
        targets.append((obj.get("description", "?"), obj["objectId"]))
    for label, object_id in targets:
        for item in cdp.send("DOMDebugger.getEventListeners", {"objectId": object_id})["listeners"]:
            if item["type"] in {"click", "pointerdown", "mousedown"}:
                found.append({"target": label, "type": item["type"], "script": item.get("scriptId"),
                              "line": item.get("lineNumber"), "column": item.get("columnNumber")})
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}/"
    results = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for name in PAGES:
            config = RunConfig(start_url=base + name, output_dir=args.out.parent / "probe_tmp", settle_ms=0)
            with BrowserSession(browser, config) as session:
                session.page.add_init_script(MUTATIONS)
                session.goto_start()
                cdp = session.context.new_cdp_session(session.page)
                before = session.observe(1)
                listeners_before = listeners(session.page, cdp)
                session.page.click("#go")
                session.page.wait_for_timeout(1500)
                after = session.observe(2)
                listeners_after = listeners(session.page, cdp)
                added = session.page.evaluate("window.__probeAdded || []")
                new_controls = sorted({f"{c.kind}:{c.label}:{c.interaction}" for c in after.controls}
                                      - {f"{c.kind}:{c.label}:{c.interaction}" for c in before.controls})
                changed = [x for x in listeners_after if x not in listeners_before]
                results[name] = {
                    "snapshot_new_controls": new_controls,
                    "cdp_new_or_changed_click_listeners": changed,
                    "cdp_ancestor_listeners": [x for x in listeners_after if x["target"] in {"document", "window"}],
                    "mutation_added_elements": added[:10],
                    "state_signature_changed": before.state_signature != after.state_signature,
                    "group_signature_changed": before.group_signature != after.group_signature,
                }
        browser.close()
    server.shutdown()
    args.out.write_text(json.dumps(results, indent=2) + "\n")
    for name, r in results.items():
        print(f"{name:22} snapshot_new={r['snapshot_new_controls']} cdp_changed={[(c['target'][:28], c['type']) for c in r['cdp_new_or_changed_click_listeners']]} "
              f"ancestor={len(r['cdp_ancestor_listeners'])} added={r['mutation_added_elements'][:3]} state_changed={r['state_signature_changed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
