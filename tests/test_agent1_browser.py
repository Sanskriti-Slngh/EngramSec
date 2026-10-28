from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from agent1.explorer import Explorer
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
                <button id="reveal" onclick="document.querySelector('#panel').hidden=false; this.remove()">Reveal details</button>
                <section id="panel" hidden><h2>Revealed details</h2></section>
                </body></html>"""
            )
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
