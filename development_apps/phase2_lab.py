"""Phase 2 development fixture: behaviors the live ACG and shadow scheduler must handle.

Local, deterministic, stdlib only. Ground truth and the server log are
operator-side; Agent 1 sees only the browser. Covers: dynamic controls and a
replaced handler; a two-page prerequisite chain (client-enabled control, then a
server-session flag enabling a control on a later page); existing records;
a method-less form whose script POSTs; global navigation on every page;
client-only interactions; a search whose results add links; a write with no
reset; an in-scope WebSocket and an out-of-scope WebSocket attempt.
"""
from __future__ import annotations

import base64
import hashlib
import json
import struct
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ITEMS = {"48213": "Copper kettle", "48217": "Linen apron", "48229": "Oak ladle"}
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _page(title: str, body: str, script: str = "") -> str:
    nav = ('<header><nav><a href="/">Home</a> <a href="/items">Items</a> <a href="/setup">Setup</a> '
           '<a href="/search">Search</a> <a href="/notes">Notes</a> <a href="/live">Live</a></nav></header>')
    return (f"<!doctype html><html><head><title>{title}</title></head><body>{nav}<main>{body}</main>"
            f"<script>{script}</script></body></html>")


def start_phase2_lab():
    log: list[tuple[str, str]] = []
    sessions: dict[str, set[str]] = {}
    state = {"reindex": 0, "notes": []}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_):
            pass

        def _sid(self) -> tuple[str, bool]:
            cookie = self.headers.get("Cookie", "")
            for part in cookie.split(";"):
                if part.strip().startswith("sid="):
                    sid = part.strip()[4:]
                    sessions.setdefault(sid, set())
                    return sid, False
            sid = uuid.uuid4().hex
            sessions[sid] = set()
            return sid, True

        def _send(self, body: str, ctype: str = "text/html", status: int = 200) -> None:
            sid, new = self._sid()
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            if new:
                self.send_header("Set-Cookie", f"sid={sid}; Path=/")
            self.end_headers()
            self.wfile.write(data)

        def _json(self, obj) -> None:
            self._send(json.dumps(obj), "application/json")

        def do_GET(self):  # noqa: N802
            parts = urlsplit(self.path)
            path, query = parts.path, parse_qs(parts.query)
            log.append(("GET", path))
            sid, _ = self._sid()
            if path == "/ws" and self.headers.get("Upgrade", "").lower() == "websocket":
                return self._websocket()
            if path == "/":
                return self._send(_page("Home", '<button id="details">Details</button><div id="panel" hidden>'
                                        '<p>Panel</p></div><button id="remember">Remember view</button>',
                                        "document.getElementById('details').onclick=()=>{const p=document.getElementById('panel');p.hidden=!p.hidden};"
                                        "document.getElementById('remember').onclick=()=>localStorage.setItem('view','compact');"))
            if path == "/items":
                rows = "".join(f'<li><a href="/items/{i}">{n}</a></li>' for i, n in ITEMS.items())
                return self._send(_page("Items", f"<ul>{rows}</ul><button id=reindex>Rebuild index</button>",
                                        "document.getElementById('reindex').onclick=()=>fetch('/api/reindex',{method:'POST'});"))
            if path.startswith("/items/") and path.split("/")[2] in ITEMS:
                item = path.split("/")[2]
                return self._send(_page(ITEMS[item], f'<button id="history">History</button>'
                                        '<button id="upgrade">Upgrade view</button><div id="extra"></div>',
                                        f"let mode='a';const h=()=>fetch('/api/items/{item}/history?mode='+mode);"
                                        "document.getElementById('history').onclick=h;"
                                        "document.getElementById('upgrade').onclick=()=>{if(mode==='b')return;mode='b';"
                                        "const b=document.createElement('button');b.textContent='Compare';"
                                        f"b.onclick=()=>fetch('/api/items/{item}/compare');"
                                        "document.getElementById('extra').appendChild(b);"
                                        "const old=document.getElementById('history');const n=old.cloneNode(true);"
                                        "n.onclick=h;old.replaceWith(n);};"))
            if path.startswith("/api/items/") and path.endswith("/history"):
                item = path.split("/")[3]
                return self._json({"item": {"id": item, "events": [{"id": "77" + item[-2:], "kind": "view"}]},
                                   "mode": (query.get("mode") or ["a"])[0]})
            if path.startswith("/api/items/") and path.endswith("/compare"):
                return self._json({"items": [{"id": i} for i in ITEMS]})
            if path == "/setup":
                return self._send(_page("Setup", '<button id="accept">Accept terms</button>'
                                        '<button id="continue" disabled>Continue</button>'
                                        '<p><a href="/setup/review">Review</a></p>',
                                        "document.getElementById('accept').onclick=()=>{document.getElementById('continue').disabled=false};"
                                        "document.getElementById('continue').onclick=()=>fetch('/api/setup/continue');"))
            if path == "/api/setup/continue":
                sessions[sid].add("setup")
                return self._json({"ok": True})
            if path == "/setup/review":
                ready = "setup" in sessions[sid]
                return self._send(_page("Review", f'<button id="finish" {"" if ready else "disabled"}>Finish setup'
                                        '</button>', "document.getElementById('finish').onclick=()=>fetch('/api/setup/finish');"))
            if path == "/api/setup/finish":
                done = "setup" in sessions[sid]
                state["setup_finished"] = state.get("setup_finished", 0) + int(done)   # chain completed (server side)
                return self._json({"done": done})
            if path == "/search":
                return self._send(_page("Search", '<form action="/search/results" method="get">'
                                        '<input type="search" name="q" required><button>Find</button></form>'))
            if path == "/search/results":
                q = (query.get("q") or [""])[0].lower()
                hits = [i for i in ITEMS if int(hashlib.sha256((q + i).encode()).hexdigest(), 16) % 2 == 0] or \
                    [sorted(ITEMS)[len(q) % 3]]
                rows = "".join(f'<li><a href="/items/{i}">{ITEMS[i]}</a></li>' for i in hits)
                return self._send(_page("Results", f"<ul>{rows}</ul>"))
            if path == "/notes":
                return self._send(_page("Notes", '<form id="note"><input name="title" required>'
                                        '<button>Add note</button></form><ul id="list"></ul>',
                                        "document.getElementById('note').addEventListener('submit',e=>{e.preventDefault();"
                                        "fetch('/api/notes',{method:'POST',headers:{'content-type':'application/json'},"
                                        "body:JSON.stringify({title:e.target.title.value})}).then(r=>r.json()).then(d=>{"
                                        "document.getElementById('list').innerHTML=d.notes.map(n=>'<li>'+n.id+'</li>').join('')})});"))
            if path == "/live":
                return self._send(_page("Live", '<button id="subscribe">Subscribe</button><ul id="feed"></ul>',
                                        "const ws=new WebSocket('ws://'+location.host+'/ws');"
                                        "ws.onmessage=m=>{document.getElementById('feed').innerHTML+='<li>update</li>'};"
                                        "document.getElementById('subscribe').onclick=()=>ws.send(JSON.stringify({type:'subscribe',channel:'news'}));"
                                        "try{new WebSocket('ws://127.0.0.1:65111/elsewhere')}catch(e){}"))
            self._send("not found", "text/plain", 404)

        def do_POST(self):  # noqa: N802
            path = urlsplit(self.path).path
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            log.append(("POST", path))
            if path == "/api/reindex":
                state["reindex"] += 1
                return self._json({"reindexed": state["reindex"]})
            if path == "/api/notes":
                title = (json.loads(body or b"{}").get("title") or "")[:40]
                state["notes"].append({"id": str(90000 + len(state["notes"])), "title": title})
                return self._json({"notes": state["notes"]})
            self._send("not found", "text/plain", 404)

        def _websocket(self) -> None:
            accept = base64.b64encode(hashlib.sha1((self.headers["Sec-WebSocket-Key"] + GUID).encode()).digest())
            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept.decode())
            self.end_headers()
            self.wfile.flush()
            while True:
                head = self.rfile.read(2)
                if len(head) < 2:
                    return
                opcode, length = head[0] & 0x0F, head[1] & 0x7F
                if length == 126:
                    length = struct.unpack(">H", self.rfile.read(2))[0]
                elif length == 127:
                    length = struct.unpack(">Q", self.rfile.read(8))[0]
                mask = self.rfile.read(4) if head[1] & 0x80 else b"\0\0\0\0"
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(self.rfile.read(length)))
                if opcode == 8:
                    return
                log.append(("WS", payload.decode(errors="replace")[:20]))
                reply = json.dumps({"type": "update", "items": [{"id": "48213"}]}).encode()
                self.wfile.write(bytes([0x81, len(reply)]) + reply)
                self.wfile.flush()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/", log, state
