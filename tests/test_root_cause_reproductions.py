"""Focused reproductions for the deterministic root-cause audit.

Every test asserts the *correct* behavior for a general HTTP/frontier situation
using synthetic localhost fixtures or a fake request context. Tests that target
the legacy code path document the original defect explicitly.
"""
from __future__ import annotations

import gzip
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest

from agent1.bounded_http import READ_CHUNK, bounded_get
from agent1.explorer import DANGEROUS_ACTION, HttpBudget
from agent1.resource_spider import (
    ResourceBudget,
    ResourceReference,
    TypedResourceSpider,
    extract_header_references,
    extract_html_references,
    extract_references,
    extract_script_references,
)

PAGE = b'<html><body><a href="/leaf/one.html">one</a><img src="/leaf/two.png"></body></html>'
BIG = 3_000_000


class Variants(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the bounded reader closes early on purpose

    def _head(self, headers=(), ctype="text/html; charset=utf-8"):
        self.send_response(200)
        if ctype:
            self.send_header("Content-Type", ctype)
        for key, value in headers:
            self.send_header(key, value)
        self.end_headers()

    def _chunks(self, parts):
        for part in parts:
            self.wfile.write(b"%x\r\n%s\r\n" % (len(part), part))
        self.wfile.write(b"0\r\n\r\n")

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/cl":
            self._head([("Content-Length", str(len(PAGE)))]); self.wfile.write(PAGE)
        elif path == "/nocl":
            self._head([("Connection", "close")]); self.wfile.write(PAGE); self.close_connection = True
        elif path == "/chunked":
            self._head([("Transfer-Encoding", "chunked")]); self._chunks([PAGE[:30], PAGE[30:]])
        elif path == "/empty":
            self._head([("Content-Length", "0")])
        elif path == "/badcl":
            self._head([("Content-Length", "12x"), ("Connection", "close")]); self.wfile.write(PAGE); self.close_connection = True
        elif path == "/big":
            self._head([("Content-Length", str(len(PAGE) + BIG))]); self.wfile.write(PAGE)
            for _ in range(BIG // 65536 + 1):
                self.wfile.write(b" " * min(65536, BIG))
        elif path == "/bigchunked":
            self._head([("Transfer-Encoding", "chunked")]); self._chunks([PAGE] + [b" " * 65536] * 60)
        elif path == "/gzipchunked":
            body = gzip.compress(PAGE)
            self._head([("Content-Encoding", "gzip"), ("Transfer-Encoding", "chunked")]); self._chunks([body])
        elif path == "/bomb":
            body = gzip.compress(b"<a href='/x.html'></a>" + b" " * 50_000_000)
            self._head([("Content-Encoding", "gzip"), ("Content-Length", str(len(body)))]); self.wfile.write(body)
        elif path == "/sniff":
            body = b"<!DOCTYPE html><a href='/sniffed.html'>s</a>"
            self._head([("Content-Length", str(len(body)))], ctype=None); self.wfile.write(body)
        else:
            self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers()


@pytest.fixture(scope="module")
def variants_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Variants)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown(); server.server_close()


def fetch_with(reader: str, url: str, request_context=None):
    spider = TypedResourceSpider(url.rsplit("/", 1)[0] + "/", [], ResourceBudget(100), 3, 1_000_000, body_reader=reader)
    return spider._fetch(request_context, ResourceReference(url, "navigation", "html", "t"), url, 1, "document", "typed_resource")


# ------------------------------------------------------------- phase 1

@pytest.mark.parametrize("variant", ["cl", "nocl", "chunked", "gzipchunked"])
def test_valid_bodies_are_parsed_regardless_of_length_framing(variants_url, variant):
    record = fetch_with("bounded_stream", f"{variants_url}/{variant}")
    assert record["http_status"] == 200 and record["body_status"] == "complete"
    assert record["response_reference_count"] == 2


@pytest.mark.parametrize("variant", ["nocl", "chunked", "gzipchunked"])
def test_legacy_reader_skips_valid_bodies_without_content_length(variants_url, variant):
    """Reproduction of the original defect (kept as the frozen legacy path)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        context = p.request.new_context()
        try:
            record = fetch_with("content_length", f"{variants_url}/{variant}", context)
        finally:
            context.dispose()
    assert record["http_status"] == 200
    assert record["body_status"] == "skipped_unknown_length" and record["response_reference_count"] == 0


def test_empty_and_invalid_framing_are_explicit(variants_url):
    assert fetch_with("bounded_stream", f"{variants_url}/empty")["body_status"] == "empty"
    bad = fetch_with("bounded_stream", f"{variants_url}/badcl")
    assert bad["body_status"] == "invalid_framing" and bad["body_bytes"] == 0  # RFC 9112 6.3


@pytest.mark.parametrize("variant", ["big", "bigchunked"])
def test_oversized_bodies_are_read_only_to_the_bound(variants_url, variant):
    response = bounded_get(f"{variants_url}/{variant}", max_body_bytes=100_000)
    assert response.body_status == "truncated" and len(response.body) == 100_000
    assert response.wire_bytes <= 100_000 + READ_CHUNK  # stopped reading, not drained
    assert b"/leaf/one.html" in response.body  # the bounded prefix is still parsed


def test_compressed_bodies_are_decoded_within_the_bound(variants_url):
    response = bounded_get(f"{variants_url}/bomb", max_body_bytes=200_000)
    assert response.body_status == "truncated" and len(response.body) == 200_000
    assert response.wire_bytes <= 200_000 + READ_CHUNK


def test_missing_content_type_html_is_sniffed_only_when_unknown():
    refs = extract_references("<!DOCTYPE html><a href='/sniffed.html'>x</a>", "http://h/", "", {}, "ast", "standards")
    assert [r.url for r in refs] == ["http://h/sniffed.html"]
    assert extract_references("<a href='/x.html'>x</a>", "http://h/", "text/plain", {}, "ast", "standards") == []
    assert extract_references("<!DOCTYPE html><a href='/s.html'>", "http://h/", "", {}, "ast", "extended") == []  # frozen


# ------------------------------------------------------------- phase 2 (frontier)

class FakeResponse:
    def __init__(self, url, status, body, headers):
        self.url, self.status, self._body = url, status, body.encode()
        self.headers = {"content-length": str(len(self._body)), **headers}

    def body(self):
        return self._body


class Site:
    """Fake request context: every requested path returns configured HTML."""

    def __init__(self, pages: dict[str, str]):
        self.pages, self.requests = pages, []

    def get(self, url, timeout, max_redirects):
        self.requests.append(urlsplit(url).path)
        body = self.pages.get(urlsplit(url).path, "x")
        return FakeResponse(url, 200, body, {"content-type": "text/html" if body != "x" else "image/png"})


BASE = "http://127.0.0.1:9200/"


def spider(frontier="persistent", allocation="shared_http", extraction="extended", speculative=0, caps=None, depth=3, **kw):
    http = HttpBudget(400)
    caps = caps or {"document": 50, "other_asset": 1}
    budget = ResourceBudget(100, dict(caps), http)
    return TypedResourceSpider(BASE, [], budget, depth, 1_000_000, class_budgets=dict(caps), extraction=extraction,
                               allocation=allocation, max_speculative_fetches=speculative,
                               dangerous_pattern=DANGEROUS_ACTION, frontier_model=frontier, **kw)


def drain(s, site, rounds=20):
    out = []
    for _ in range(rounds):
        out += s.fetch_pending(site, 10)
    return out


def test_observed_only_reference_does_not_block_a_later_explicit_get_link():
    s = spider()
    s.observe_response('<script>fetch("/data/feed", {method: "POST"})</script>', BASE, "text/html", {})
    s.observe_response('<a href="/data/feed">feed</a>', BASE + "other.html", "text/html", {})
    site = Site({})
    drain(s, site)
    assert site.requests == ["/data/feed"]  # fetched once, via the explicit GET link only


def test_speculative_sighting_does_not_block_or_slow_a_later_explicit_reference():
    for cap in (0, 1):
        s = spider(speculative=cap)
        s.observe_response("<p>see /docs/guide.html</p><p>and /docs/other.html</p>", BASE, "text/html", {})
        s.observe_response('<a href="/docs/guide.html">guide</a>', BASE + "index.html", "text/html", {})
        site = Site({})
        records = drain(s, site, rounds=1)
        assert "/docs/guide.html" in site.requests
        guide = [r for r in records if r.get("url", "").endswith("/docs/guide.html") and r.get("status") == "fetched"]
        assert guide and guide[0]["channel"] != "speculative"


def test_kind_upgrade_from_asset_to_document_is_not_lost_to_the_asset_cap():
    s = spider(caps={"document": 50, "other_asset": 0})
    s.observe_response('<img src="/media/report.bin"><a href="/media/report.bin">report</a>', BASE, "text/html", {})
    site = Site({})
    drain(s, site)
    assert "/media/report.bin" in site.requests


def test_safety_rejections_never_become_eligible_again():
    s = spider()
    s.observe_response('<a href="/account/logout">x</a>', BASE, "text/html", {})
    s.observe_response('<a href="/account/logout">again</a>', BASE + "p.html", "text/html", {})
    site = Site({})
    drain(s, site)
    assert site.requests == []


def test_checkpoint_resume_preserves_query_speculative_and_redirect_depth():
    s = spider(speculative=5)
    s.observe_response('<a href="/list?page=2">n</a><p>see /notes/a.txt</p>', BASE, "text/html", {})
    evidence = s.evidence[:]
    resumed = spider(speculative=5)
    resumed.restore_from_evidence(evidence)
    site = Site({})
    drain(resumed, site)
    assert "/list" in site.requests            # query-bearing admitted reference survives resume
    assert "/notes/a.txt" in site.requests     # speculative lane survives resume


def test_redirect_hop_depth_is_restored_without_off_by_one():
    s = spider(depth=1)
    hop = {"url": BASE + "a/", "kind": "navigation", "source_type": "header", "source_url": BASE + "a",
           "source": "Location", "relation": "redirect", "depth": 1, "status": "discovered",
           "queue_decision": "admitted", "confidence": "observed_literal"}
    s.restore_from_evidence([hop])
    site = Site({})
    drain(s, site)
    assert "/a/" in site.requests  # a same-depth hop at the limit stays fetchable after resume


# ------------------------------------------------------------- phase 4 (extraction correctness)

def test_references_with_different_methods_are_kept_distinct():
    refs = [r for r in extract_references('fetch("/rec", {method: "PUT"}); fetch("/rec");', BASE, "application/javascript", {}, "ast", "standards")]
    assert sorted(r.method for r in refs if r.url.endswith("/rec")) == ["GET", "PUT"]


def test_content_location_header_is_an_explicit_reference():
    refs = extract_header_references({"content-location": "/items/7.json"}, BASE + "items/7", corrections=True)
    assert [(r.url, r.kind) for r in refs] == [(BASE + "items/7.json", "asset")]
    assert extract_header_references({"content-location": "/items/7.json"}, BASE + "items/7", extended=True) == []  # frozen


def test_hyperlinks_before_base_resolve_against_the_document_base():
    html = '<head><link rel=stylesheet href="early.css"><base href="/sub/"></head><a href="later.html">x</a><a href="first.html">'
    refs = {r.url for r in extract_html_references('<a href="pre.html">p</a>' + html, BASE + "dir/page.html", extended=True, lazy_base=True)}
    assert BASE + "sub/pre.html" in refs            # hyperlinks resolve lazily against the final base
    assert BASE + "dir/early.css" in refs           # a subresource fetched before <base> keeps the document URL
    assert BASE + "sub/later.html" in refs


def test_shorter_depth_propagates_through_already_fetched_pages():
    """O links A only via a long chain at first; A is fetched deep, so its child
    C is depth-capped. When A is later observed one hop from a browser page, the
    shorter distance must propagate to A's capped descendants (edge relaxation)."""
    pages = {"/l1": '<a href="/l2">x</a>', "/l2": '<a href="/a">x</a>', "/a": '<a href="/b">x</a>',
             "/b": '<a href="/c.html">x</a>', "/c.html": "<p>c</p>"}
    s = spider(depth=3)
    s.observe_response('<a href="/l1">x</a>', BASE, "text/html", {})      # /l1 depth1, /l2 2, /a 3, /b capped (4)
    site = Site(pages)
    drain(s, site)
    assert "/b" not in site.requests
    s.observe_response('<a href="/a">x</a>', BASE + "shortcut.html", "text/html", {})  # /a now depth 1 -> /b 2, /c 3
    drain(s, site)
    assert "/b" in site.requests and "/c.html" in site.requests
    assert site.requests.count("/a") == 1  # the already-fetched page is not fetched again


def test_relaxed_speculative_candidates_stay_in_their_own_lane():
    """Re-admission after a shorter route must not move a speculative candidate
    into the typed queue, where it would compete for (and lose to) class caps."""
    pages = {"/l1": '<a href="/a">x</a>', "/a": "<!-- see /notes/n1.txt -->"}
    s = spider(depth=2, speculative=5, caps={"document": 50, "other_asset": 0})
    s.observe_response('<a href="/l1">x</a>', BASE, "text/html", {})
    site = Site(pages)
    drain(s, site)  # /a fetched at depth 2; its speculative candidate (depth 3) is capped
    assert "/notes/n1.txt" not in site.requests and BASE + "notes/n1.txt" in s._capped
    s.observe_response('<a href="/a">x</a>', BASE + "shortcut.html", "text/html", {})
    records = drain(s, site)
    note = [r for r in records if r.get("url", "").endswith("/notes/n1.txt") and r.get("status") == "fetched"]
    assert note and note[0]["channel"] == "speculative"


def test_budget_aware_frontier_reclaims_class_deferred_work_when_idle():
    """Class caps keep competition fair while work is pending; once nothing better
    is queued, deferred candidates may use the remaining typed and HTTP budget."""
    page = "".join(f'<img src="/img/p{i}.png">' for i in range(5))
    capped = spider(caps={"document": 50, "other_asset": 2})
    capped.observe_response(page, BASE, "text/html", {})
    site = Site({})
    drain(capped, site)
    assert len(site.requests) == 2
    reclaim = spider(caps={"document": 50, "other_asset": 2}, budget_aware_deepening=True)
    reclaim.observe_response(page, BASE, "text/html", {})
    site2 = Site({})
    records = drain(reclaim, site2)
    assert len(site2.requests) == 5 and reclaim.budget.attempted <= reclaim.budget.limit
    assert sum(r.get("queue_decision") == "budget_reclaimed" for r in records) == 3


def test_speculative_lane_honors_budget_deepening_and_defers_instead_of_dropping():
    """A deep speculative candidate must be deferred (not discarded) at pop time,
    and fetched when budget-aware deepening re-admits it."""
    pages = {"/l1": '<a href="/l2">x</a>', "/l2": "<!-- old copy at /archive/a.txt -->"}
    s = spider(depth=1, speculative=5, budget_aware_deepening=True, hard_max_depth=4)
    s.observe_response('<a href="/l1">x</a>', BASE, "text/html", {})
    site = Site(pages)
    records = drain(s, site, rounds=30)
    assert "/archive/a.txt" in site.requests
    assert not any(r.get("status") == "depth_limited" and r.get("url", "").endswith("/archive/a.txt")
                   and r.get("queue_decision") == "depth_limited" and BASE + "archive/a.txt" not in s.fetched
                   for r in records)
