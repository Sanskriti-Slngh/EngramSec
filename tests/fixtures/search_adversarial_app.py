from __future__ import annotations

import html
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


CASES = {
    "/functional-literal",
    "/echo-only",
    "/permanent-sidebar",
    "/functional-nonliteral",
}


class AdversarialSearchHandler(BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        return

    def _send(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path not in CASES:
            self.send_error(404)
            return
        query = parse_qs(parsed.query).get("q", [""])[0].casefold()
        form = (
            f'<form method="get" action="{parsed.path}">'
            '<label>Search records <input type="search" name="q" required></label>'
            '<button type="submit">Search</button></form>'
        )
        sidebar = ""
        result = ""
        if parsed.path == "/permanent-sidebar":
            sidebar = (
                '<aside aria-label="Related resources">'
                '<a href="/resources/alpha">Alpha reference</a>'
                '<a href="/resources/beta">Beta reference</a></aside>'
            )
        if query and parsed.path == "/functional-literal":
            label, target = {
                "alpha": ("Alpha operations result", "/records/operations"),
                "beta": ("Beta deployment result", "/records/deployment"),
            }.get(query, ("No result", "/records/none"))
            result = f'<section aria-label="Results"><a href="{target}">{label}</a></section>'
        elif query and parsed.path in {"/echo-only", "/permanent-sidebar"}:
            result = f'<section aria-label="Results"><p>You searched {html.escape(query)}</p></section>'
        elif query and parsed.path == "/functional-nonliteral":
            label, target = {
                "alpha": ("Operations handbook", "/records/operations"),
                "beta": ("Deployment manual", "/records/deployment"),
            }.get(query, ("No result", "/records/none"))
            result = f'<section aria-label="Results"><a href="{target}">{label}</a></section>'
        self._send(
            "<!doctype html><html><head><title>Independent search fixture</title></head>"
            f"<body><main><h1>Document search</h1>{form}{sidebar}{result}</main></body></html>"
        )


def start_adversarial_search_server() -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), AdversarialSearchHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"
