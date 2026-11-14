"""Operator-approved canonical-host aliases (an app that links to its own internal service name)."""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from pydantic import ValidationError

from agent1.explorer import Explorer
from agent1.schema import RunConfig


@pytest.fixture()
def app():
    seen: list[tuple[str, str]] = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            seen.append((self.headers.get("Host"), self.path))
            body = (b"<title>Shop</title><main><h1>Shop</h1><a href='http://appsvc/catalog'>Catalog</a></main>"
                    if self.path == "/" else b"<title>Catalog</title><main><h1>Catalog</h1><p>items</p></main>")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", seen
    server.shutdown()


@pytest.mark.parametrize("listener", ["off", "revisit"])          # without and with the scope router
def test_aliased_canonical_host_is_reached_through_loopback_with_its_host_header(app, tmp_path, listener):
    origin, seen = app
    config = RunConfig(start_url=origin + "/", output_dir=tmp_path, max_seconds=20, max_browser_actions=8,
                       max_transitions=4, settle_ms=50, runtime_listener_observation=listener,
                       origin_aliases=["http://appsvc"], host_map={"http://appsvc": origin})
    artifact = Explorer(config, tmp_path).run()
    assert any(o.url.startswith("http://appsvc/catalog") for o in artifact.observations)
    assert ("appsvc", "/catalog") in seen


def test_without_the_alias_the_canonical_host_stays_out_of_scope(app, tmp_path):
    origin, seen = app
    config = RunConfig(start_url=origin + "/", output_dir=tmp_path, max_seconds=15, max_browser_actions=6,
                       max_transitions=3, settle_ms=50)
    artifact = Explorer(config, tmp_path).run()
    assert not any("/catalog" in path for _, path in seen)
    assert any(c.skip_reason == "cross_origin" for o in artifact.observations for c in o.controls)


def test_host_map_requires_loopback_targets_and_an_approved_alias(tmp_path):
    base = dict(start_url="http://127.0.0.1:1/", output_dir=tmp_path)
    with pytest.raises(ValidationError):
        RunConfig(**base, origin_aliases=["http://appsvc"], host_map={"http://appsvc": "http://10.0.0.5:80"})
    with pytest.raises(ValidationError):
        RunConfig(**base, host_map={"http://appsvc": "http://127.0.0.1:1"})        # alias not approved
