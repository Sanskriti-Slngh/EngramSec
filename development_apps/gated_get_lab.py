"""GET-unlocked deep-functionality fixture (development only; stdlib; no writes at all).

Tests whether the focus generalizes beyond writes: an ordinary GET to a functional hub (``/dashboard``)
reveals a deeper subtree of DISTINCT functional operations (reports / settings / billing, and a nested
report export). There are no POSTs anywhere. Navigation breadth keeps the hub's deep children stranded
under ordinary discovery (they are deprioritized and discovery hits its deadline first), so only a focus
that seeds on genuinely-new functionality — not on breadth lists — will reach them.

The hub's children have distinct route templates (a functional area); the section pages are breadth
(one template x N items) and must NOT be focused.

Ground truth: FUNCTIONAL_CAPABILITIES, ALWAYS_REACHABLE, DEEP_GET_SUBTREE (reachable only by descending
the hub). STATE.functions is the executed ledger.
"""
from __future__ import annotations

import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

CATALOG_ITEMS = 60
SECTIONS = {"catalog": "item", "guides": "guide", "docs": "doc", "archive": "arch",
            "notes": "note", "wiki": "page"}

# The hub's subtree is two levels deep and uses DISTINCT operations at each level, so under ordinary
# discovery (where GET links are explored breadth-first by path length) the deeper grandchildren are
# deprioritized behind the section breadth and stranded at the discovery deadline.
HUB = {
    "reports": ["monthly", "annual", "export"],
    "settings": ["profile", "security"],
    "billing": ["invoices", "plan"],
}
FUNCTIONAL_CAPABILITIES = ({"home", "section_view", "item_view", "dashboard_view"}
                           | {f"{k}_view" for k in HUB} | {f"{k}_{c}" for k, cs in HUB.items() for c in cs})
ALWAYS_REACHABLE = {"home", "section_view", "item_view", "dashboard_view"}
DEEP_GET_SUBTREE = ({f"{k}_view" for k in HUB} | {f"{k}_{c}" for k, cs in HUB.items() for c in cs})


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.functions: Counter[str] = Counter()
        self.log: list[dict] = []

    def executed(self, key: str) -> None:
        with self.lock:
            self.functions[key] += 1

    def snapshot(self) -> dict:
        with self.lock:
            return {"functions": dict(self.functions), "distinct_paths": len({e["path"] for e in self.log})}


STATE = _State()


def _page(title: str, body: str) -> bytes:
    sections = " ".join(f"<a href='/{s}'>{s.title()}</a>" for s in SECTIONS)
    return (f"<!doctype html><html><head><title>{title}</title></head><body>"
            f"<nav aria-label='main'><a href='/'>Home</a> {sections} <a href='/dashboard'>Dashboard</a></nav>"
            f"<main>{body}</main></body></html>").encode()


class GatedGetHandler(BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        return

    def _send(self, body: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        with STATE.lock:
            STATE.log.append({"method": "GET", "path": path})
        parts = [p for p in path.split("/") if p]
        if path == "/":
            STATE.executed("home")
            return self._send(_page("Home", "<h1>Home</h1>"))
        if len(parts) == 1 and parts[0] in SECTIONS:
            STATE.executed("section_view")
            leaf = SECTIONS[parts[0]]
            links = "".join(f"<li><a href='/{leaf}/{i}'>{parts[0].title()} {i}</a></li>"
                            for i in range(1, CATALOG_ITEMS + 1))
            return self._send(_page(parts[0].title(), f"<h1>{parts[0].title()}</h1><ul>{links}</ul>"))
        if len(parts) == 2 and parts[0] in SECTIONS.values():
            n = int(parts[1]) if parts[1].isdigit() else 0
            if 1 <= n <= CATALOG_ITEMS:
                STATE.executed("item_view")
                return self._send(_page(f"Entry {n}", f"<h1>Entry {n}</h1>"))
            return self._send(_page("Not found", "<h1>404</h1>"), status=404)
        # functional hub -> distinct deeper operations, two levels deep (no writes)
        if path == "/dashboard":
            STATE.executed("dashboard_view")
            links = " ".join(f"<a href='/dashboard/{k}'>{k.title()}</a>" for k in HUB)
            return self._send(_page("Dashboard", f"<h1>Dashboard</h1>{links}"))
        if len(parts) == 2 and parts[0] == "dashboard" and parts[1] in HUB:
            STATE.executed(f"{parts[1]}_view")
            links = " ".join(f"<a href='/dashboard/{parts[1]}/{c}'>{c.title()}</a>" for c in HUB[parts[1]])
            return self._send(_page(parts[1].title(), f"<h1>{parts[1].title()}</h1>{links}"))
        if len(parts) == 3 and parts[0] == "dashboard" and parts[1] in HUB and parts[2] in HUB[parts[1]]:
            STATE.executed(f"{parts[1]}_{parts[2]}")
            return self._send(_page(f"{parts[1]} {parts[2]}", f"<h1>{parts[1]} / {parts[2]}</h1>"))
        return self._send(_page("Not found", "<h1>404</h1>"), status=404)


def start_gated_get_lab(port: int = 0) -> tuple[ThreadingHTTPServer, str, _State]:
    STATE.reset()
    server = ThreadingHTTPServer(("127.0.0.1", port), GatedGetHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    return server, url, STATE


if __name__ == "__main__":
    srv, url, _ = start_gated_get_lab(8082)
    print(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
