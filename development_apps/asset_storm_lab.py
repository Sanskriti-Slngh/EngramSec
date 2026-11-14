"""Module-heavy SPA fixture (development only; stdlib) that reproduces the ComfyUI request storm.

The ComfyUI diagnosis showed that most of Agent 1's HTTP budget went to refetching a small set of
identical static assets (scripts/styles) on every navigation and every replay, because the route
interceptor fetches each request from the server (defeating the browser cache) and because restored
pages start from a cold context. This fixture reproduces that pattern generically: every page links the
SAME large static-asset bundle (``MODULES`` scripts + ``STYLES`` stylesheets), so navigating between the
handful of pages re-pulls the whole bundle. A few genuinely functional controls (search, an XHR button,
a GET detail view) are the actual application behavior that competes for the shared HTTP budget.

No ComfyUI-specific paths or rules appear here; it is a synthetic, deterministic JavaScript-heavy site.
``STATE`` counts requests per path so refetching is measurable server-side as well as from the trace.

Ground truth (functional, asset-independent):
  FUNCTIONAL_CAPABILITIES = page/area views + search + detail + the XHR action.
"""
from __future__ import annotations

import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

MODULES = [f"/assets/mod-{i:02d}.js" for i in range(44)]      # the "bundle": many script modules
STYLES = [f"/assets/style-{i}.css" for i in range(8)]
PAGES = {"/": "Home", "/gallery": "Gallery", "/editor": "Editor",
         "/settings": "Settings", "/docs": "Docs", "/about": "About"}
FUNCTIONAL_CAPABILITIES = {
    "home_view", "gallery_view", "editor_view", "settings_view", "docs_view", "about_view",
    "search", "detail_view", "stats_xhr",
}


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.requests: Counter[str] = Counter()
        self.functions: Counter[str] = Counter()
        self.log: list[dict] = []

    def record(self, method: str, path: str) -> None:
        with self.lock:
            self.requests[path] += 1
            self.log.append({"method": method, "path": path})

    def executed(self, key: str) -> None:
        with self.lock:
            self.functions[key] += 1

    def snapshot(self) -> dict:
        with self.lock:
            assets = {p: n for p, n in self.requests.items() if p.startswith("/assets/")}
            return {"functions": dict(self.functions),
                    "asset_requests_total": sum(assets.values()),
                    "asset_paths_unique": len(assets),
                    "asset_refetch_waste": sum(n - 1 for n in assets.values()),
                    "distinct_paths": len(self.requests)}


STATE = _State()


def _shell(title: str, body: str) -> str:
    links = "".join(f"<link rel='stylesheet' href='{s}'>" for s in STYLES)
    scripts = "".join(f"<script src='{m}'></script>" for m in MODULES)
    nav = "".join(f"<a href='{p}'>{n}</a> " for p, n in PAGES.items())
    return (f"<!doctype html><html><head><title>{title}</title>{links}{scripts}</head><body>"
            f"<nav aria-label='main'>{nav}</nav><main>{body}</main></body></html>")


class AssetStormHandler(BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        return

    def _send(self, body: bytes, status: int = 200, ctype: str = "text/html") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # Realistic immutable caching headers (the route interceptor still refetches through them).
        if urlsplit(self.path).path.startswith("/assets/"):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.send_header("ETag", '"' + urlsplit(self.path).path.strip("/").replace("/", "_") + '"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parts = urlsplit(self.path)
        path, qs = parts.path, parse_qs(parts.query)
        STATE.record("GET", path)

        if path.startswith("/assets/mod-") and path.endswith(".js"):
            idx = path[len("/assets/mod-"):-3]
            # A real, non-trivial module body so the bytes are meaningful but deterministic.
            body = (f"export const MOD='{idx}';\n" + f"// module {idx}\n" * 40).encode()
            return self._send(body, ctype="application/javascript")
        if path.startswith("/assets/style-") and path.endswith(".css"):
            return self._send((f".m{path} {{color:#{path[-5]}{path[-5]}{path[-5]}}}\n" * 20).encode(),
                              ctype="text/css")
        if path == "/api/stats":
            STATE.executed("stats_xhr")
            return self._send(b'{"ok":true,"items":3}', ctype="application/json")
        if path == "/detail":
            STATE.executed("detail_view")
            iid = (qs.get("id") or ["1"])[0]
            return self._send(_shell("Detail", f"<h1>Item {iid}</h1><a href='/gallery'>Back</a>").encode())

        if path in PAGES:
            key = {"/": "home_view", "/gallery": "gallery_view", "/editor": "editor_view",
                   "/settings": "settings_view", "/docs": "docs_view", "/about": "about_view"}[path]
            STATE.executed(key)
            if path == "/gallery" and qs.get("q"):
                STATE.executed("search")
            extras = {
                "/": "<form action='/gallery' method='get'><input name='q' aria-label='search'>"
                     "<button>Search</button></form>",
                "/gallery": "<ul>" + "".join(f"<li><a href='/detail?id={i}'>Item {i}</a></li>"
                                             for i in range(1, 6)) + "</ul>",
                "/editor": "<button id='stats' onclick=\"fetch('/api/stats')\">Load stats</button>",
            }.get(path, "")
            return self._send(_shell(PAGES[path], f"<h1>{PAGES[path]}</h1>{extras}").encode())
        return self._send(_shell("Not found", "<h1>404</h1>").encode(), status=404)


def start_asset_storm_lab(port: int = 0) -> tuple[ThreadingHTTPServer, str, _State]:
    STATE.reset()
    server = ThreadingHTTPServer(("127.0.0.1", port), AssetStormHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    return server, url, STATE


if __name__ == "__main__":
    srv, url, _ = start_asset_storm_lab(8078)
    print(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
