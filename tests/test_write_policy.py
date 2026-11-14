"""Write policy: read-only is enforced at the request level; disposable mode allows bounded,
logged, non-destructive writes only on an attested disposable environment."""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from playwright.sync_api import sync_playwright
from pydantic import ValidationError

from agent1.explorer import Explorer
from agent1.schema import RunConfig

PAGE = """<!doctype html><title>Lab</title><main><h1>Lab</h1>
<button id="join">Join</button> <button id="tidy">Tidy</button> <button id="remove">Remove</button>
<a href="/about">About</a><div id="out"></div></main><script>
const send = (url, method) => fetch(url, {method, headers: {'Content-Type': 'application/json'},
  body: method === 'DELETE' ? undefined : JSON.stringify({username: 'u', password: 'p'})})
  .then(r => document.getElementById('out').textContent = r.status).catch(() => {});
document.getElementById('join').onclick = () => send('/api/register', 'POST');
document.getElementById('tidy').onclick = () => send('/api/purge', 'POST');
document.getElementById('remove').onclick = () => send('/api/items/1', 'DELETE');
</script>"""


@pytest.fixture()
def lab():
    log: list[tuple[str, str]] = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def _send(self, body=b"ok", ctype="text/plain"):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            log.append(("GET", self.path))
            self._send(PAGE.encode(), "text/html") if self.path == "/" else self._send()

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            log.append(("POST", self.path))
            self._send()

        def do_DELETE(self):
            log.append(("DELETE", self.path))
            self._send()

    server = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/", log
    server.shutdown()


def _click_all(tmp_path, url, labels, **cfg):
    explorer = Explorer(RunConfig(start_url=url, output_dir=tmp_path, **cfg), tmp_path)
    events = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        with explorer._browser_session(browser) as session:
            session.goto_start()
            for label in labels:
                obs = session.observe(explorer._next_sequence())
                control = next(c for c in obs.controls if c.label == label)
                _, network, _, _ = session.execute(control, {}, None)
                session.page.wait_for_timeout(300)
                network += session.network.drain() if session.network else []
                events[label] = [(e.method, e.url.rsplit("/", 2)[-2:], e.failure, e.status) for e in network
                                 if "/api/" in e.url]
        browser.close()
    return explorer, events


def test_read_only_blocks_script_issued_writes_before_they_reach_the_server(lab, tmp_path):
    url, log = lab
    explorer, events = _click_all(tmp_path, url, ["Join", "Remove"])          # allow_post_forms=False (default)
    assert not [m for m, _ in log if m != "GET"]                               # nothing state-changing arrived
    assert all(f == "net::ERR_ACCESS_DENIED" for e in events.values() for _, _, f, _ in e)
    stats = explorer.artifact.metrics.write_policy
    assert stats["mode"] == "read_only" and stats["blocked_read_only"] == 2 and stats["allowed"] == 0
    assert {(x["method"], x["route"], x["decision"]) for x in stats["log"]} == {
        ("POST", "/api/register", "blocked_read_only"), ("DELETE", "/api/items/{instance}", "blocked_read_only")}


def test_disposable_allows_bounded_writes_but_never_destructive_ones(lab, tmp_path):
    url, log = lab
    explorer, _ = _click_all(tmp_path, url, ["Join", "Tidy", "Remove"], allow_post_forms=True,
                             write_policy="disposable", environment_attestation="disposable:test-fixture")
    assert ("POST", "/api/register") in log
    assert ("POST", "/api/purge") not in log and not [p for m, p in log if m == "DELETE"]
    stats = explorer.artifact.metrics.write_policy
    assert stats["allowed"] == 1 and stats["blocked_destructive"] == 2


def test_disposable_write_cap_blocks_writes_beyond_the_limit(lab, tmp_path):
    url, log = lab
    explorer, _ = _click_all(tmp_path, url, ["Join", "Join"], allow_post_forms=True, write_policy="disposable",
                             environment_attestation="disposable:test-fixture", max_write_requests=1)
    assert log.count(("POST", "/api/register")) == 1
    assert explorer.artifact.metrics.write_policy["blocked_write_cap"] == 1


def test_write_policy_configuration_is_validated(tmp_path):
    base = dict(start_url="http://127.0.0.1:1/", output_dir=tmp_path)
    with pytest.raises(ValidationError):
        RunConfig(**base, allow_post_forms=True, write_policy="disposable")          # no attestation
    with pytest.raises(ValidationError):
        RunConfig(**base, write_policy="disposable", environment_attestation="disposable:x")   # POST still off
    with pytest.raises(ValidationError):
        RunConfig(**base, allow_post_forms=True, write_policy="read_only")           # contradiction
    assert RunConfig(**base).effective_write_policy == "read_only"
    assert RunConfig(**base, allow_post_forms=True).effective_write_policy == "legacy_post_forms"
