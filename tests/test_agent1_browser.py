from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from agent1.explorer import BrowserSession, Explorer
from agent1.exporter import build_graph_a, write_outputs
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
