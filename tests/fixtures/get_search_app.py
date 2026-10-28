from __future__ import annotations

import html
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


class SearchFixtureServer(ThreadingHTTPServer):
    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), SearchFixtureHandler)
        self.lock = threading.Lock()
        self.queries: list[tuple[str, str]] = []

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server_port}"

    def record(self, path: str, query: str) -> None:
        with self.lock:
            self.queries.append((path, query))

    def snapshot(self) -> list[tuple[str, str]]:
        with self.lock:
            return list(self.queries)

    def reset(self) -> None:
        with self.lock:
            self.queries.clear()


class SearchFixtureHandler(BaseHTTPRequestHandler):
    server: SearchFixtureServer

    def log_message(self, *_: object) -> None:
        return

    def _send(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    @staticmethod
    def _form(action: str, *, hidden: bool = False) -> str:
        hidden_attribute = " hidden" if hidden else ""
        return (
            f'<form id="search-form" method="get" action="{action}"{hidden_attribute}>'
            '<label>Search records <input name="query" type="search" required></label>'
            '<button type="submit"><i class="icon-search"></i></button></form>'
        )

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query).get("query", [""])[0]
        if parsed.path not in {"/search-success", "/fake-search", "/toggle-search"}:
            self.send_error(404)
            return
        if query:
            self.server.record(parsed.path, query)
        toggle = ""
        hidden = False
        if parsed.path == "/toggle-search":
            toggle = (
                '<i id="toggle-search" style="display:block;width:20px;height:20px" '
                'onclick="document.querySelector(\'#search-form\').hidden=false"></i>'
            )
            hidden = not bool(query)
        result = ""
        if query and parsed.path in {"/search-success", "/toggle-search"}:
            known = {
                "alpha": ("Alpha operations guide", "/records/alpha-guide"),
                "beta": ("Beta deployment guide", "/records/beta-guide"),
            }
            label, target = known.get(query.casefold(), ("No matching record", "/records/none"))
            result = f'<section id="results"><a href="{target}">{html.escape(label)}</a></section>'
        elif query:
            result = f'<section id="results"><p>You searched for {html.escape(query)}</p></section>'
        self._send(
            "<!doctype html><html><head><title>Search fixture</title></head><body><main>"
            f"<h1>Record search</h1>{toggle}{self._form(parsed.path, hidden=hidden)}{result}"
            "</main></body></html>"
        )


def start_search_server() -> tuple[SearchFixtureServer, threading.Thread]:
    server = SearchFixtureServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
