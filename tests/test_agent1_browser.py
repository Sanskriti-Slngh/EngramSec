from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from agent1.explorer import BrowserSession, Explorer, HttpBudget
from agent1.exporter import build_graph_a, mermaid, write_outputs
from agent1.schema import EvidenceStatus, RunConfig


class FixtureHandler(BaseHTTPRequestHandler):
    def _html(self, body: str, status: int = 200, headers: dict[str, str] | None = None) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._html(
                """<html><title>Fixture Home</title><body>
                <a href="/setup">Account setup</a>
                <a href="/catalog/1">Catalog item 1</a>
                <a href="/catalog/2">Catalog item 2</a>
                <a href="/interactions">Interaction gallery</a>
                <button id="reveal" onclick="document.querySelector('#panel').hidden=false; this.remove()">Reveal details</button>
                <section id="panel" hidden><h2>Revealed details</h2></section>
                </body></html>"""
            )
        elif path == "/interactions":
            self._html(
                """<html><title>Interaction gallery</title><body>
                <nav><a href="/">Home</a></nav>
                <main>
                <button id="hover" aria-haspopup="true"
                  onmouseover="document.querySelector('#hover-result').hidden=false">Hover menu</button>
                <p id="hover-result" hidden>Hover revealed content</p>
                <button id="double" ondblclick="this.textContent='Double complete'">Double target</button>
                <button id="context" oncontextmenu="event.preventDefault();this.textContent='Context complete'">Context target</button>
                <button id="keyboard" onkeydown="if(event.key==='Enter')this.textContent='Keyboard complete'">Keyboard target</button>
                <button id="popup" onclick="window.open('/popup','fixture-popup')">Open popup</button>
                <section class="control-area">
                  <p>Right-click (contextmenu) the target below to reveal content.</p>
                  <div id="listener-zone" style="width:200px;height:40px">Listener target</div>
                </section>
                <div id="shadow-host"></div>
                <iframe src="/frame"></iframe>
                <script>
                  const root = document.querySelector('#shadow-host').attachShadow({mode:'open'});
                  root.innerHTML = `<button id="shadow-button" onclick="this.textContent='Shadow complete'">Shadow target</button>`;
                  document.querySelector('#listener-zone').addEventListener('contextmenu', event => {
                    event.preventDefault(); event.currentTarget.textContent = 'Listener complete';
                  });
                </script>
                </main>
                </body></html>"""
            )
        elif path == "/frame":
            self._html(
                "<html><title>Frame</title><body><button id='frame-button' "
                "onclick=\"this.textContent='Frame complete'\">Frame target</button></body></html>"
            )
        elif path == "/popup":
            self._html("<html><title>Popup destination</title><body>Popup evidence</body></html>")
        elif path == "/late-control":
            self._html(
                "<html><title>Late control</title><body><main><div id='mount'></div>"
                "<script>setTimeout(()=>{const b=document.createElement('button');"
                "b.textContent='Hydrated control';document.querySelector('#mount').append(b)},350)</script>"
                "</main></body></html>"
            )
        elif path == "/litegraph-mock":
            # A canvas app that exposes a LiteGraph model via JS globals (as ComfyUI does). The DOM has
            # only a <canvas>; the functionality (node types + placed nodes) lives in the JS model. This
            # mock is drivable: createNode() returns typed I/O schemas and graph.add/remove work.
            self._html(
                "<html><title>Canvas</title><body><canvas id='c' width='200' height='200'></canvas>"
                "<script>"
                "const SCHEMAS={"
                "KSampler:{title:'KSampler',inputs:[{name:'model',type:'MODEL'},{name:'seed',type:'INT'}],"
                "outputs:[{name:'LATENT',type:'LATENT'}],widgets:[{name:'seed',type:'number',value:0}]},"
                "LoadImage:{title:'Load Image',inputs:[{name:'image',type:'COMBO'}],outputs:[{name:'IMAGE',type:'IMAGE'}],widgets:[]},"
                "SaveImage:{title:'Save Image',inputs:[{name:'images',type:'IMAGE'}],outputs:[],widgets:[]},"
                "CLIPTextEncode:{title:'CLIP',inputs:[{name:'text',type:'STRING'}],outputs:[{name:'CONDITIONING',type:'CONDITIONING'}],widgets:[{name:'text',type:'customtext',value:''}]},"
                "Note:{title:'Note',inputs:[],outputs:[],widgets:[{name:'text',type:'text',value:''}]}};"
                "window.LiteGraph={registered_node_types:{KSampler:1,LoadImage:1,SaveImage:1,CLIPTextEncode:1,Note:1},"
                "createNode:function(t){const s=SCHEMAS[t];if(!s)return null;"
                "return {type:t,title:s.title,pos:[0,0],inputs:s.inputs,outputs:s.outputs,widgets:s.widgets};}};"
                "window.app={graph:{_nodes:["
                "{id:1,type:'KSampler',title:'KSampler',pos:[10,20],widgets:[{name:'seed',value:42},{name:'steps',value:20}]},"
                "{id:2,type:'LoadImage',title:'Load Image',pos:[200,20],widgets:[]}],"
                "links:{},add:function(n){this._nodes.push(n);},remove:function(n){const i=this._nodes.indexOf(n);if(i>=0)this._nodes.splice(i,1);}}};"
                "</script></body></html>"
            )
        elif path == "/comfy-exec-mock":
            # A LiteGraph app exposing a workflow-execution mechanism (app.graphToPrompt + POST /prompt).
            self._html(
                "<html><title>Exec</title><body><canvas></canvas><script>"
                "window.LiteGraph={registered_node_types:{Note:1},"
                "createNode:function(t){return {type:t,title:t,pos:[0,0],inputs:[],outputs:[],widgets:[{name:'text',value:''}]};}};"
                "window.app={graph:{_nodes:[],add:function(n){this._nodes.push(n);},remove:function(n){const i=this._nodes.indexOf(n);if(i>=0)this._nodes.splice(i,1);}},"
                "graphToPrompt:async function(){return {output:{'1':{class_type:'Note'}}};}};"
                "</script></body></html>"
            )
        elif path == "/reactflow-mock":
            # React Flow renders nodes as DOM elements (not canvas) — extractable from the DOM.
            self._html(
                "<html><title>Flow</title><body><div class='react-flow'><div class='react-flow__renderer'>"
                "<div class='react-flow__node react-flow__node-input' data-id='n1'>Start</div>"
                "<div class='react-flow__node react-flow__node-default' data-id='n2'>Process</div>"
                "<div class='react-flow__edge' data-source='n1' data-target='n2'></div>"
                "</div></div></body></html>"
            )
        elif path == "/generic-graph-mock":
            # A graph editor stored on an arbitrary global, exposing getNodes() — caught by the sweep.
            self._html(
                "<html><title>Editor</title><body><canvas></canvas><script>"
                "window.myEditor={getNodes:function(){return ["
                "{id:'a',label:'Source',type:'source'},{id:'b',label:'Sink',type:'sink'}];}};"
                "</script></body></html>"
            )
        elif path == "/cytoscape-mock":
            self._html(
                "<html><title>Cy</title><body><canvas></canvas><script>"
                "const N=[{id:'x',label:'X',type:'t1'},{id:'y',label:'Y',type:'t2'}];"
                "const E=[{source:'x',target:'y'}];"
                "window.cytoscape=function(){};"
                "window.cy={nodes:function(){return N.map(d=>({id:()=>d.id,data:k=>d[k]}));},"
                "edges:function(){return E.map(d=>({data:k=>d[k]}));}};"
                "</script></body></html>"
            )
        elif path == "/login-form":
            # A minimal SPA-style login: on submit, JS writes BOTH a cookie and a localStorage flag,
            # then changes the URL. Exercises the UI-login helper capturing full client state.
            self._html(
                "<html><title>Login</title><body><main><form id='f'>"
                "<input name='username' type='text' placeholder='user'>"
                "<input name='password' type='password' placeholder='pass'>"
                "<button type='submit'>Sign in</button></form>"
                "<script>document.querySelector('#f').addEventListener('submit', e => {"
                "e.preventDefault();"
                "const u=document.querySelector('[name=username]').value;"
                "window.localStorage.setItem('app_user', JSON.stringify(u));"
                "document.cookie='app_session=ok; path=/';"
                "location.href='/?logged_in=1';});</script></main></body></html>"
            )
        elif path == "/writes-on-load":
            # An SPA that performs a benign write during init (as comfyui PUTs a setting). Under the
            # read-only policy the write is denied: aborting makes fetch() reject (#write-failed),
            # neutralizing fulfils it so fetch() resolves (#after-write) and init continues.
            self._html(
                "<html><title>Writes on load</title><body><main><div id='root'></div>"
                "<script>"
                "fetch('/api/persist',{method:'PUT',body:'{}'})"
                ".then(()=>{const b=document.createElement('button');b.id='after-write';"
                "b.textContent='After write';document.querySelector('#root').appendChild(b);})"
                ".catch(()=>{const b=document.createElement('button');b.id='write-failed';"
                "b.textContent='Write failed';document.querySelector('#root').appendChild(b);});"
                "</script></main></body></html>"
            )
        elif path == "/blob-script":
            # Loads a script from a blob: URL (as comfyui does for its module/worker code). The scope
            # router must not abort it; if it does, #from-blob never appears.
            self._html(
                "<html><title>Blob script</title><body><main><div id='root'></div>"
                "<script>"
                "const code=\"const b=document.createElement('button');b.id='from-blob';"
                "b.textContent='Blob control';document.querySelector('#root').appendChild(b);\";"
                "const u=URL.createObjectURL(new Blob([code],{type:'text/javascript'}));"
                "const s=document.createElement('script');s.src=u;document.body.appendChild(s);"
                "</script></main></body></html>"
            )
        elif path == "/scripted-shell":
            # A scripted shell with NO actionable controls (like a heavy SPA still building its DOM).
            # readiness_await_content should keep waiting; default readiness declares it usable fast.
            self._html(
                "<html><title>Scripted shell</title><body><div id='root'></div>"
                "<script>void 0;</script></body></html>"
            )
        elif path == "/out-of-main":
            # Controls are enabled and present immediately, but rendered OUTSIDE any <main>
            # (as many SPAs do). A <script> is present so the readiness branch treats it as a
            # scripted page. There is nothing to hydrate; readiness_any_enabled should exit fast.
            self._html(
                "<html><title>Out of main</title><body>"
                "<nav><a href='/'>Home</a></nav>"
                "<div id='app'><button id='a'>Action A</button>"
                "<button id='b'>Action B</button><a href='/catalog/1'>Deep link</a></div>"
                "<script>void 0;</script></body></html>"
            )
        elif path == "/budget-redirect":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/redirected")
            self.end_headers()
        elif path == "/budget-redirect-chain":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/budget-redirect")
            self.end_headers()
        elif path == "/delayed-refresh":
            self._html(
                "<html><head><meta http-equiv='refresh' content='0.5;url=/redirected'></head>"
                "<body><p>Waiting for the delayed redirect.</p></body></html>"
            )
        elif path == "/redirected":
            self._html("<html><title>Redirect destination</title><body><main>Reached destination.</main></body></html>")
        elif path.startswith("/catalog/"):
            item = path.rsplit("/", 1)[-1]
            self._html(
                f"<html><title>Catalog item {item}</title><body><h1>Item {item}</h1>"
                '<a href="/">Home</a><form method="GET" action="/search">'
                '<label>Search <input name="q" type="search"></label><button>Search</button></form></body></html>'
            )
        elif path == "/search":
            query = parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "").get("q", [""])[0]
            self._html(f"<html><title>Search results</title><body><h1>Results</h1><p>{query}</p></body></html>")
        elif path == "/setup":
            self._html(
                """<html><title>Setup</title><body><form method="POST" action="/session">
                <label>Display name <input name="display_name" required></label>
                <button type="submit">Create test session</button></form></body></html>"""
            )
        elif path == "/private":
            if "fixture_session=ready" in (self.headers.get("Cookie") or ""):
                self._html("<html><title>Private ready</title><body><h1>Session ready</h1></body></html>")
            else:
                self._html("<html><title>Setup required</title><body><h1>Missing prerequisite</h1></body></html>", 403)
        else:
            self._html("<html><title>Not found</title></html>", 404)

    def do_POST(self) -> None:
        if self.path == "/prompt":
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            self._html('{"prompt_id":"pid-123","number":1}', 200)
            return
        if self.path != "/session":
            self._html("<html><title>Not found</title></html>", 404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", "/private")
        self.send_header("Set-Cookie", "fixture_session=ready; HttpOnly; SameSite=Lax")
        self.end_headers()

    def log_message(self, *_: object) -> None:
        pass


@pytest.fixture(scope="module")
def fixture_url() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()


def test_live_pipeline_records_and_replays_prerequisite_paths(
    fixture_url: str, tmp_path: Path
) -> None:
    output = tmp_path / "run"
    config = RunConfig(
        start_url=fixture_url,
        output_dir=output,
        policy="grouped",
        max_seconds=25,
        max_transitions=7,
        max_browser_actions=70,
        settle_ms=50,
        allow_post_forms=True,
    )
    artifact = Explorer(config, Path(__file__).resolve().parents[1]).run()
    write_outputs(artifact, output)
    assert artifact.metrics.transitions_observed >= 3
    assert artifact.metrics.replay_success_denominator > 0
    assert artifact.metrics.replay_success_numerator > 0
    assert artifact.metrics.distinct_validated_feature_workflows > 0
    assert any(
        transition.input_references and transition.status == EvidenceStatus.REPLAY_VALIDATED
        for transition in artifact.transitions
    )
    assert all(reference.protected for transition in artifact.transitions for reference in transition.input_references)
    member_observations = [
        item for item in artifact.observations
        if "fixture_session" in item.session_markers.get("cookie_names", [])
    ]
    assert member_observations
    assert all(set(item.session_markers) == {
        "cookie_names", "local_storage_keys", "session_storage_keys"
    } for item in member_observations)
    assert all("ready" not in json.dumps(item.session_markers) for item in member_observations)
    assert (output / "graph_a.json").exists()
    graph = json.loads((output / "graph_a.json").read_text(encoding="utf-8"))
    assert graph["nodes"]["features"]
    assert graph["replays"]


def test_external_seed_is_fetched_separately_and_http_budget_is_shared(
    fixture_url: str, tmp_path: Path
) -> None:
    source = tmp_path / "zap.json"
    source.write_text(json.dumps({
        "schema": "zap-http-history-1", "run_id": "fixture",
        "source_origin": "http://crawlmaze:3460", "request_upper_bound": 3,
        "elapsed_seconds": 1.0,
        "records": [{"path": "/catalog/1", "method": "GET", "status": 200, "parameter_names": []}],
    }))
    config = RunConfig(
        start_url=fixture_url, output_dir=tmp_path / "budgeted", policy="hierarchical",
        exploration_mode="persistent", max_seconds=12, max_transitions=1,
        max_browser_actions=20, settle_ms=0, typed_resource_spider=True,
        max_resource_fetches=2, max_total_http_requests=10,
        zap_evidence_path=source, zap_source_origin="http://crawlmaze:3460",
    )
    artifact = Explorer(config, Path(__file__).resolve().parents[1]).run()
    graph = build_graph_a(artifact)
    assert artifact.metrics.total_http_budget_used <= 10
    assert artifact.metrics.external_request_upper_bound == 3
    assert len(graph["nodes"]["external_discoveries"]) == 1
    assert any(edge["type"] == "external_report" for edge in graph["edges"])
    assert any(edge["type"] == "agent_seed_fetch" for edge in graph["edges"])
    assert all(item["status"] != "replay_validated" for item in graph["nodes"]["external_discoveries"])


def test_http_budget_counts_redirect_requests(fixture_url: str, tmp_path: Path) -> None:
    from playwright.sync_api import sync_playwright
    config = RunConfig(start_url=f"{fixture_url}budget-redirect", output_dir=tmp_path, settle_ms=0)
    budget = HttpBudget(10)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            with BrowserSession(browser, config, http_budget=budget) as session:
                session.goto_start()
                assert session.page and session.page.url.endswith("/redirected")
            assert budget.used == 2
            assert budget.redirect_overrun == 0
        finally:
            browser.close()


def test_http_budget_charges_unrouted_chain_hops_once_and_refuses_when_exhausted(
    fixture_url: str, tmp_path: Path
) -> None:
    from playwright.sync_api import sync_playwright
    chain = RunConfig(start_url=f"{fixture_url}budget-redirect-chain", output_dir=tmp_path, settle_ms=0)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            # Three wire requests: the routed first hop and two unrouted redirect hops.
            budget = HttpBudget(10)
            with BrowserSession(browser, chain, http_budget=budget) as session:
                session.goto_start()
                assert session.page and session.page.url.endswith("/redirected")
            assert budget.used == 3
            assert dict(budget.by_source) == {"browser": 1, "browser_redirect": 2}
            assert budget.redirect_overrun == 0 and budget.redirect_scope_violations == 0
            # With one request left, the 302 is refused before the browser can follow it.
            exhausted = HttpBudget(1)
            single = RunConfig(start_url=f"{fixture_url}budget-redirect", output_dir=tmp_path, settle_ms=0)
            with BrowserSession(browser, single, http_budget=exhausted) as session:
                with pytest.raises(Exception, match="ERR_BLOCKED_BY_CLIENT"):
                    session.goto_start()
            assert exhausted.used == 1 and exhausted.blocked >= 1
            assert exhausted.redirect_overrun == 0
        finally:
            browser.close()


def test_checkpoint_resume_preserves_run_and_advances_frontier(
    fixture_url: str, tmp_path: Path
) -> None:
    output = tmp_path / "resume"
    first = RunConfig(
        start_url=fixture_url,
        output_dir=output,
        policy="grouped",
        max_seconds=12,
        max_transitions=1,
        max_browser_actions=20,
        settle_ms=25,
        replay_reserve_fraction=0.2,
    )
    initial = Explorer(first, Path(__file__).resolve().parents[1]).run()
    assert (output / "checkpoint.json").exists()
    initial_count = len(initial.transitions)
    resumed_config = first.model_copy(
        update={
            "resume_from": output / "checkpoint.json",
            "max_transitions": 3,
            "max_browser_actions": 45,
            "max_seconds": 18,
        }
    )
    resumed = Explorer(resumed_config, Path(__file__).resolve().parents[1]).run()
    assert resumed.run_id == initial.run_id
    assert len(resumed.transitions) > initial_count
    assert any("Resumed from checkpoint" in note for note in resumed.notes)


def test_typed_spider_is_exported_as_candidates_separate_from_browser_actions(
    fixture_url: str, tmp_path: Path
) -> None:
    output = tmp_path / "typed-spider"
    config = RunConfig(
        start_url=fixture_url,
        output_dir=output,
        policy="breadth",
        max_seconds=12,
        max_transitions=6,
        max_browser_actions=30,
        settle_ms=10,
        typed_resource_spider=True,
        max_resource_fetches=8,
        max_resource_depth=2,
    )
    artifact = Explorer(config, Path(__file__).resolve().parents[1]).run()
    assert artifact.metrics.resource_fetches_attempted <= 8
    assert artifact.metrics.resource_fetches_succeeded > 0
    assert artifact.resource_evidence
    assert any(item.kind == "navigation" for item in artifact.resource_evidence)
    assert any(transition.restoration_attempted for transition in artifact.transitions)
    assert artifact.metrics.browser_actions <= 30
    graph = build_graph_a(artifact)
    assert graph["resource_evidence"]
    assert graph["nodes"]["resource_references"]
    assert graph["nodes"]["resource_source_responses"]
    assert any(edge["type"] == "references" for edge in graph["edges"])
    assert all(
        item["complete"]
        for item in graph["connection_evidence"]
        if item["claim_type"] in {"resource_reference", "prerequisite_network"}
    )
    assert graph["metrics"]["graph_connections_missing_evidence"] == 0
    assert graph["metrics"]["resource_fetches_attempted"] <= 8
    preserved_browser_events = (
        sum(len(item.get("network", [])) for item in graph["navigation_evidence"])
        + sum(len(item.get("network", [])) for item in graph["nodes"]["actions_evidence"])
        + sum(
            len(step.get("network", []))
            for item in graph["nodes"]["actions_evidence"]
            for step in item.get("prerequisite_network", [])
        )
        + sum(len(item.get("network", [])) for item in graph["replays"])
    )
    assert graph["metrics"]["network_events_recorded"] == preserved_browser_events
    assert graph["metrics"]["observed_http_requests"] == preserved_browser_events
    diagram = mermaid(graph)
    assert "HTTP response" in diagram or "Response 127.0.0.1" in diagram
    assert "fetched" in diagram
    assert "_resource_diagram_labels" not in graph


def test_extended_interaction_engine_observes_frames_shadow_and_popup(
    fixture_url: str, tmp_path: Path
) -> None:
    from playwright.sync_api import sync_playwright

    config = RunConfig(
        start_url=f"{fixture_url}interactions",
        output_dir=tmp_path / "extended",
        policy="multidimensional",
        max_seconds=15,
        max_transitions=10,
        max_browser_actions=40,
        settle_ms=25,
        interaction_profile="extended",
        hybrid_link_discovery=True,
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            with BrowserSession(browser, config) as session:
                session.goto_start()
                observed = session.observe(1)
                interactions = {control.interaction for control in observed.controls}
                assert {"hover", "double_click", "context_menu", "key_enter"} <= interactions
                assert any(control.frame_index > 0 for control in observed.controls)
                assert any(control.label == "Shadow target" for control in observed.controls)
                assert any(
                    control.label == "Listener target" and control.interaction == "context_menu"
                    for control in observed.controls
                )
                assert not any(
                    control.label == "Home" and control.interaction != "navigate"
                    for control in observed.controls
                )

                listener = next(
                    control for control in observed.controls
                    if control.label == "Listener target" and control.interaction == "context_menu"
                )
                session.execute(listener)
                assert "Listener complete" in session.observe(2).meaningful_text

                session.goto_start()
                observed = session.observe(3)
                hover = next(
                    control for control in observed.controls
                    if control.label == "Hover menu" and control.interaction == "hover"
                )
                session.execute(hover)
                assert "Hover revealed content" in session.observe(4).meaningful_text

                session.goto_start()
                frame_observation = session.observe(5)
                frame_control = next(
                    control for control in frame_observation.controls
                    if control.label == "Frame target"
                )
                session.execute(frame_control)
                assert "Frame complete" in session.observe(6).meaningful_text

                session.goto_start()
                shadow_observation = session.observe(7)
                shadow_control = next(
                    control for control in shadow_observation.controls
                    if control.label == "Shadow target"
                )
                session.execute(shadow_control)
                assert "Shadow complete" in session.observe(8).meaningful_text

                session.goto_start()
                popup_observation = session.observe(9)
                popup = next(
                    control for control in popup_observation.controls
                    if control.label == "Open popup" and control.interaction == "click"
                )
                session.execute(popup)
                assert session.last_popup_opened
                assert session.page and session.page.title() == "Popup destination"
        finally:
            browser.close()


def test_readiness_waits_for_late_control_and_delayed_redirect(
    fixture_url: str, tmp_path: Path
) -> None:
    from playwright.sync_api import sync_playwright

    config = RunConfig(
        start_url=f"{fixture_url}late-control",
        output_dir=tmp_path / "readiness",
        robust_readiness=True,
        readiness_timeout_ms=2_500,
        readiness_poll_ms=50,
        idle_page_wait_ms=1_600,
        passive_page_wait_ms=100,
        readiness_strategy="adaptive",
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            with BrowserSession(browser, config) as session:
                session.goto_start()
                late = session.observe(1)
                assert any(item.label == "Hydrated control" for item in late.controls)
                assert late.readiness.status == "usable"
                assert 300 <= late.readiness.duration_ms <= 1_500

                session.config = config.model_copy(
                    update={"start_url": f"{fixture_url}delayed-refresh"}
                )
                # Keep the browser-session allowlist rooted to the same fixture origin.
                session.goto_start()
                assert session.page and session.page.url.endswith("/redirected")
        finally:
            browser.close()


def test_readiness_any_enabled_skips_hydration_wait_for_ready_out_of_main_page(
    fixture_url: str, tmp_path: Path
) -> None:
    """A page whose controls are already enabled but rendered outside <main> is READY; the default
    readiness still pays the full hydration wait (controls not in <main>), while readiness_any_enabled
    exits at the cheap stability wait. This is the fix for the breadth-heavy-SPA readiness tax."""
    from playwright.sync_api import sync_playwright

    common = dict(
        start_url=f"{fixture_url}out-of-main", output_dir=tmp_path / "ooml",
        robust_readiness=True, readiness_timeout_ms=2_500, readiness_poll_ms=50,
        idle_page_wait_ms=1_600, passive_page_wait_ms=100, readiness_strategy="fixed",
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            # Default: controls are outside <main> -> slow hydration path.
            with BrowserSession(browser, RunConfig(**common)) as s:
                s.goto_start()
                slow = s.observe(1)
            # Fix on: any enabled control counts -> cheap exit.
            with BrowserSession(browser, RunConfig(**{**common, "readiness_any_enabled": True})) as s:
                s.goto_start()
                fast = s.observe(1)
        finally:
            browser.close()

    # Both see the same ready controls...
    for obs in (slow, fast):
        assert any(c.label in {"Action A", "Action B"} for c in obs.controls)
        assert obs.readiness.status == "usable"
    # ...but the fix exits much sooner (no wasted hydration wait).
    assert fast.readiness.duration_ms < 900, fast.readiness.duration_ms
    assert slow.readiness.duration_ms >= 1_200, slow.readiness.duration_ms
    assert fast.readiness.duration_ms < slow.readiness.duration_ms


def test_canvas_probe_introspects_litegraph_model(fixture_url: str) -> None:
    """The canvas probe reads a node-graph app's JS model (operation catalog + placed nodes) that a
    DOM crawler cannot see. Read-only; no canvas interaction."""
    from agent1.canvas_probe import probe_url

    inv = probe_url(f"{fixture_url}litegraph-mock", wait_ms=800)
    assert inv is not None and inv.is_introspectable
    assert inv.framework == "litegraph"
    assert inv.node_type_count == 5
    assert "KSampler" in inv.registered_node_types and "CLIPTextEncode" in inv.registered_node_types
    assert len(inv.nodes) == 2
    assert inv.nodes[0]["type"] == "KSampler"
    assert {w["name"] for w in inv.nodes[0]["widgets"]} == {"seed", "steps"}


def test_canvas_probe_extends_beyond_litegraph(fixture_url: str) -> None:
    """Introspection generalizes beyond LiteGraph: React Flow (DOM nodes), a generic editor stored on a
    global (swept by shape), and Cytoscape (window.cy)."""
    from agent1.canvas_probe import probe_url

    rf = probe_url(f"{fixture_url}reactflow-mock", wait_ms=400)
    assert rf is not None and rf.framework == "reactflow"
    assert {n["id"] for n in rf.nodes} == {"n1", "n2"}
    assert any(e["from"] == "n1" and e["to"] == "n2" for e in rf.edges)

    gen = probe_url(f"{fixture_url}generic-graph-mock", wait_ms=400)
    assert gen is not None and gen.framework == "generic:myEditor"
    assert {n["label"] for n in gen.nodes} == {"Source", "Sink"}

    cy = probe_url(f"{fixture_url}cytoscape-mock", wait_ms=400)
    assert cy is not None and cy.framework == "cytoscape"
    assert {n["id"] for n in cy.nodes} == {"x", "y"}
    assert any(e["from"] == "x" and e["to"] == "y" for e in cy.edges)


def test_canvas_probe_drives_litegraph_schemas_and_add_remove(fixture_url: str) -> None:
    """Driving: instantiate node types to read their full I/O schemas, and prove the graph is drivable
    by adding then removing a node (client-side only; never executed; graph restored)."""
    from agent1.canvas_probe import on_page, drive_node_schemas, demonstrate_drive

    def act(page):
        schemas = drive_node_schemas(page, limit=10)
        demo = demonstrate_drive(page, "Note")
        return schemas, demo

    schemas, demo = on_page(f"{fixture_url}litegraph-mock", act, wait_ms=800)
    by_type = {s.type: s for s in schemas if s.created}
    assert "KSampler" in by_type
    ks = by_type["KSampler"]
    assert {i["name"] for i in ks.inputs} == {"model", "seed"}
    assert [o["type"] for o in ks.outputs] == ["LATENT"]
    assert any(w["name"] == "seed" for w in ks.widgets)
    # drive demo: node added then removed, graph restored
    assert demo is not None
    assert demo["added_ok"] and demo["removed_ok"]
    assert demo["after_remove"] == demo["before"]


def test_canvas_execution_red_roadblock_when_unauthorized(fixture_url: str) -> None:
    """Without authorization, canvas workflow execution is NOT fired — a RED roadblock marker is recorded
    (optionally injected as a visible red node), so the blocked capability is surfaced, not skipped."""
    from agent1.canvas_probe import on_page, execute_canvas_workflow
    from agent1.write_policy import WritePolicy

    def act(page):
        # read_only policy -> would_allow(POST) is False -> roadblock even with allow_execution=True
        return execute_canvas_workflow(
            page, allow_execution=True, write_policy=WritePolicy("read_only"), inject_roadblock_node=True)

    att = on_page(f"{fixture_url}comfy-exec-mock", act, wait_ms=500)
    assert att.roadblock and not att.executed
    assert att.color == "RED"
    assert att.framework == "litegraph" and att.endpoint == "/prompt"
    red = att.as_red_node()
    assert red["color"] == "RED" and red["kind"] == "roadblock"
    assert att.evidence.get("red_node", {}).get("injected") is True


def test_canvas_execution_fires_when_authorized(fixture_url: str) -> None:
    """With allow_execution AND a disposable write policy, execution fires (POST /prompt) and the server
    response is captured as evidence (GREEN)."""
    from agent1.canvas_probe import on_page, execute_canvas_workflow
    from agent1.write_policy import WritePolicy

    def act(page):
        return execute_canvas_workflow(
            page, allow_execution=True, write_policy=WritePolicy("disposable"))

    att = on_page(f"{fixture_url}comfy-exec-mock", act, wait_ms=500)
    assert att.executed and not att.roadblock
    assert att.color == "GREEN"
    assert att.evidence.get("status") == 200
    assert "pid-123" in (att.evidence.get("body") or "")


def test_canvas_probe_returns_none_without_graph_model(fixture_url: str) -> None:
    """A page with no canvas / no graph framework returns None (reported honestly)."""
    from agent1.canvas_probe import probe_url

    assert probe_url(f"{fixture_url}interactions", wait_ms=400) is None


def test_ui_login_helper_captures_cookie_and_localstorage(fixture_url: str, tmp_path: Path) -> None:
    """The UI-login helper drives a real login form and saves BOTH the cookie and the localStorage the
    app writes — the full client state a token/role-gated SPA needs (not just the cookie)."""
    from agent1.auth_capture import capture_login_session

    out = tmp_path / "session.json"
    result = capture_login_session(
        f"{fixture_url}login-form", "admin", "secret", out,
        success_url_contains="logged_in", wait_ms=2_000,
    )
    assert out.exists()
    assert result.verified is True
    assert result.cookies >= 1
    state = json.loads(out.read_text())
    cookie_names = {c["name"] for c in state.get("cookies", [])}
    assert "app_session" in cookie_names
    ls_keys = {k for keys in result.local_storage_keys.values() for k in keys}
    assert "app_user" in ls_keys, result.local_storage_keys


def test_neutralize_blocked_writes_lets_init_write_resolve(fixture_url: str, tmp_path: Path) -> None:
    """Under read_only, a page's init-time write is denied. Aborting it (default) makes fetch() reject
    and can halt an SPA's startup; neutralize fulfils it (without forwarding to the server) so the page
    continues. The server never receives the write either way. Regression guard for comfyui context-init."""
    from playwright.sync_api import sync_playwright
    from agent1.write_policy import WritePolicy

    def run(neutralize: bool):
        config = RunConfig(
            start_url=f"{fixture_url}writes-on-load", output_dir=tmp_path / f"w{int(neutralize)}",
            neutralize_blocked_writes=neutralize, robust_readiness=True, readiness_timeout_ms=2_000,
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                session = BrowserSession(browser, config)
                session.write_policy = WritePolicy("read_only")  # what Explorer wires by default
                session.__enter__()
                try:
                    session.goto_start()
                    assert session.page is not None
                    session.page.wait_for_timeout(600)
                    return session.page.evaluate(
                        "() => ({after: !!document.querySelector('#after-write'),"
                        " failed: !!document.querySelector('#write-failed')})")
                finally:
                    session.__exit__()
            finally:
                browser.close()

    abort = run(False)
    neutral = run(True)
    assert abort["failed"] and not abort["after"], abort      # default: write rejected
    assert neutral["after"] and not neutral["failed"], neutral  # neutralized: write resolved


def test_scope_router_allows_blob_url_scripts(fixture_url: str, tmp_path: Path) -> None:
    """The scope router (active when an HTTP budget is configured) must pass browser-internal pseudo-URLs
    (blob:/data:) rather than aborting them — otherwise apps that load modules/workers from blob: URLs
    (e.g. comfyui) never build their DOM. Regression guard for the comfyui context-init fix."""
    from playwright.sync_api import sync_playwright

    config = RunConfig(
        start_url=f"{fixture_url}blob-script", output_dir=tmp_path / "blob",
        max_total_http_requests=200,  # enables the bounded scope router
        robust_readiness=True, readiness_any_enabled=True, readiness_timeout_ms=3_000,
        readiness_poll_ms=50,
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            with BrowserSession(browser, config) as session:
                session.goto_start()
                assert session.page is not None
                session.page.wait_for_selector("#from-blob", timeout=3_000)
                obs = session.observe(1)
            assert any(c.label == "Blob control" for c in obs.controls), \
                "blob: script was blocked by the scope router"
        finally:
            browser.close()


def test_readiness_await_content_waits_for_scripted_shell_to_build(
    fixture_url: str, tmp_path: Path
) -> None:
    """A scripted shell with no actionable controls: default readiness declares it usable quickly,
    but readiness_await_content keeps waiting (bounded by readiness_timeout_ms) for content to appear.
    This is the lever for heavy SPAs (e.g. comfyui) that build their DOM toolbar over many seconds."""
    from playwright.sync_api import sync_playwright

    common = dict(
        start_url=f"{fixture_url}scripted-shell", output_dir=tmp_path / "shell",
        robust_readiness=True, readiness_timeout_ms=800, readiness_poll_ms=50,
        idle_page_wait_ms=300, passive_page_wait_ms=100, readiness_strategy="fixed",
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            with BrowserSession(browser, RunConfig(**common)) as s:
                s.goto_start()
                default = s.last_readiness
            with BrowserSession(browser, RunConfig(**{**common, "readiness_await_content": True})) as s:
                s.goto_start()
                awaited = s.last_readiness
        finally:
            browser.close()

    # Default gives up quickly on the empty-but-stable shell; await_content waits out the timeout.
    assert default.status == "usable" and default.duration_ms < 500, default
    assert awaited.status == "timeout" and awaited.duration_ms >= 700, awaited


def test_history_return_is_verified_and_keeps_graph_evidence_complete(
    fixture_url: str, tmp_path: Path
) -> None:
    config = RunConfig(
        start_url=fixture_url, output_dir=tmp_path / "history", policy="hierarchical",
        exploration_mode="persistent", state_reuse="prefix", max_seconds=25,
        max_transitions=12, max_browser_actions=60, settle_ms=0,
    )
    artifact = Explorer(config, Path(__file__).resolve().parents[1]).run()
    metrics = artifact.metrics
    assert metrics.history_returns == metrics.history_return_attempts
    assert metrics.root_reloads_avoided <= metrics.history_returns + metrics.prefix_state_reuses
    assert metrics.graph_connections_missing_evidence == 0
    assert all(
        [step.step_index for step in t.prerequisite_network]
        == list(range(t.reused_prefix_steps, len(t.workflow_path) - 1))
        for t in artifact.transitions if t.restoration_attempted and t.status != EvidenceStatus.FAILED
    )
