from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

from agent1.resource_spider import (
    ResourceBudget,
    TypedResourceSpider,
    extract_css_references,
    extract_header_references,
    extract_html_references,
    extract_script_references,
)


def test_html_references_resolve_base_and_typed_attributes() -> None:
    html = """<html><head>
    <base href="/catalog/v2/">
    <link rel="canonical" href="item/7">
    <link rel="preload" href="bundle.js" as="script">
    <link rel="manifest" href="app.webmanifest">
    <meta http-equiv="refresh" content="3; url=next">
    <style>.hero{background:url('../img/bg.png')}</style>
    </head><body>
    <a href="../help">help</a><img src="photo.png" srcset="small.png 1x, large.png 2x">
    <iframe src="frame"></iframe><video poster="cover.jpg"><source src="clip.mp4"></video>
    <audio src="audio.ogg"></audio><track src="captions.vtt">
    <form action="lookup"><button formaction="submit">go</button></form>
    <script>fetch('/api/items'); import('./module.mjs');</script>
    </body></html>"""
    refs = extract_html_references(html, "http://app.test/page")
    by_source = {(item.source, item.relation, item.url): item.kind for item in refs}
    assert any(item.url == "http://app.test/catalog/help" and item.kind == "navigation" for item in refs)
    assert any(item.url == "http://app.test/catalog/v2/photo.png" and item.kind == "asset" for item in refs)
    assert any(item.url == "http://app.test/catalog/v2/large.png" for item in refs)
    assert any(item.url == "http://app.test/catalog/v2/submit" and item.kind == "navigation" for item in refs)
    assert any(item.url == "http://app.test/catalog/v2/lookup" and item.kind == "api" for item in refs)
    assert any(item.url == "http://app.test/catalog/v2/next" and item.relation == "refresh" for item in refs)
    assert any(item.url == "http://app.test/catalog/img/bg.png" for item in refs)
    assert by_source


def test_http_headers_css_and_script_references_are_observed() -> None:
    headers = {
        "Location": "../new-page",
        "Link": "</css/site.css>; rel=preload; as=style, </api/catalog>; rel=alternate",
        "Refresh": "2; url=/refresh-target",
    }
    refs = extract_header_references(headers, "https://app.test/old/page")
    assert {(item.url, item.kind) for item in refs} >= {
        ("https://app.test/new-page", "navigation"),
        ("https://app.test/css/site.css", "asset"),
        ("https://app.test/api/catalog", "navigation"),
        ("https://app.test/refresh-target", "navigation"),
    }
    css = extract_css_references("@import '../base.css'; .x{src:url(\"../font.woff2\")}", "https://app.test/css/main.css")
    assert {item.url for item in css} == {
        "https://app.test/base.css", "https://app.test/font.woff2"
    }
    script = extract_script_references("import('./chunk.js'); fetch('/api/search?q=x');", "https://app.test/js/main.js")
    assert {(item.url, item.kind) for item in script} == {
        ("https://app.test/js/chunk.js", "asset"),
        ("https://app.test/api/search?q=x", "api"),
    }


class SpiderHandler(BaseHTTPRequestHandler):
    def _send(self, content_type: str, text: str, status: int = 200) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/":
            self._send("text/html; charset=utf-8", '<a href="/page">page</a><img src="/pixel.png"><a href="/redirect">redirect</a>')
        elif self.path == "/page":
            self._send("text/html; charset=utf-8", '<a href="/nested">nested</a><link rel="stylesheet" href="/style.css">')
        elif self.path == "/nested":
            self._send("text/html; charset=utf-8", "<p>deep page</p>")
        elif self.path == "/style.css":
            self._send("text/css; charset=utf-8", "body{background:url('/pixel.png')}")
        elif self.path == "/pixel.png":
            self._send("image/png", "not-a-real-image")
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "https://outside.test/never-fetch")
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self._send("text/plain", "missing", 404)

    def log_message(self, *_: object) -> None:
        pass


def test_typed_spider_fetches_only_observed_in_scope_references_and_honors_budget() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), SpiderHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}/"
    try:
        budget = ResourceBudget(2)
        spider = TypedResourceSpider(base, [], budget, max_depth=3, max_body_bytes=64_000)
        spider.observe_response(
            '<a href="/page">page</a><a href="https://outside.test/x">external</a><form action="/api"></form>',
            base,
            "text/html",
            {},
        )
        spider.observe_response(
            '<a href="/page">page</a><a href="https://outside.test/x">external</a><form action="/api"></form>',
            base,
            "text/html",
            {},
        )
        with sync_playwright() as playwright:
            request = playwright.request.new_context()
            evidence = spider.fetch_pending(request)
            request.dispose()
        assert budget.attempted == 2
        assert any(item["status"] == "out_of_scope" for item in evidence)
        assert any(item["kind"] == "api" and item["status"] == "discovered" for item in evidence)
        assert all("outside.test" not in str(item["url"]) for item in evidence if item["status"] in {"fetched", "failed"})
        assert sum(item["status"] == "fetched" for item in evidence) == 2
        assert any(item["status"] == "budget_limited" for item in evidence)
        page_refs = [
            item for item in evidence
            if item["url"] == f"http://127.0.0.1:{server.server_port}/page"
            and item["status"] == "discovered"
        ]
        assert len(page_refs) == 1
        redirect_spider = TypedResourceSpider(base, [], ResourceBudget(1), 1, 64_000)
        redirect_spider.observe_response('<a href="/redirect">redirect</a>', base, "text/html", {})
        with sync_playwright() as playwright:
            request = playwright.request.new_context()
            redirect_evidence = redirect_spider.fetch_pending(request)
            request.dispose()
        assert any(item.get("redirected_to", "").startswith("https://outside.test") for item in redirect_evidence)
        assert not any(item["url"].startswith("https://outside.test") and item["status"] in {"fetched", "failed"} for item in redirect_evidence)
    finally:
        server.shutdown()
        server.server_close()
