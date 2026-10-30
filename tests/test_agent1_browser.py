from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from agent1.explorer import BrowserSession, Explorer
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
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            with BrowserSession(browser, config) as session:
                session.goto_start()
                late = session.observe(1)
                assert any(item.label == "Hydrated control" for item in late.controls)
                assert late.readiness.status == "usable"
                assert late.readiness.duration_ms >= 300

                session.config = config.model_copy(
                    update={"start_url": f"{fixture_url}delayed-refresh"}
                )
                # Keep the browser-session allowlist rooted to the same fixture origin.
                session.goto_start()
                assert session.page and session.page.url.endswith("/redirected")
        finally:
            browser.close()
