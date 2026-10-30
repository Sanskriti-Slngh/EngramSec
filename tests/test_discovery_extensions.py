"""Independent fixtures for the optional discovery changes.

All pages, paths and names here are synthetic. They exercise general HTML/HTTP
mechanisms and budget semantics; none mirror an evaluation target.
"""
from __future__ import annotations

import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from agent1.explorer import DANGEROUS_ACTION, Explorer, HttpBudget
from agent1.exporter import build_graph_a, build_request_surfaces
from agent1.resource_spider import (
    ResourceBudget,
    TypedResourceSpider,
    extract_html_references,
    extract_references,
    extract_script_references,
)
from agent1.schema import NetworkEvent, RunArtifact, RunConfig, Transition, ActionDescriptor, utc_now

BASE = "http://127.0.0.1:9100/"


def refs(html: str, extended: bool = True, url: str = BASE + "shelf/item.html"):
    return {(r.url, r.kind, r.confidence, r.method) for r in extract_html_references(html, url, extended=extended)}


# ---------------------------------------------------------------- extraction

@pytest.mark.parametrize("markup, expected_url, kind", [
    ('<body background="/tex/linen.gif">', BASE + "tex/linen.gif", "asset"),
    ('<table><tr><td background="cell.png">', BASE + "shelf/cell.png", "asset"),
    ('<img lowsrc="/p/preview.jpg">', BASE + "p/preview.jpg", "asset"),
    ('<img dynsrc="/p/clip.avi">', BASE + "p/clip.avi", "asset"),
    ('<img longdesc="/p/about.html">', BASE + "p/about.html", "navigation"),
    ('<object codebase="/plugins/v2/"></object>', BASE + "plugins/v2/", "asset"),
    ('<html manifest="/offline.appcache">', BASE + "offline.appcache", "asset"),
    ('<svg><script xlink:href="/vec/helper.js"></script></svg>', BASE + "vec/helper.js", "asset"),
    ('<svg><script href="/vec/modern.js"></script></svg>', BASE + "vec/modern.js", "asset"),
    ('<IMPORT namespace="x" implementation="/behaviors/x.htc">', BASE + "behaviors/x.htc", "asset"),
    ('<head profile="/meta/terms"></head>', BASE + "meta/terms", "asset"),
    ('<!DOCTYPE note SYSTEM "/schemas/note.dtd">', BASE + "schemas/note.dtd", "asset"),
    ('<meta property="og:image" content="/cards/share.png">', BASE + "cards/share.png", "asset"),
])
def test_extended_html_attributes_are_extracted_only_in_extended_mode(markup, expected_url, kind):
    assert (expected_url, kind, "observed_literal", None) in refs(markup)
    assert all(url != expected_url for url, *_ in refs(markup, extended=False))


def test_base_url_is_emitted_and_applied_to_later_relative_references():
    found = refs('<base href="/library/"><a href="vol1.html">v</a><img src="cover.jpg">')
    assert (BASE + "library/", "navigation", "observed_literal", None) in found
    assert (BASE + "library/vol1.html", "navigation", "observed_literal", None) in found
    assert (BASE + "library/cover.jpg", "asset", "observed_literal", None) in found


def test_srcdoc_is_parsed_as_a_bounded_nested_document_with_parent_base():
    found = refs('<base href="/gallery/"><iframe srcdoc="<img src=\'thumb.png\'><iframe srcdoc=&quot;'
                 '<img src=deep.png><iframe srcdoc=&amp;quot;<img src=deeper.png>&amp;quot;>&quot;>"></iframe>')
    urls = {url for url, *_ in found}
    assert BASE + "gallery/thumb.png" in urls and BASE + "gallery/deep.png" in urls
    assert BASE + "gallery/deeper.png" not in urls  # nesting bound


def test_conditional_comment_markup_is_labelled_and_plain_comments_are_speculative():
    found = refs('<!--[if lt IE 9]><script src="/compat/shim.js"></script><![endif]--><!-- moved to /old/index.html -->')
    assert (BASE + "compat/shim.js", "asset", "conditional_comment", None) in found
    assert (BASE + "old/index.html", "asset", "speculative", None) in found


def test_request_surfaces_are_typed_and_never_downgraded_to_get_references():
    found = refs(
        '<a href="/news.html" ping="/audit/click"></a>'
        '<form action="/orders" method="post"><input name=q><button formaction="/orders/draft">d</button></form>'
        '<form action="/find"><input name=q></form><isindex action="/lookup">'
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'self'; report-uri /csp/reports\">"
    )
    assert (BASE + "audit/click", "ping", "observed_literal", "POST") in found
    assert (BASE + "orders", "form_action", "observed_literal", "POST") in found
    assert (BASE + "orders/draft", "form_action", "observed_literal", "POST") in found
    assert (BASE + "find", "form_action", "observed_literal", "GET") in found
    assert (BASE + "lookup", "form_action", "observed_literal", "GET") in found
    assert (BASE + "csp/reports", "security_report", "observed_literal", "POST") in found
    header_refs = extract_references("", BASE, "text/html", {"content-security-policy": "report-uri /csp/hdr"}, "ast", "extended")
    assert [(r.kind, r.method) for r in header_refs] == [("security_report", "POST")]


def test_text_candidates_are_conservative_and_speculative():
    found = refs("<p>See ./manuals/setup.pdf and https://cdn.example.net/x.js, and/or 1/2 cups. Not a/b.</p>"
                 '<div data-next="/feed/page2.json">')
    urls = {url: conf for url, _kind, conf, _m in found}
    assert urls.get(BASE + "shelf/manuals/setup.pdf") == "speculative"
    assert urls.get("https://cdn.example.net/x.js") == "speculative"
    assert urls.get(BASE + "feed/page2.json") == "speculative"
    assert not any("and/or" in url or url.endswith("/2") or url.endswith("a/b") for url in urls)


def test_script_extraction_beyond_sinks_keeps_methods_and_uncertainty():
    js = ('const base = "/media/"; const icon = base + "icons/star.svg"; // legacy: /v1/legacy.js\n'
          'var cfg = {endpoint: "https://127.0.0.1:9100/status.json"};\n'
          'const save = "/records/save"; fetch(save, {method: "PUT"}); fetch("/records/list");\n'
          'const x = new XMLHttpRequest(); x.open("DELETE", "/records/7");')
    found = {(r.url, r.kind, r.confidence, r.method, r.source) for r in extract_script_references(js, BASE, extended=True)}
    assert (BASE + "records/save", "api", "observed_literal", "PUT", "call:fetch") in found
    assert (BASE + "records/list", "api", "observed_literal", "GET", "call:fetch") in found
    assert (BASE + "records/7", "api", "observed_literal", "DELETE", "call:xhr.open") in found
    speculative = {url: source for url, _k, conf, _m, source in found if conf == "speculative"}
    assert speculative.get(BASE + "media/icons/star.svg") == "script-constant"
    assert speculative.get(BASE + "v1/legacy.js") == "script-comment"
    assert speculative.get("https://127.0.0.1:9100/status.json") == "script-literal"
    # A sink literal (here a PUT endpoint) is never re-emitted as a GET candidate.
    assert BASE + "records/save" not in speculative and BASE + "records/7" not in speculative
    baseline = extract_script_references(js, BASE)
    assert all(r.confidence == "observed_literal" and r.method is None for r in baseline)


# ---------------------------------------------------------------- spider channels

class FakeResponse:
    def __init__(self, url: str, status: int, body: str, headers: dict[str, str]):
        self.url, self.status, self._body = url, status, body.encode()
        self.headers = {"content-length": str(len(self._body)), **headers}

    def body(self) -> bytes:
        return self._body


class FakeContext:
    """Synthetic site: /hub/ lists N section pages; each section links one leaf."""

    def __init__(self, sections: int = 8):
        self.sections = sections
        self.requests: list[str] = []

    def get(self, url: str, timeout: int, max_redirects: int) -> FakeResponse:
        assert max_redirects == 0
        self.requests.append(url)
        path = urlsplit(url).path
        html = {"content-type": "text/html"}
        if path == "/hub/":
            links = "".join(f'<a href="/hub/s{i}">s{i}</a>' for i in range(self.sections))
            return FakeResponse(url, 200, links + '<a href="/account/logout">bye</a><a href="/q?token=1">t</a>', html)
        if re.fullmatch(r"/hub/s\d+", path):
            return FakeResponse(url, 308, "", {"location": path + "/"})
        if re.fullmatch(r"/hub/s\d+/", path):
            return FakeResponse(url, 200, f'<img src="{path}leaf.png"><!-- see {path}notes.txt -->', html)
        return FakeResponse(url, 200, "x", {"content-type": "image/png"})


def make_spider(allocation: str, *, http_limit: int = 200, reserve: int = 0, speculative: int = 0,
                extraction: str = "baseline", document_cap: int = 2, depth: int = 3):
    http = HttpBudget(http_limit)
    budget = ResourceBudget(100, {"document": document_cap, "other_asset": 20}, http)
    spider = TypedResourceSpider(BASE, [], budget, depth, 1_000_000, class_budgets={"document": document_cap, "other_asset": 20},
                                 extraction=extraction, allocation=allocation, passive_http_reserve=reserve,
                                 max_speculative_fetches=speculative, dangerous_pattern=DANGEROUS_ACTION)
    spider.observe_response('<a href="/hub/">hub</a>', BASE, "text/html", {})
    return spider, http


def drain(spider, context, rounds: int = 30):
    records = []
    for _ in range(rounds):
        records += spider.fetch_pending(context, 10)
    return records


def fetched_paths(records, channel=None):
    return {urlsplit(r["url"]).path for r in records
            if r.get("status") == "fetched" and (channel is None or r.get("channel") == channel)}


def test_shared_http_allocation_lifts_the_document_class_cap_and_follows_redirects_at_same_depth():
    capped, _ = make_spider("class_caps")
    capped_records = drain(capped, FakeContext())
    shared, http = make_spider("shared_http")
    context = FakeContext()
    shared_records = drain(shared, context)
    assert len([p for p in fetched_paths(capped_records) if p.startswith("/hub/s")]) <= 1
    leaves = {p for p in fetched_paths(shared_records) if p.endswith("leaf.png")}
    assert len(leaves) == 8  # every section reached despite document cap 2
    # Each section costs two charged requests (308 hop + target), at one depth level.
    hops = [r for r in shared_records if r.get("relation") == "redirect" and r.get("queue_decision") == "admitted"]
    assert len(hops) == 8 and all(h["depth"] == 2 for h in hops)
    assert http.used == len(context.requests)
    assert http.by_source["passive_document"] == sum(1 for u in context.requests if not u.endswith(".png"))


def test_passive_channel_respects_the_http_reserve_and_safety_filters():
    spider, http = make_spider("shared_http", http_limit=12, reserve=6)
    context = FakeContext()
    records = drain(spider, context)
    assert http.used <= 12 and http.by_source["passive_document"] <= 6
    assert any(r.get("queue_decision") == "budget_limited" or r.get("status") == "budget_limited" for r in records)
    assert not any("/account/logout" in u for u in context.requests)
    assert any(r.get("queue_decision") == "rejected_dangerous" for r in records)
    assert not any("token" in u for u in context.requests)


def test_speculative_candidates_are_fetched_only_under_their_own_cap():
    off, _ = make_spider("shared_http", extraction="extended")
    off_context = FakeContext(3)
    off_records = drain(off, off_context)
    assert not any(u.endswith("notes.txt") for u in off_context.requests)
    assert any(r.get("queue_decision") == "observed_only_speculative" for r in off_records)
    on, http = make_spider("shared_http", extraction="extended", speculative=2)
    on_context = FakeContext(3)
    on_records = drain(on, on_context)
    assert len([u for u in on_context.requests if u.endswith("notes.txt")]) == 2
    assert http.by_source["speculative_candidate"] == 2
    assert all(r.get("channel") == "speculative" for r in on_records
               if r.get("status") == "fetched" and r["url"].endswith("notes.txt"))


def test_observed_only_request_surfaces_are_never_fetched():
    spider, _ = make_spider("shared_http", extraction="extended")
    page = ('<form action="/forms/send" method="post"></form><form action="/forms/find"></form>'
            '<a href="/x.html" ping="/beacon"></a>'
            '<script>fetch("/data/write", {method: "POST"}); fetch("/data/read");</script>')
    spider.observe_response(page, BASE + "page.html", "text/html", {})
    context = FakeContext(0)
    records = drain(spider, context)
    for path in ("/forms/send", "/forms/find", "/beacon", "/data/write", "/data/read"):
        assert not any(urlsplit(u).path == path for u in context.requests), path
    assert urlsplit(context.requests[0]).path == "/hub/" or "/x.html" in {urlsplit(u).path for u in context.requests}


def test_observed_only_decisions_are_recorded_with_methods():
    spider, _ = make_spider("shared_http", extraction="extended")
    spider.observe_response('<form action="/forms/send" method="post"></form><a ping="/beacon" href="/y.html"></a>'
                            '<script>fetch("/data/write", {method: "POST"})</script>',
                            BASE + "page.html", "text/html", {})
    by_path = {urlsplit(r["url"]).path: r for r in spider.evidence if r.get("url")}
    assert by_path["/forms/send"]["queue_decision"] == "observed_only_form_action" and by_path["/forms/send"]["method"] == "POST"
    assert by_path["/beacon"]["queue_decision"] == "observed_only_ping"
    assert by_path["/data/write"]["queue_decision"] == "observed_only_api" and by_path["/data/write"]["method"] == "POST"


def test_checkpoint_restore_keeps_channel_counters_separate():
    spider, _ = make_spider("shared_http")
    records = drain(spider, FakeContext(4))
    restored, _ = make_spider("shared_http")
    restored.restore_from_evidence(records)
    assert restored.passive_attempted == spider.passive_attempted
    assert restored.budget.attempted == sum(1 for r in records if r.get("status") in {"fetched", "failed"}
                                            and r.get("channel") == "typed_resource")


def test_config_requires_http_budget_for_shared_allocation(tmp_path: Path):
    with pytest.raises(ValueError, match="shared_http"):
        RunConfig(start_url=BASE, output_dir=tmp_path, typed_resource_spider=True, resource_allocation="shared_http")


# ---------------------------------------------------------------- Graph A semantics

def test_non_2xx_browser_request_is_a_sent_surface_not_a_resource_or_workflow():
    action = ActionDescriptor(control_id="c", kind="button", label="Save", role="button", css_path="button", signature="s1")
    transition = Transition(
        id="t1", source_observation_id="o1", source_state_signature="a", source_group_signature="a", action=action,
        workflow_path=[action], result_observation_id="o2", result_state_signature="b", result_group_signature="b",
        status="observed", run_id="r", started_at=utc_now(), ended_at=utc_now(),
        network=[NetworkEvent(method="POST", url=BASE + "records/save", status=405, resource_type="fetch")],
    )
    artifact = RunArtifact(run_id="r", code_revision="t", config={}, started_at=utc_now(), transitions=[transition])
    surfaces = {(s["method"], s["url"]): s for s in build_request_surfaces(artifact)}
    surface = surfaces[("POST", BASE + "records/save")]
    assert surface["outcome"] == "sent_non_2xx" and surface["statuses"] == [405]
    assert not surface["in_replay_validated_workflow"]
    assert ("GET", BASE + "records/save") not in surfaces


# ---------------------------------------------------------------- live integration

class SiteHandler(BaseHTTPRequestHandler):
    """Small independent site: a hub with more sections than the document cap,
    legacy-attribute leaves, and a button that POSTs to a GET-only endpoint."""

    def log_message(self, *_args):
        pass

    def _send(self, status: int, body: str = "", ctype: str = "text/html", headers: dict | None = None):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def do_POST(self):
        self._send(405, "method not allowed", "text/plain")

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/":
            self._send(200, '<title>Home</title><a href="/wing">Wing</a><a href="/desk/">Desk</a>')
        elif path == "/wing":
            self._send(301, "", headers={"Location": "/wing/"})
        elif path == "/wing/":
            self._send(200, "<title>Wing</title>" + "".join(f'<a href="/wing/room{i}">Room {i}</a>' for i in range(6)))
        elif re.fullmatch(r"/wing/room\d", path):
            self._send(200, f'<title>{path}</title><body background="{path}/wall.gif"><img lowsrc="{path}/lo.jpg"></body>')
        elif path == "/desk/":
            self._send(200, '<title>Desk</title><button onclick="fetch(\'/desk/commit\', {method: \'POST\'})">Commit</button>')
        elif path.endswith((".gif", ".jpg")):
            self._send(200, "GIF89a", "image/gif")
        else:
            self._send(404, "missing")


@pytest.fixture(scope="module")
def site_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), SiteHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()


def run_site(site_url: str, tmp_path: Path, allocation: str, extraction: str):
    config = RunConfig(
        start_url=site_url, output_dir=tmp_path / f"{allocation}-{extraction}", policy="multidimensional",
        exploration_mode="persistent", max_seconds=25, max_transitions=4, max_browser_actions=12, settle_ms=0,
        typed_resource_spider=True, max_resource_fetches=20, max_resource_document_fetches=2,
        max_resource_asset_fetches=20, max_total_http_requests=200, resource_allocation=allocation,
        html_extraction=extraction,
    )
    return Explorer(config, Path(__file__).resolve().parents[1]).run()


def test_live_combined_mode_reaches_more_documents_without_new_ui_transitions(site_url: str, tmp_path: Path):
    baseline = run_site(site_url, tmp_path, "class_caps", "baseline")
    combined = run_site(site_url, tmp_path, "shared_http", "extended")
    def fetched(artifact, suffix):
        return {urlsplit(r.url).path for r in artifact.resource_evidence
                if r.url and r.status == "fetched" and urlsplit(r.url).path.endswith(suffix)}
    assert len(fetched(combined, (".gif", ".jpg"))) > len(fetched(baseline, (".gif", ".jpg")))
    assert combined.metrics.passive_document_fetches > 0
    assert combined.metrics.effective_resource_budgets["document_class_cap"] is None
    assert baseline.metrics.effective_resource_budgets["document_class_cap"] == 2
    # Passively fetched documents never become UI transitions.
    transition_targets = {urlsplit(step.target or "").path for t in combined.transitions for step in t.workflow_path}
    passive_only = {urlsplit(r.url).path for r in combined.resource_evidence
                    if r.channel == "passive_document" and r.status == "fetched"} - transition_targets
    assert passive_only
    observed_ids = {o.id for o in combined.observations}
    assert all(t.result_observation_id in observed_ids for t in combined.transitions if t.result_observation_id)
    graph = build_graph_a(combined)
    assert graph["metrics"]["graph_connections_missing_evidence"] == 0
    surfaces = {(s["method"], urlsplit(s["url"]).path): s for s in graph["request_surfaces"]}
    commit = surfaces.get(("POST", "/desk/commit"))
    assert commit is not None and commit["outcome"] == "sent_non_2xx" and commit["statuses"] == [405]
    assert commit["sent_by"] == ["browser_action"] and not commit["in_replay_validated_workflow"]
    assert ("GET", "/desk/commit") not in surfaces


def test_shared_http_depth_is_the_minimum_over_discovery_paths():
    """A page first reached on a long chain must not stay depth-capped once it is
    observed directly (e.g. by the browser)."""
    spider, _ = make_spider("shared_http", depth=2)
    context = FakeContext(2)
    drain(spider, context)
    # /hub/s0/ was reached at depth 2 (via 308 hop), so its leaf at depth 3 was capped.
    assert not any(u.endswith("/hub/s0/leaf.png") for u in context.requests)
    assert "http://127.0.0.1:9100/hub/s0/leaf.png" in spider._capped
    # The browser now observes /hub/s0/ directly: its references are depth 1.
    spider.observe_response('<img src="/hub/s0/leaf.png">', BASE + "hub/s0/", "text/html", {})
    records = drain(spider, context)
    assert any(u.endswith("/hub/s0/leaf.png") for u in context.requests)
    assert not any(u.endswith("/hub/s1/leaf.png") for u in context.requests)  # still capped: not rediscovered
    # Frozen baseline: /hub/s1/ was first discovered (via a redirect Location) at
    # the depth limit; rediscovering it at depth 1 does not re-admit it.
    baseline, _ = make_spider("class_caps", depth=2, document_cap=50)
    base_context = FakeContext(2)
    drain(baseline, base_context)
    assert not any(u.endswith("/hub/s1/") for u in base_context.requests)
    baseline.observe_response('<a href="/hub/s1/">s1</a>', BASE + "hub/", "text/html", {})
    drain(baseline, base_context)
    assert not any(u.endswith("/hub/s1/") for u in base_context.requests)


def test_reserve_bounds_the_passive_share_not_other_traffic():
    """Browser traffic must not starve the passive channel below its share, and
    the passive channel must never take the reserved share."""
    spider, http = make_spider("shared_http", http_limit=40, reserve=20)
    for _ in range(15):
        assert http.consume("browser")  # 15 browser requests already spent
    context = FakeContext(30)  # 61 documents available, more than the share
    drain(spider, context)
    assert http.by_source["passive_document"] == 20  # full share despite browser use
    assert http.used <= http.limit and http.by_source["passive_document"] + http.by_source["speculative_candidate"] <= 40 - 20
