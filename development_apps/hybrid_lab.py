"""Capability-aware hybrid contract fixture: redundancy next to distinct behavior.

Local, deterministic, stdlib only; the server log and state are operator-side.
- a catalog of 200 records exposing one shared view capability (and one
  per-record handler-driven button);
- two structurally identical buttons ("Check", in sibling menus) calling different endpoints;
- global navigation repeated on every template;
- a stateful chain: Accept enables Continue (server-side flag), and Review's
  Finish button is enabled only once the flag is set;
- a JavaScript-only tab that reveals a control without a URL change;
- a member area entered by a POST form (a state-changing prerequisite that
  verification must not replay).
"""
from __future__ import annotations

import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

RECORDS = 200


def _page(title: str, body: str, script: str = "") -> str:
    nav = ('<nav><a href="/">Home</a> <a href="/catalog">Catalog</a> <a href="/help">Help</a></nav>')
    return (f"<!doctype html><html><head><title>{title}</title></head><body>{nav}<main>{body}</main>"
            f"<script>{script}</script></body></html>")


def start_hybrid_lab():
    log: list[tuple[str, str]] = []
    sessions: dict[str, set[str]] = {}
    state = {"setup_finished": 0, "member_entries": 0}

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

        def _send(self, body: str, ctype: str = "text/html", status: int = 200, location: str | None = None,
                  cookie: str | None = None):
            sid, new = self._sid()
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            if location:
                self.send_header("Location", location)
            if new:
                self.send_header("Set-Cookie", f"sid={sid}; Path=/")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(data)

        def _json(self, body: str = '{"ok": true}'):
            self._send(body, "application/json")

        def do_GET(self):  # noqa: N802
            path = urlsplit(self.path).path
            log.append(("GET", path))
            sid, _ = self._sid()
            if path == "/":
                return self._send(_page("Home", '<h1>Hybrid lab</h1><ul><li><a href="/twins">Twins</a></li>'
                                        '<li><a href="/setup">Setup</a></li><li><a href="/tabs">Tabs</a></li>'
                                        '<li><a href="/account">Account</a></li></ul>'))
            if path == "/help":
                return self._send(_page("Help", "<h1>Help</h1><p>Static help.</p>"))
            if path == "/catalog":
                links = "".join(f'<li><a href="/records/{i}">Item {i}</a></li>' for i in range(1, RECORDS + 1))
                return self._send(_page("Catalog", f"<h1>Catalog</h1><ul>{links}</ul>"))
            if path.startswith("/records/") and path.split("/")[2].isdigit():
                rid = path.split("/")[2]
                return self._send(_page(f"Item {rid}", f'<h1>Item {rid}</h1><button id="h">Show history</button>',
                                        f"document.getElementById('h').onclick=()=>fetch('/api/records/{rid}/history');"))
            if path.startswith("/api/"):
                if path == "/api/setup/continue":
                    sessions[sid].add("setup")
                if path == "/api/setup/finish" and "setup" in sessions[sid]:
                    state["setup_finished"] += 1
                return self._json()
            if path == "/twins":
                return self._send(_page("Twins", '<div role="menu" id="loans"><button id="a">Check</button></div>'
                                        '<div role="menu" id="stock"><button id="b">Check</button></div>',
                                        "document.getElementById('a').onclick=()=>fetch('/api/first');"
                                        "document.getElementById('b').onclick=()=>fetch('/api/second');"))
            if path == "/setup":
                return self._send(_page("Setup", '<button id="accept">Accept terms</button>'
                                        '<button id="continue" disabled>Continue</button>'
                                        '<p><a href="/setup/review">Review</a></p>',
                                        "document.getElementById('accept').onclick=()=>{document.getElementById('continue').disabled=false};"
                                        "document.getElementById('continue').onclick=()=>fetch('/api/setup/continue');"))
            if path == "/setup/review":
                ready = "setup" in sessions[sid]
                return self._send(_page("Review", f'<button id="finish" {"" if ready else "disabled"}>Finish setup</button>',
                                        "document.getElementById('finish').onclick=()=>fetch('/api/setup/finish');"))
            if path == "/tabs":
                return self._send(_page("Tabs", '<button id="t">Show panel</button><div id="panel"></div>',
                                        "document.getElementById('t').onclick=()=>{document.getElementById('panel')"
                                        ".innerHTML='<button id=\"p\">Load panel data</button>';"
                                        "document.getElementById('p').onclick=()=>fetch('/api/panel');};"))
            if path == "/account":
                return self._send(_page("Account", '<form method="post" action="/session">'
                                        '<button type="submit">Enter member mode</button></form>'))
            if path == "/member":
                if "member" not in sessions[sid]:
                    return self._send("", status=303, location="/account")
                return self._send(_page("Member", '<a href="/member/prefs">Preferences</a>'))
            if path == "/member/prefs":
                if "member" not in sessions[sid]:
                    return self._send("", status=303, location="/account")
                return self._send(_page("Preferences", "<h1>Preferences</h1>"))
            self._send("not found", "text/plain", 404)

        def do_POST(self):  # noqa: N802
            path = urlsplit(self.path).path
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            log.append(("POST", path))
            sid, _ = self._sid()
            if path == "/session":
                sessions[sid].add("member")
                state["member_entries"] += 1
                return self._send("", status=303, location="/member", cookie="member=1; Path=/")
            self._send("not found", "text/plain", 404)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/", log, state
