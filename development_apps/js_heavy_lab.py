from __future__ import annotations

import json
import threading
from collections import Counter
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


class LabState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.requests: Counter[str] = Counter()

    def record(self, method: str, path: str) -> None:
        with self.lock:
            self.requests[f"{method} {path}"] += 1

    def reset(self) -> None:
        with self.lock:
            self.requests.clear()

    def snapshot(self) -> dict[str, int]:
        with self.lock:
            return dict(sorted(self.requests.items()))


STATE = LabState()


def _shell(title: str, body: str, script: str = "") -> str:
    return f"""<!doctype html><html><head><title>{title}</title></head><body>
<nav aria-label="Repeated main menu">
  <a href="/">JS Lab</a><a href="/shallow/a">Overview</a><a href="/shallow/b">News</a>
</nav>
<main>{body}</main>{script}</body></html>"""


class JSHeavyLabHandler(BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        return

    def _record(self) -> None:
        STATE.record(self.command, urlsplit(self.path).path)

    def _send(
        self,
        body: str,
        *,
        status: int = HTTPStatus.OK,
        content_type: str = "text/html",
        cookie: str | None = None,
    ) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(encoded)

    def _page(self, title: str, body: str, script: str = "") -> None:
        self._send(_shell(title, body, script))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path == "/__eval__/stats":
            self._send(json.dumps(STATE.snapshot()), content_type="application/json")
            return
        self._record()
        if parsed.path == "/":
            alias = f"http://localhost:{self.server.server_port}/alias-area"
            self._page(
                "JavaScript Readiness Lab",
                f"""
<section id="application" aria-busy="true">
  <h1>JavaScript Readiness Lab</h1>
  <p id="boot-state" role="status">Initialising application</p>
  <button id="open-lab" disabled>Open workflow</button>
  <div id="late-controls"></div>
  <form method="post" action="/session">
    <label>Member code <input name="member_code" placeholder="DEMO"></label>
    <button disabled id="member-submit">Enter member mode</button>
  </form>
  <a href="{alias}">Public alias area</a>
  <a href="https://example.test/outside">External documentation</a>
  <button id="ineffective" disabled>Refresh status</button>
  <time data-volatile id="clock">00:00:00</time>
  <section id="workflow"></section>
</section>
""",
                """<script>
const app = document.querySelector('#application');
const clock = document.querySelector('#clock');
setInterval(() => { clock.textContent = new Date().toISOString(); }, 40);
setTimeout(async () => {
  await fetch('/api/bootstrap?mode=anonymous&format=json');
  const open = document.querySelector('#open-lab');
  const member = document.querySelector('#member-submit');
  const ineffective = document.querySelector('#ineffective');
  open.disabled = false; member.disabled = false; ineffective.disabled = false;
  open.onclick = () => {
    document.querySelector('#workflow').innerHTML =
      '<h2>Workflow stage one</h2><button id="continue-setup">Continue setup</button>';
    document.querySelector('#continue-setup').onclick = async () => {
      await fetch('/api/workflow/prepare?mode=safe');
      document.querySelector('#workflow').innerHTML =
        '<h2>Workflow ready</h2><a href="/workspace">Open workspace</a>';
    };
  };
  ineffective.onclick = () => {};
  document.querySelector('#boot-state').textContent = 'Application ready';
  app.setAttribute('aria-busy', 'false');
}, 650);
setTimeout(() => {
  const late = document.createElement('button');
  late.id = 'late-reports'; late.textContent = 'Load late reports';
  late.onclick = async () => {
    await fetch('/api/late?view=reports');
    document.querySelector('#late-controls').innerHTML = '<a href="/reports">Open reports</a>';
  };
  document.querySelector('#late-controls').appendChild(late);
}, 800);
</script>""",
            )
            return
        if parsed.path == "/shallow/a":
            self._page("Overview", "<h1>Overview</h1><p>Repeated shallow destination.</p>")
            return
        if parsed.path == "/shallow/b":
            self._page("News", "<h1>News</h1><p>Another shallow destination.</p>")
            return
        if parsed.path == "/alias-area":
            self._page("Alias Area", "<h1>Verified alias area</h1><button id='alias-data'>Load alias data</button>",
                       "<script>document.querySelector('#alias-data').onclick=()=>fetch('/api/alias?source=public');</script>")
            return
        if parsed.path == "/workspace":
            self._page("Workspace", "<h1>Deep workspace</h1><a href='/workspace/detail'>Workspace detail</a>")
            return
        if parsed.path == "/workspace/detail":
            self._page("Workspace Detail", "<h1>Workspace detail</h1><p>Deep workflow result.</p>")
            return
        if parsed.path == "/reports":
            self._page("Reports", "<h1>Late reports</h1><p>Hydrated report index.</p>")
            return
        if parsed.path == "/member":
            member = "member_session=member-secret-9f31" in (self.headers.get("Cookie") or "")
            body = (
                "<h1>Member dashboard</h1><a href='/member/preferences'>Member preferences</a>"
                if member
                else "<h1>Member access blocked</h1>"
            )
            self._page("Member", body)
            return
        if parsed.path == "/member/preferences":
            self._page("Member Preferences", "<h1>Member preferences</h1><button id='member-data'>Load preferences</button>",
                       "<script>document.querySelector('#member-data').onclick=()=>fetch('/api/member/preferences?view=compact');</script>")
            return
        if parsed.path.startswith("/api/"):
            self._send(json.dumps({"ok": True, "path": parsed.path}), content_type="application/json")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path == "/__eval__/reset":
            STATE.reset()
            self._send(json.dumps({"ok": True}), content_type="application/json")
            return
        self._record()
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        if parsed.path == "/session" and parse_qs(body).get("member_code"):
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/member")
            self.send_header(
                "Set-Cookie",
                "member_session=member-secret-9f31; Path=/; HttpOnly; SameSite=Lax",
            )
            self.end_headers()
            return
        self.send_error(HTTPStatus.FORBIDDEN)


def start_js_heavy_lab() -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    STATE.reset()
    server = ThreadingHTTPServer(("127.0.0.1", 0), JSHeavyLabHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}/"
