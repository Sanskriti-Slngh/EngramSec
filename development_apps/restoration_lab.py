"""Restoration contract fixture (Phase 3b): states that are hard to restore truthfully.

Local, deterministic, stdlib only; the server log and state are operator-side.
- two records sharing one template, a handler that changes (Edit mode), a control
  created by that change, and a write button (Archive);
- a JavaScript-only state (tabs without URL change);
- a session-gated control that starts disabled, and a page that redirects back
  when the session lacks the prerequisite;
- a state-changing GET (a link that leaves and returns to the same URL with
  different content);
- a page whose structure changes after its first visit (deterministic replay
  mismatch);
- a session cookie (`sid`).
"""
from __future__ import annotations

import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

RECORDS = {"7301": "Harbor survey", "7302": "Quarry ledger"}


def _page(title: str, body: str, script: str = "") -> str:
    nav = ('<nav><a href="/records">Records</a> <a href="/tabs">Tabs</a> <a href="/gate">Gate</a> '
           '<a href="/counter">Counter</a> <a href="/status">Status</a></nav>')
    return f"<!doctype html><html><head><title>{title}</title></head><body>{nav}<main>{body}</main><script>{script}</script></body></html>"


def start_restoration_lab():
    log: list[tuple[str, str]] = []
    sessions: dict[str, set[str]] = {}
    state = {"bumps": 0, "status_visits": 0, "archived": 0, "proceeded": 0}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_):
            pass

        def _sid(self):
            for part in self.headers.get("Cookie", "").split(";"):
                if part.strip().startswith("sid="):
                    sid = part.strip()[4:]
                    sessions.setdefault(sid, set())
                    return sid, False
            sid = uuid.uuid4().hex
            sessions[sid] = set()
            return sid, True

        def _send(self, body: str, ctype: str = "text/html", status: int = 200, location: str | None = None):
            sid, new = self._sid()
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            if location:
                self.send_header("Location", location)
            if new:
                self.send_header("Set-Cookie", f"sid={sid}; Path=/")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802
            parts = urlsplit(self.path)
            path, query = parts.path, parse_qs(parts.query)
            log.append(("GET", path))
            sid, _ = self._sid()
            flags = sessions[sid]
            if path == "/":
                return self._send(_page("Home", "<p>Restoration lab</p>"))
            if path == "/records":
                rows = "".join(f'<li><a href="/records/{i}">{n}</a></li>' for i, n in RECORDS.items())
                return self._send(_page("Records", f"<ul>{rows}</ul>"))
            if path.startswith("/records/") and path.count("/") == 2 and path.split("/")[2] in RECORDS:
                rid = path.split("/")[2]
                return self._send(_page(RECORDS[rid], '<button id="notes">Notes</button><button id="edit">Edit mode</button>'
                                        '<button id="archive">Archive</button><div id="extra"></div>',
                                        f"let mode='view';document.getElementById('notes').onclick=()=>fetch('/api/records/{rid}/notes?mode='+mode);"
                                        "document.getElementById('edit').onclick=()=>{if(mode==='edit')return;mode='edit';"
                                        f"const b=document.createElement('button');b.textContent='Save draft';b.onclick=()=>fetch('/api/records/{rid}/draft');"
                                        "document.getElementById('extra').appendChild(b);};"
                                        f"document.getElementById('archive').onclick=()=>fetch('/api/records/{rid}/archive',{{method:'POST'}});"))
            if path.startswith("/api/records/"):
                return self._send('{"ok": true}', "application/json")
            if path == "/tabs":
                return self._send(_page("Tabs", '<button id="tab-a">Tab A</button><button id="tab-b">Tab B</button>'
                                        '<section id="panel-b" hidden><button id="load-b">Load B data</button></section>',
                                        "document.getElementById('tab-b').onclick=()=>{document.getElementById('panel-b').hidden=false};"
                                        "document.getElementById('tab-a').onclick=()=>{document.getElementById('panel-b').hidden=true};"
                                        "document.getElementById('load-b').onclick=()=>fetch('/api/tabs/b');"))
            if path == "/api/tabs/b":
                return self._send('{"rows": 3}', "application/json")
            if path == "/gate":
                ready = "unlocked" in flags
                return self._send(_page("Gate", '<button id="unlock">Unlock</button>'
                                        f'<button id="proceed" {"" if ready else "disabled"}>Proceed</button>'
                                        '<p><a href="/gate/draft">Draft</a></p>',
                                        "document.getElementById('unlock').onclick=()=>fetch('/api/gate/unlock').then(()=>"
                                        "{document.getElementById('proceed').disabled=false});"
                                        "document.getElementById('proceed').onclick=()=>fetch('/api/gate/proceed');"))
            if path == "/api/gate/unlock":
                flags.add("unlocked")
                return self._send('{"ok": true}', "application/json")
            if path == "/api/gate/proceed":
                state["proceeded"] += int("unlocked" in flags)
                return self._send('{"ok": true}', "application/json")
            if path == "/gate/draft":
                if "unlocked" not in flags:
                    return self._send("", status=302, location="/gate")          # redirect to a different state
                return self._send(_page("Draft", '<button id="preview">Preview</button>',
                                        "document.getElementById('preview').onclick=()=>fetch('/api/gate/preview');"))
            if path == "/api/gate/preview":
                return self._send('{"ok": true}', "application/json")
            if path == "/counter":
                return self._send(_page("Counter", f'<p>Count {state["bumps"]}</p><a href="/counter/bump">Bump</a>'))
            if path == "/counter/bump":
                state["bumps"] += 1                                             # a state-changing GET
                return self._send("", status=302, location="/counter")
            if path == "/status":
                state["status_visits"] += 1
                extra = '<button id="clear">Clear notice</button>' if state["status_visits"] > 1 else ""
                return self._send(_page("Status", f'<button id="refresh">Refresh</button>{extra}'))
            self._send("not found", "text/plain", 404)

        def do_POST(self):  # noqa: N802
            path = urlsplit(self.path).path
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            log.append(("POST", path))
            if path.endswith("/archive"):
                state["archived"] += 1
            self._send('{"ok": true}', "application/json")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/", log, state
