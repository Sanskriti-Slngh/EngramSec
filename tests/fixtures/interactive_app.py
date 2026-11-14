from __future__ import annotations

import json
import threading
from collections import defaultdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


SHELL = """<!doctype html><html><head><title>{title}</title></head>
<body><main>{body}</main>{script}</body></html>"""


class FixtureState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.counters: dict[str, int] = defaultdict(int)
        self.events: list[dict[str, Any]] = []

    def reset(self) -> None:
        with self.lock:
            self.counters.clear()
            self.events.clear()

    def next(self, key: str) -> int:
        with self.lock:
            value = self.counters[key]
            self.counters[key] += 1
            return value

    def record(self, **event: Any) -> None:
        with self.lock:
            self.events.append(event)

    def snapshot(self) -> list[dict[str, Any]]:
        with self.lock:
            return list(self.events)


class InteractiveHandler(BaseHTTPRequestHandler):
    server: "InteractiveServer"

    def log_message(self, *_: Any) -> None:
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

    def _json(self, payload: dict[str, Any], *, cookie: str | None = None) -> None:
        self._send(json.dumps(payload), content_type="application/json", cookie=cookie)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/search":
            self._send(
                SHELL.format(
                    title="Search",
                    body=(
                        '<h1>Search records</h1><form id="search" method="post" action="/search">'
                        '<label>Query <input name="query" type="search" required></label>'
                        '<button type="submit">Search</button></form>'
                        '<section id="result" role="status" aria-live="polite"></section>'
                    ),
                    script="""<script>
document.querySelector('#search').addEventListener('submit', async (event) => {
  event.preventDefault();
  const response = await fetch('/search', {method:'POST', body:new FormData(event.target)});
  const data = await response.json();
  document.querySelector('#result').innerHTML = `<p data-outcome="result">${data.result}</p>`;
});</script>""",
                )
            )
            return
        if path == "/form":
            self._send(
                SHELL.format(
                    title="Registration",
                    body=(
                        '<h1>Registration</h1><form id="registration" novalidate method="post" action="/form">'
                        '<label>Invite code <input name="invite_code" required pattern="[A-Z]{5}-[0-9]{2}" '
                        'placeholder="VALID-42" aria-describedby="code-help"></label>'
                        '<small id="code-help">Five capital letters, a dash, and two digits.</small>'
                        '<button type="submit">Create registration</button></form>'
                        '<section id="feedback" aria-live="assertive"></section>'
                    ),
                    script="""<script>
document.querySelector('#registration').addEventListener('submit', async (event) => {
  event.preventDefault();
  const response = await fetch('/form', {method:'POST', body:new FormData(event.target)});
  const data = await response.json();
  const feedback = document.querySelector('#feedback');
  feedback.setAttribute('role', data.ok ? 'status' : 'alert');
  feedback.innerHTML = `<p data-outcome="${data.ok ? 'success' : 'validation_error'}">${data.message}</p>`;
});</script>""",
                )
            )
            return
        if path == "/model-form":
            self._send(
                SHELL.format(
                    title="Demo access",
                    body=(
                        '<h1>Demo access</h1><form id="model-form" novalidate method="post" action="/model-form">'
                        '<label>Demo access code <input name="demo_code" required pattern="[A-Z]{5}-[0-9]{2}" '
                        'aria-describedby="model-help"></label>'
                        '<small id="model-help">Use a five-letter demo code, a dash, and two digits.</small>'
                        '<button type="submit">Activate demo</button></form>'
                        '<section id="model-feedback" aria-live="assertive"></section>'
                    ),
                    script="""<script>
document.querySelector('#model-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const response = await fetch('/model-form', {method:'POST', body:new FormData(event.target)});
  const data = await response.json();
  const feedback = document.querySelector('#model-feedback');
  feedback.innerHTML = `<p role="${data.ok ? 'status' : 'alert'}" data-outcome="${data.ok ? 'success' : 'validation_error'}">${data.message}</p>`;
});</script>""",
                )
            )
            return
        if path == "/multi":
            self._send(
                SHELL.format(
                    title="Workspace setup",
                    body=(
                        '<h1>Workspace setup</h1><button id="prepare" type="button">Prepare workspace</button>'
                        '<section id="step" aria-live="polite"></section>'
                    ),
                    script="""<script>
document.querySelector('#prepare').addEventListener('click', async () => {
  const response = await fetch('/multi/setup', {method:'POST'});
  const data = await response.json();
  document.querySelector('#step').innerHTML = `<p role="status" data-outcome="setup">${data.message}</p>
    <form id="complete" method="post" action="/multi/complete">
      <label>Workspace name <input name="workspace" required placeholder="Demo workspace"></label>
      <button type="submit">Complete setup</button></form>`;
  document.querySelector('#complete').addEventListener('submit', async (event) => {
    event.preventDefault();
    const result = await fetch('/multi/complete', {method:'POST', body:new FormData(event.target)});
    const completed = await result.json();
    const role = completed.ok ? 'status' : 'alert';
    const outcome = completed.ok ? 'success' : 'validation_error';
    document.querySelector('#step').innerHTML = `<p role="${role}" data-outcome="${outcome}">${completed.message}</p>`;
  });
});</script>""",
                )
            )
            return
        if path == "/records":
            choice = "1" if self.server.state.next("record_index") % 2 == 0 else "2"
            self.server.state.record(kind="record_index", choice=choice)
            self._send(
                SHELL.format(
                    title="Records",
                    body=f'<h1>Records</h1><a href="/record/{choice}">Open record</a>',
                    script="",
                )
            )
            return
        if path in {"/record/1", "/record/2"}:
            record = path.rsplit("/", 1)[-1]
            self.server.state.record(kind="record_visit", record=record)
            display = "Alpha" if record == "1" else "Beta"
            self._send(
                SHELL.format(
                    title="Customer record",
                    body=f'<h1>Customer record</h1><p data-record-id="{record}">Record {display}</p>',
                    script="",
                )
            )
            return
        if path == "/cosmetic":
            tick = self.server.state.next("timestamp")
            self._send(
                SHELL.format(
                    title="Dashboard",
                    body=(
                        '<h1>System dashboard</h1><p>All systems operational</p>'
                        f'<time data-volatile datetime="2026-10-28T13:{tick:02d}:00Z">Updated at 13:{tick:02d}</time>'
                        f'<span><i class="icon-eye"></i>{tick + 10}</span>'
                        '<a href="/cosmetic">Refresh dashboard</a>'
                    ),
                    script="",
                )
            )
            return
        if path == "/outcomes":
            self._send(
                SHELL.format(
                    title="Outcome examples",
                    body=(
                        '<h1>Outcome examples</h1>'
                        '<button id="success" type="button">C verify success</button>'
                        '<button id="failure" type="button">B show validation failure</button>'
                        '<button id="untested" type="button">A leave untested</button>'
                        '<section id="outcome" aria-live="polite"></section>'
                    ),
                    script="""<script>
document.querySelector('#success').addEventListener('click', () => {
  document.querySelector('#outcome').innerHTML = '<p role="status" data-outcome="success">Profile saved successfully</p>';
});
document.querySelector('#failure').addEventListener('click', () => {
  document.querySelector('#outcome').innerHTML = '<p role="alert" data-outcome="validation_error">Required field is missing</p>';
});
document.querySelector('#untested').addEventListener('click', () => {
  document.querySelector('#outcome').innerHTML = '<p role="status" data-outcome="result">This action should remain untested</p>';
});
</script>""",
                )
            )
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length).decode("utf-8", errors="replace")
        if self.path == "/search":
            sequence = self.server.state.next("search_result")
            result = "Result Alpha" if sequence % 2 == 0 else "Result Beta"
            self.server.state.record(kind="search_result", result=result)
            self._json({"result": result})
            return
        if self.path == "/form":
            valid = "VALID-42" in payload and (
                "invite_code=VALID-42" in payload or 'name="invite_code"' in payload
            )
            self.server.state.record(kind="form_submission", success=valid)
            self._json(
                {
                    "ok": valid,
                    "message": "Registration created" if valid else "Invite code is invalid",
                }
            )
            return
        if self.path == "/model-form":
            valid = "ORBIT-73" in payload
            self.server.state.record(kind="model_form_submission", success=valid)
            self._json(
                {
                    "ok": valid,
                    "message": (
                        "Demo access activated"
                        if valid
                        else "Code rejected. For this demo, use ORBIT-73."
                    ),
                }
            )
            return
        if self.path == "/multi/setup":
            self.server.state.record(kind="setup", success=True)
            self._json({"ok": True, "message": "Workspace is ready"}, cookie="setup=ready; Path=/")
            return
        if self.path == "/multi/complete":
            ready = "setup=ready" in self.headers.get("Cookie", "")
            has_name = 'name="workspace"' in payload and (
                "EngramSec test" in payload or "Demo workspace" in payload
            )
            success = ready and has_name
            self.server.state.record(kind="completion", success=success, prerequisite=ready)
            self._json(
                {
                    "ok": success,
                    "message": "Workspace setup complete" if success else "Workspace setup is incomplete",
                }
            )
            return
        self.send_error(HTTPStatus.NOT_FOUND)


class InteractiveServer(ThreadingHTTPServer):
    def __init__(self) -> None:
        self.state = FixtureState()
        super().__init__(("127.0.0.1", 0), InteractiveHandler)

    @property
    def base_url(self) -> str:
        host, port = self.server_address
        return f"http://{host}:{port}"


def start_server() -> tuple[InteractiveServer, threading.Thread]:
    server = InteractiveServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
