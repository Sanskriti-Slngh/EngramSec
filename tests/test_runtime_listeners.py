"""Phase 2/3 tests: bounded DevTools listener observation, handler revisions,
and their Graph A evidence. Synthetic localhost pages only."""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from agent1.explorer import BrowserSession, Explorer, SNAPSHOT_SELECTOR
from agent1.exporter import build_graph_a
from agent1.listeners import ListenerObserver
from agent1.schema import EvidenceStatus, RunConfig

HITS: list[str] = []
PAGES = {
    "/div": """<button id=go onclick="var d=document.createElement('div');d.textContent='Open details';
        d.addEventListener('click',()=>fetch('/api/details'));document.body.append(d)">Show</button>""",
    "/redefine": """<button id=go onclick="fetch('/api/first');this.onclick=()=>fetch('/api/second')">Step</button>""",
    "/delegation": """<ul><li><span data-id=1>Alpha</span></li><li><span data-id=2>Beta</span></li></ul>
        <script>document.addEventListener('click',e=>{const t=e.target.closest('[data-id]');if(t)fetch('/api/item/'+t.dataset.id)})</script>""",
    "/danger": """<div id=wipe style="padding:4px">Delete everything</div>
        <script>wipe.addEventListener('click',()=>fetch('/api/wipe',{method:'POST'}))</script>""",
    "/hidden": """<div id=a style="display:none">Hidden</div><div id=b style="width:0;height:0;overflow:hidden">Zero</div>
        <script>for (const id of ['a','b']) document.getElementById(id).addEventListener('click',()=>fetch('/api/h'))</script>""",
    "/shadow": """<x-open></x-open><x-closed></x-closed><script>
        for (const [tag, mode] of [['x-open','open'],['x-closed','closed']]) customElements.define(tag, class extends HTMLElement {
          connectedCallback(){ const r=this.attachShadow({mode}); const d=document.createElement('div'); d.textContent=mode+' panel';
          d.style.padding='4px'; d.addEventListener('click',()=>fetch('/api/'+mode)); r.append(d);} });</script>""",
    "/frame": """<iframe src="/frame-inner" width=300 height=80></iframe>""",
    "/frame-inner": """<span id=c style="display:inline-block;padding:4px">Cite</span>
        <script>c.addEventListener('click',()=>fetch('/api/cite'))</script>""",
    "/rows": "<table>" + "".join(f"<tr class=r><td>Row {n}</td></tr>" for n in range(50)) + """</table>
        <script>for (const r of document.querySelectorAll('.r')) r.addEventListener('click',()=>fetch('/api/row'))</script>""",
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _send(self, body: bytes, ctype: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/api/"):
            HITS.append(path)
            return self._send(b"{}", "application/json")
        if path == "/":
            links = "".join(f'<a href="{p}">{p.strip("/")}</a> ' for p in ("/div", "/redefine"))
            return self._send(f"<!doctype html><title>Home</title><main>{links}</main>".encode(), "text/html")
        if path in PAGES:
            return self._send(f"<!doctype html><title>{path}</title><body><main>{PAGES[path]}</main></body>".encode(), "text/html")
        self._send(b"no", "text/plain", 404)

    def do_POST(self):
        HITS.append("POST " + self.path)
        self._send(b"{}", "application/json")


@pytest.fixture(scope="module")
def base():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown(); server.server_close()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            yield b
        finally:
            b.close()


def session_for(browser, base, path, tmp_path, mode="observe", **kw):
    config = RunConfig(start_url=base + path, output_dir=tmp_path, settle_ms=150, runtime_listener_observation=mode,
                       interaction_profile="extended", **kw)
    return BrowserSession(browser, config)


def listener_controls(observation):
    return [c for c in observation.controls if c.provenance == "observed_listener"]


def test_listener_div_created_by_an_action_becomes_a_candidate_with_provenance(browser, base, tmp_path):
    with session_for(browser, base, "/div", tmp_path) as session:
        session.goto_start()
        before = session.observe(1)
        assert listener_controls(before) == []
        go = next(c for c in before.controls if c.label == "Show")
        session.execute(go)
        after = session.observe(2)
        [control] = listener_controls(after)
        assert control.label == "Open details" and control.safe and control.kind == "button"
        assert control.listener_evidence["provenance"] == "created_after_action"
        assert control.listener_evidence["caused_by_action"] == go.signature
        HITS.clear()
        session.execute(control)
        assert "/api/details" in HITS


def test_handler_revision_is_evidence_in_observe_mode_and_a_revision_in_revisit_mode(browser, base, tmp_path):
    for mode in ("observe", "revisit"):
        with session_for(browser, base, "/redefine", tmp_path, mode=mode) as session:
            session.goto_start()
            before = session.observe(1)
            go = next(c for c in before.controls if c.label == "Step")
            session.execute(go)
            after = session.observe(2)
            assert after.group_signature == before.group_signature           # same visible DOM
            assert after.behavior_signature != after.group_signature         # different handler behavior
            [revision] = after.listener_evidence.revisions
            assert revision["snapshot_control"] and revision["caused_by_action"] == go.signature
            revised = next(c for c in after.controls if c.label == "Step")
            assert (revised.behavior_revision is not None) == (mode == "revisit")
            # Same document, no further change: the revision stays active.
            third = session.observe(3)
            assert third.listener_evidence.revisions == [] and third.listener_evidence.active_revisions


def test_delegated_listener_is_not_attributed_to_descendants(browser, base, tmp_path):
    with session_for(browser, base, "/delegation", tmp_path) as session:
        session.goto_start()
        observation = session.observe(1)
        assert listener_controls(observation) == []
        assert observation.listener_evidence.skipped.get("delegation_host", 0) >= 1


def test_listener_alone_never_authorizes_an_unsafe_action(browser, base, tmp_path):
    with session_for(browser, base, "/danger", tmp_path) as session:
        session.goto_start()
        [control] = listener_controls(session.observe(1))
        assert not control.safe and control.skip_reason == "dangerous_label_or_target"


def test_hidden_and_zero_size_listener_elements_are_skipped(browser, base, tmp_path):
    with session_for(browser, base, "/hidden", tmp_path) as session:
        session.goto_start()
        observation = session.observe(1)
        assert listener_controls(observation) == []
        assert observation.listener_evidence.skipped["not_rendered"] == 2


def test_open_shadow_candidates_execute_and_closed_shadow_is_reported(browser, base, tmp_path):
    with session_for(browser, base, "/shadow", tmp_path) as session:
        session.goto_start()
        observation = session.observe(1)
        [control] = listener_controls(observation)
        assert control.label == "open panel" and " >> " in control.css_path
        assert observation.listener_evidence.skipped["closed_shadow_root"] == 1
        HITS.clear()
        session.execute(control)
        assert "/api/open" in HITS and "/api/closed" not in HITS


def test_same_origin_frame_candidates_keep_their_frame(browser, base, tmp_path):
    with session_for(browser, base, "/frame", tmp_path) as session:
        session.goto_start()
        session.page.wait_for_timeout(300)
        [control] = listener_controls(session.observe(1))
        assert control.frame_index == 1 and control.frame_url.endswith("/frame-inner")
        HITS.clear()
        session.execute(control)
        assert "/api/cite" in HITS


def test_inspection_work_is_bounded_and_skips_are_counted(browser, base, tmp_path):
    with session_for(browser, base, "/rows", tmp_path, max_listener_nodes=10) as session:
        session.goto_start()
        evidence = session.observe(1).listener_evidence
        assert evidence.described_nodes == 10 and evidence.skipped["node_budget"] == 40
        assert len(evidence.candidates) == 2 and evidence.skipped["family_limit"] == 8


def test_observer_is_off_by_default_and_reports_unsupported_engines(browser, base, tmp_path):
    with session_for(browser, base, "/div", tmp_path, mode="off") as session:
        session.goto_start()
        assert session.observe(1).listener_evidence is None

    class Engine:
        name = "firefox"

    class FakeBrowser:
        browser_type = Engine()

    class FakeContext:
        browser = FakeBrowser()

    class FakePage:
        context = FakeContext()

    snapshot = ListenerObserver(SNAPSHOT_SELECTOR).observe(FakePage(), None)
    assert not snapshot.supported and snapshot.error == "unsupported_engine:firefox"
