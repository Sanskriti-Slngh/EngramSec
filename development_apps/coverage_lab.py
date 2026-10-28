from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


SHELL = """<!doctype html><html><head><title>{title}</title></head><body>
<nav><a href="/">Coverage Lab</a><a href="https://example.test/outside">External docs</a></nav>
<main>{body}</main><time data-volatile>12:34:56</time>{script}</body></html>"""


class CoverageLabHandler(BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        return

    def _send(self, body: str, *, content_type: str = "text/html", cookie: str | None = None) -> None:
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(encoded)

    def _page(self, title: str, body: str, script: str = "") -> None:
        self._send(SHELL.format(title=title, body=body, script=script))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path == "/":
            self._page(
                "Coverage Lab",
                """
<h1>Coverage Lab</h1>
<a href="/records/1">Alpha customer</a><a href="/records/2">Beta customer</a>
<button id="load-summary">Load summary</button>
<button id="toggle-tools" aria-controls="tools">Show tools</button>
<section id="tools" hidden><a href="/workspace">Workspace</a><button id="audit">Audit record</button></section>
<div role="tab" tabindex="0" id="analytics-tab">Analytics</div>
<section id="analytics" hidden><h2>Analytics dashboard</h2><button id="export">Export analytics</button></section>
<details><summary>Advanced settings</summary><a href="/settings">Open settings</a></details>
<span tabindex="0" data-action="navigate" id="help-launcher">Help center</span>
<button id="ineffective">Refresh status</button>
<form method="post" action="/session"><label>Member code <input name="member_code" placeholder="DEMO"></label><button>Enter member area</button></form>
<form method="post" action="/admin"><label>Admin password <input type="password" name="password"></label><button>Admin login</button></form>
<section id="feedback" aria-live="polite"></section>
""",
                """<script>
const feedback = document.querySelector('#feedback');
document.querySelector('#load-summary').onclick = async () => {
  const response = await fetch('/api/summary?scope=home&format=json');
  feedback.textContent = (await response.json()).message;
};
document.querySelector('#toggle-tools').onclick = () => document.querySelector('#tools').hidden = false;
document.querySelector('#audit').onclick = () => fetch('/api/audit?record=1');
document.querySelector('#analytics-tab').onclick = () => document.querySelector('#analytics').hidden = false;
document.querySelector('#export').onclick = () => fetch('/api/analytics?range=30d');
document.querySelector('#help-launcher').onclick = () => location.href = '/help';
document.querySelector('#ineffective').onclick = () => {};
</script>""",
            )
            return
        if parsed.path in {"/records/1", "/records/2"}:
            record = parsed.path.rsplit("/", 1)[-1]
            other = "2" if record == "1" else "1"
            name = "Alpha" if record == "1" else "Beta"
            self._page(
                "Customer record",
                f'<h1>{name} customer</h1><p data-record="{record}">Account {record}</p>'
                f'<button id="history">Load history</button><a href="/records/{other}">Related customer</a>',
                f"""<script>document.querySelector('#history').onclick = () =>
fetch('/api/history?record={record}&limit=10');</script>""",
            )
            return
        if parsed.path == "/workspace":
            self._page(
                "Workspace",
                '<h1>Workspace</h1><button id="prepare">Prepare workspace</button><section id="ready"></section>',
                """<script>document.querySelector('#prepare').onclick = async () => {
await fetch('/api/workspace/bootstrap?mode=demo');
document.querySelector('#ready').innerHTML = '<p>Workspace ready</p><a href="/workspace/reports">Open reports</a>';
};</script>""",
            )
            return
        if parsed.path == "/workspace/reports":
            self._page("Reports", "<h1>Workspace reports</h1><p>Quarterly report queue</p>")
            return
        if parsed.path == "/settings":
            self._page("Settings", "<h1>Advanced settings</h1><p>Read-only test settings</p>")
            return
        if parsed.path == "/help":
            self._page("Help", "<h1>Help center</h1><p>Local documentation</p>")
            return
        if parsed.path == "/member":
            member = "member=ready" in (self.headers.get("Cookie") or "")
            body = (
                '<h1>Member dashboard</h1><a href="/member/preferences">Member preferences</a>'
                if member
                else "<h1>Member access required</h1>"
            )
            self._page("Member", body)
            return
        if parsed.path == "/member/preferences":
            self._page("Preferences", "<h1>Member preferences</h1>")
            return
        if parsed.path.startswith("/api/"):
            payload = {"ok": True, "message": parsed.path.rsplit("/", 1)[-1] + " loaded"}
            self._send(json.dumps(payload), content_type="application/json")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        if self.path == "/session" and parse_qs(body).get("member_code"):
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/member")
            self.send_header("Set-Cookie", "member=ready; Path=/; HttpOnly; SameSite=Lax")
            self.end_headers()
            return
        self.send_error(HTTPStatus.FORBIDDEN)


def start_coverage_lab() -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), CoverageLabHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}/"
