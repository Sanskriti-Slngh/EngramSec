"""Phase 1 (transfer validation) reproductions for the bounded HTTP pipeline.

Each test asserts the correct behavior of a general HTTP situation against a
synthetic localhost server. None of them uses Crawl Maze paths.
"""
from __future__ import annotations

import gzip
import threading
import time
import uuid
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest

from agent1.bounded_http import bounded_get
from agent1.cookies import context_cookie_bridge, parse_set_cookie
from agent1.explorer import DANGEROUS_ACTION, HttpBudget
from agent1.resource_spider import ResourceBudget, ResourceReference, TypedResourceSpider

PAGE = b'<html><body><a href="/leaf/one.html">one</a><img src="/leaf/two.png"></body></html>'
VALID_SESSIONS: set[str] = set()


class Server(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _head(self, headers=(), status=200, ctype="text/html; charset=utf-8"):
        self.send_response(status)
        if ctype:
            self.send_header("Content-Type", ctype)
        for key, value in headers:
            self.send_header(key, value)
        self.end_headers()

    def _sid(self) -> str | None:
        for part in (self.headers.get("Cookie") or "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == "sid":
                return value
        return None

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/gzip-truncated":
            body = gzip.compress(PAGE)[:-6]  # trailer (CRC + size) cut off
            self._head([("Content-Encoding", "gzip"), ("Connection", "close")]); self.wfile.write(body)
            self.close_connection = True
        elif path == "/raw-deflate":
            compressor = zlib.compressobj(wbits=-15)
            body = compressor.compress(PAGE) + compressor.flush()
            self._head([("Content-Encoding", "deflate"), ("Content-Length", str(len(body)))]); self.wfile.write(body)
        elif path == "/te-gzip-chunked":
            body = gzip.compress(PAGE)
            self._head([("Transfer-Encoding", "gzip, chunked")])
            self.wfile.write(b"%x\r\n%s\r\n0\r\n\r\n" % (len(body), body))
        elif path == "/slow":
            self._head([("Connection", "close")])
            self.wfile.write(PAGE[:40]); self.wfile.flush()
            for _ in range(100):  # 30 s if read to the end
                time.sleep(0.3)
                self.wfile.write(b" " * 64); self.wfile.flush()
            self.close_connection = True
        elif path.startswith("/r/"):
            n = int(path.rsplit("/", 1)[1])
            self._head([("Location", f"/r/{n + 1}"), ("Content-Length", "0")], status=302)
        elif path == "/login":
            sid = uuid.uuid4().hex
            VALID_SESSIONS.add(sid)
            self._head([("Set-Cookie", f"sid={sid}; Path=/; HttpOnly; SameSite=Lax"), ("Content-Length", "2")])
            self.wfile.write(b"ok")
        elif path == "/renew":
            # Periodic session renewal: a new identifier replaces the old one,
            # which is invalidated server-side immediately.
            old = self._sid()
            if old in VALID_SESSIONS:
                VALID_SESSIONS.discard(old)
                new = uuid.uuid4().hex
                VALID_SESSIONS.add(new)
                self._head([("Set-Cookie", f"sid={new}; Path=/; HttpOnly; SameSite=Lax"), ("Content-Length", str(len(PAGE)))])
            else:
                self._head([("Content-Length", str(len(PAGE)))])
            self.wfile.write(PAGE)
        elif path == "/whoami":
            body = b"valid" if self._sid() in VALID_SESSIONS else b"expired"
            self._head([("Content-Length", str(len(body)))], ctype="text/plain"); self.wfile.write(body)
        else:
            self._head([("Content-Length", "0")], status=404)


@pytest.fixture(scope="module")
def base():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Server)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown(); server.server_close()


# ------------------------------------------------------------- framing and coding

def test_truncated_gzip_stream_is_incomplete_not_complete(base):
    result = bounded_get(f"{base}/gzip-truncated", max_body_bytes=1_000_000)
    assert result.body_status == "incomplete"


def test_raw_deflate_content_coding_is_decoded(base):
    result = bounded_get(f"{base}/raw-deflate", max_body_bytes=1_000_000)
    assert result.body_status == "complete" and result.body == PAGE


def test_unsupported_transfer_coding_is_not_parsed_as_a_body(base):
    result = bounded_get(f"{base}/te-gzip-chunked", max_body_bytes=1_000_000)
    assert result.body_status == "unsupported_transfer_coding" and result.body == b""


def test_slow_trickle_is_bounded_by_a_total_deadline(base):
    started = time.monotonic()
    result = bounded_get(f"{base}/slow", max_body_bytes=1_000_000, timeout_s=2.0, deadline_s=1.0)
    assert time.monotonic() - started < 3.0
    assert result.body_status == "timeout" and result.body.startswith(PAGE[:40])


def test_set_cookie_headers_are_returned_not_dropped(base):
    result = bounded_get(f"{base}/login", max_body_bytes=1_000)
    assert len(result.set_cookies) == 1 and result.set_cookies[0].startswith("sid=")


# ------------------------------------------------------------- RFC 6265 storage rules

def test_set_cookie_parser_follows_rfc6265_scope_rules():
    url = "http://app.example.test/a/b/page"
    host = parse_set_cookie("sid=1; HttpOnly; SameSite=strict", url, now=0)
    assert (host.name, host.domain, host.host_only, host.path, host.http_only, host.same_site) == (
        "sid", "app.example.test", True, "/a/b", True, "Strict")
    domain = parse_set_cookie("pref=x; Domain=.example.test; Path=/", url, now=0)
    assert domain.domain == "example.test" and not domain.host_only and domain.path == "/"
    assert parse_set_cookie("x=1; Domain=other.test", url, now=0).reject_reason == "domain_mismatch"
    assert parse_set_cookie("x=1; Secure", url, now=0).reject_reason == "secure_from_insecure_origin"
    assert parse_set_cookie("__Host-x=1; Secure; Path=/", "https://app.example.test/", now=0).reject_reason is None
    assert parse_set_cookie("__Host-x=1; Secure; Path=/a", "https://app.example.test/", now=0).reject_reason == "prefix_rules"
    assert parse_set_cookie("x=1; Max-Age=0", url, now=0).delete
    assert parse_set_cookie("x=1; Expires=Thu, 01 Jan 1970 00:00:00 GMT", url, now=10).delete
    assert parse_set_cookie("x=1; Max-Age=60; Expires=Thu, 01 Jan 1970 00:00:00 GMT", url, now=10).expires == 70
    assert parse_set_cookie("novalue", url, now=0).reject_reason == "no_name_value_pair"
    # Secure cookies from http://localhost are accepted, as Chromium does.
    assert parse_set_cookie("x=1; Secure", "http://127.0.0.1:8000/", now=0).reject_reason is None


# ------------------------------------------------------------- authorized session context

def test_passive_fetch_keeps_the_browser_session_in_sync_after_server_rotation(base):
    """Reproduction: the bounded reader sent the browser's cookie but dropped
    the rotated one, so the server invalidated the browser's session."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(f"{base}/login")
            spider = TypedResourceSpider(base + "/", [], ResourceBudget(10), 3, 1_000_000, body_reader="bounded_stream")
            spider.cookie_source, spider.cookie_sink = context_cookie_bridge(context)
            record = spider._fetch(None, ResourceReference(f"{base}/renew", "navigation", "html", "t"),
                                   base + "/", 1, "document", "typed_resource")
            assert record["session_cookie_names"] == ["sid"] and record["set_cookie_names"] == ["sid"]
            assert record["cookie_updates"] == {"applied": 1}
            page.goto(f"{base}/whoami")
            assert page.inner_text("body") == "valid"
            # Evidence carries cookie names only, never values.
            sid = next(c["value"] for c in context.cookies() if c["name"] == "sid")
            assert sid not in repr(record)
        finally:
            browser.close()


# ------------------------------------------------------------- redirect chains

def test_redirect_chains_are_bounded_like_a_user_agent(base):
    http = HttpBudget(400)
    caps = {"document": 50, "other_asset": 1}
    s = TypedResourceSpider(base + "/", [], ResourceBudget(100, dict(caps), http), 3, 1_000_000,
                            class_budgets=dict(caps), extraction="standards", allocation="shared_http",
                            dangerous_pattern=DANGEROUS_ACTION, frontier_model="persistent",
                            body_reader="bounded_stream")
    s.observe_response('<a href="/r/0">start</a>', base + "/", "text/html", {})
    records = []
    for _ in range(40):
        records += s.fetch_pending(None, 10)
    hops = [r for r in records if r.get("status") == "fetched" and "/r/" in str(r.get("url"))]
    assert len(hops) <= 21  # the first request plus at most 20 followed hops
    assert any(r.get("queue_decision") == "rejected_redirect_limit" for r in records)


# ------------------------------------------------------------- verification reserve

def test_http_verification_reserve_is_spent_only_by_browser_replay():
    """Reproduction (transfer fixture): exploration exhausted the shared budget
    and 68 of 77 replays failed at the start URL with ERR_BLOCKED_BY_CLIENT."""
    budget = HttpBudget(10, verification_reserve=3)
    assert sum(budget.consume("browser") for _ in range(10)) == 7          # discovery stops at limit - reserve
    budget.phase = "verification"
    assert not budget.consume("passive_document")                          # passive sources never use the reserve
    assert sum(budget.consume("browser") for _ in range(5)) == 3            # replay may
    assert budget.by_source == {"browser": 7, "browser_verification": 3}
    assert HttpBudget(10).remaining() and HttpBudget(10, 0)._cap("browser") == 10  # default: no reserve


def test_literal_prefix_of_a_computed_request_target_is_not_a_speculative_get():
    """Reproduction (transfer fixture): '/api/shelf/' from fetch('/api/shelf/' + id)
    was fetched by the speculative lane, i.e. a GET to part of a runtime request."""
    from agent1.resource_spider import extract_script_references
    js = ("fetch('/api/shelf/' + t.dataset.id, {method: 'POST'}); x.open('PUT', '/api/rec/' + id);"
          "new Request('/api/req/' + n); const page = '/docs/guide.html';")
    refs = extract_script_references(js, "http://h/app.js", extended=True)
    speculative = {r.url for r in refs if r.confidence == "speculative"}
    assert speculative == {"http://h/docs/guide.html"}
