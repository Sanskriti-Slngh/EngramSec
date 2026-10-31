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
    "/attach": """<div id=note style="padding:4px">Renew card</div><button id=wire
        onclick="document.getElementById('note').addEventListener('click',()=>fetch('/api/renew'))">Enable renewals</button>""",
    "/repeat": """<div id=fav style="padding:4px">Add to favourites</div>
        <script>fav.addEventListener('click',()=>fetch('/api/fav'))</script>""",
    "/disabled": """<div id=off aria-disabled=true style="padding:4px">Renew (unavailable)</div>
        <script>off.addEventListener('click',()=>fetch('/api/off'))</script>""",
    "/multi": """<div id=m style="padding:4px">Open map</div><script>
        m.addEventListener('click',()=>fetch('/api/map'));m.addEventListener('click',()=>fetch('/api/map-log'));
        m.addEventListener('mousedown',()=>{});m.addEventListener('pointerup',()=>{});</script>""",
    "/plain": """<a href="/div">Details</a> <button onclick="fetch('/api/plain')">Refresh</button>
        <form action="/plain"><input name=q><button>Search</button></form>""",
    "/many": """<button id=more onclick="var d=document.createElement('div');d.textContent='Load newer rows';
        d.addEventListener('click',()=>fetch('/api/newer'));document.body.prepend(d)">More</button><table>"""
        + "".join(f"<tr class=r><td>Row {n}</td></tr>" for n in range(400)) + """</table>
        <script>for (const r of document.querySelectorAll('.r')) r.addEventListener('click',()=>fetch('/api/row'))</script>""",
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


# --- Focused runtime-discovery regression tests (development brief, Phase 3) ---

def test_existing_element_with_a_newly_attached_listener_is_distinguished_from_a_created_one(browser, base, tmp_path):
    with session_for(browser, base, "/attach", tmp_path) as session:
        session.goto_start()
        before = session.observe(1)
        assert listener_controls(before) == []
        session.execute(next(c for c in before.controls if c.label == "Enable renewals"))
        [control] = listener_controls(session.observe(2))
        assert control.label == "Renew card"
        assert control.listener_evidence["provenance"] == "listener_attached_after_action"


def test_unchanged_listener_is_deduplicated_and_not_reinspected(browser, base, tmp_path):
    with session_for(browser, base, "/repeat", tmp_path) as session:
        session.goto_start()
        observations = [session.observe(n) for n in (1, 2, 3)]
        ids = [[c.id for c in listener_controls(o)] for o in observations]
        assert ids[0] and ids[0] == ids[1] == ids[2]                      # one control, stable identity
        first, second, third = (o.listener_evidence for o in observations)
        assert first.changes == {"present_at_first_observation": 1}
        assert second.changes == {"unchanged": 1} and third.changes == {"unchanged": 1}
        assert second.described_nodes == 0 and second.reused_nodes == 1   # incremental: cached description
        assert second.revisions == [] and third.revisions == []
        assert observations[1].behavior_signature == observations[0].behavior_signature


def test_disabled_listener_element_is_not_promoted(browser, base, tmp_path):
    with session_for(browser, base, "/disabled", tmp_path) as session:
        session.goto_start()
        observation = session.observe(1)
        assert listener_controls(observation) == []
        assert observation.listener_evidence.skipped["disabled"] == 1


def test_default_inspection_limit_on_a_large_page_prioritizes_new_nodes(browser, base, tmp_path):
    """400 listener rows (>300 DOM elements with listeners) at the default limit."""
    with session_for(browser, base, "/many", tmp_path) as session:
        assert session.config.max_listener_nodes == 300
        session.goto_start()
        first = session.observe(1)
        evidence = first.listener_evidence
        # 400 rows plus the inline onclick of the "More" button.
        assert evidence.listener_nodes == 401 and evidence.described_nodes == 300
        assert evidence.truncated and evidence.skipped["node_budget"] == 101
        session.execute(next(c for c in first.controls if c.label == "More"))
        second = session.observe(2).listener_evidence
        assert second.described_nodes <= 300
        # The node created by the action is inspected first, ahead of the 101
        # nodes never inspected before; cached nodes cost no DevTools calls.
        assert second.changes.get("created_after_action") == 1
        assert any(c["label"] == "Load newer rows" and c["provenance"] == "created_after_action" for c in second.candidates)
        assert second.reused_nodes == 300 and second.described_nodes == 102 and not second.truncated


def test_multiple_listeners_on_one_element_yield_one_control(browser, base, tmp_path):
    with session_for(browser, base, "/multi", tmp_path) as session:
        session.goto_start()
        observation = session.observe(1)
        [control] = listener_controls(observation)
        assert control.label == "Open map" and control.interaction == "click"
        [record] = observation.listener_evidence.candidates
        assert record["listener_count"] == 4 and len(record["handler_locations"]) == 4


def test_page_without_listeners_is_unchanged_by_the_observer(browser, base, tmp_path):
    results = {}
    for mode in ("off", "observe", "revisit"):
        with session_for(browser, base, "/plain", tmp_path, mode=mode) as session:
            session.goto_start()
            observation = session.observe(1)
            results[mode] = observation
            assert listener_controls(observation) == []
    for mode in ("observe", "revisit"):
        assert [c.id for c in results[mode].controls] == [c.id for c in results["off"].controls]
        assert results[mode].group_signature == results["off"].group_signature
        assert results[mode].behavior_signature == results[mode].group_signature


def test_devtools_failure_falls_back_to_the_snapshot(browser, base, tmp_path):
    with session_for(browser, base, "/div", tmp_path, mode="off") as session:
        session.goto_start()
        baseline = session.observe(1)
    with session_for(browser, base, "/div", tmp_path, mode="revisit") as session:
        session.goto_start()

        def broken(_page):
            raise RuntimeError("Target closed: DevTools session unavailable")
        session.listener_observer._cdp = broken
        observation = session.observe(1)
        assert observation.listener_evidence.error.startswith("RuntimeError")
        assert listener_controls(observation) == []
        assert [c.id for c in observation.controls] == [c.id for c in baseline.controls]
        assert observation.behavior_signature == observation.group_signature
        session.execute(next(c for c in observation.controls if c.label == "Show"))  # exploration continues


def test_navigation_starts_a_new_listener_inventory(browser, base, tmp_path):
    with session_for(browser, base, "/div", tmp_path, mode="revisit") as session:
        session.goto_start()
        first = session.observe(1)
        session.execute(next(c for c in first.controls if c.label == "Show"))
        on_div = session.observe(2)
        assert [c.label for c in listener_controls(on_div)] == ["Open details"]
        session.page.goto(base + "/repeat")
        on_repeat = session.observe(3)
        evidence = on_repeat.listener_evidence
        assert evidence.document_token != on_div.listener_evidence.document_token
        assert evidence.changes == {"present_at_first_observation": 1} and evidence.revisions == []
        assert [c.label for c in listener_controls(on_repeat)] == ["Add to favourites"]
        assert all(c.frame_url.endswith("/repeat") for c in listener_controls(on_repeat))
        session.page.reload()                                     # same URL, new document
        reloaded = session.observe(4).listener_evidence
        assert reloaded.document_token != evidence.document_token and reloaded.revisions == []
