"""Replay lab: a small localhost application for replay-scheduler regression
tests. Each page isolates one replay situation; the server logs every request
(method, path, session) so tests can check what replays actually reproduced.

Pages (linked from "/" next to plain decoy pages, so a shallow-first replay
order has cheaper work to do first):
  /lab/div       a click creates a listener <div>; clicking it GETs /api/details
  /lab/redefine  one button: first handler GETs /api/first, then is replaced by one that GETs /api/second
  /lab/multi     Begin -> creates "Continue" <div> -> creates "Finish" <div> -> GET /api/finish
  /lab/pair      two buttons with different request structures (/api/reviews, /api/stock?sku=)
  /lab/twins     two <div>s with the same request structure (/api/save/<n>)
  /lab/claim     a one-time voucher: the button exists only while unclaimed (server state)
  /records/3     needs the session cookie; "Show history" GETs /api/records/3/history
  /cart          the cart id is per session; "Refresh cart" GETs /api/carts/<session cart>
  /lab/danger    a listener <div> labelled "Delete all records" that would POST
"""
from __future__ import annotations

import itertools
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


class LabState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.log: list[dict[str, str]] = []
        self.claimed = False
        self.carts: dict[str, int] = {}
        self._sessions = itertools.count(1)
        self._carts = itertools.count(101)

    def new_session(self) -> str:
        with self.lock:
            return f"s{next(self._sessions)}"

    def cart(self, sid: str) -> int:
        with self.lock:
            if sid not in self.carts:
                self.carts[sid] = next(self._carts)
            return self.carts[sid]


STATE = LabState()
DECOYS = [f"/topics/{name}" for name in ("history", "science", "poetry", "travel", "music", "cooking")]

PAGES = {
    "/lab/div": ("Details", """<p>Reveal the details panel.</p><button id=show>Show details</button><div id=host></div>
<script>show.addEventListener('click',()=>{const d=document.createElement('div');d.textContent='Open details';
d.style.padding='6px';d.addEventListener('click',()=>fetch('/api/details'));host.replaceChildren(d);});</script>"""),
    "/lab/redefine": ("Loans", """<p>Check your loans.</p><button id=step>Check loans</button>
<script>step.onclick=()=>{fetch('/api/first');step.onclick=()=>fetch('/api/second');};</script>"""),
    "/lab/multi": ("Wizard", """<p>A three step wizard.</p><button id=begin>Begin</button><div id=w></div>
<script>begin.addEventListener('click',()=>{const c=document.createElement('div');c.textContent='Continue';c.style.padding='6px';
c.addEventListener('click',()=>{if(document.getElementById('finish'))return;const f=document.createElement('div');
f.id='finish';f.textContent='Finish';f.style.padding='6px';
f.addEventListener('click',()=>fetch('/api/finish'));w.append(f);});w.replaceChildren(c);});</script>"""),
    "/lab/pair": ("Product", """<p>Product page.</p><button onclick="fetch('/api/reviews')">Load reviews</button>
<button onclick="fetch('/api/stock?sku=77')">Load stock</button>"""),
    "/lab/twins": ("Saved items", """<p>Save an item.</p><div id=a style="padding:6px">Save first item</div>
<div id=b style="padding:6px">Save second item</div>
<script>a.addEventListener('click',()=>fetch('/api/save/1'));b.addEventListener('click',()=>fetch('/api/save/2'));</script>"""),
    "/lab/danger": ("Admin", """<p>Administration.</p><div id=wipe style="padding:6px">Delete all records</div>
<script>wipe.addEventListener('click',()=>fetch('/api/records/delete',{method:'POST'}));</script>"""),
}


class LabHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _sid(self) -> tuple[str | None, str]:
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name == "sid" and value:
                return value, value
        return None, STATE.new_session()

    def _send(self, status: int, body: str, ctype: str = "text/html", set_sid: str | None = None) -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if set_sid:
            self.send_header("Set-Cookie", f"sid={set_sid}; Path=/; HttpOnly; SameSite=Lax")
        self.end_headers()
        self.wfile.write(data)

    def _page(self, title: str, body: str, set_sid: str | None) -> None:
        nav = '<nav><a href="/">Home</a></nav>'
        self._send(200, f"<!doctype html><title>{title}</title><body>{nav}<main><h1>{title}</h1>{body}</main></body>",
                   set_sid=set_sid)

    def do_GET(self):
        path = urlsplit(self.path).path
        existing, sid = self._sid()
        set_sid = None if existing else sid
        with STATE.lock:
            STATE.log.append({"method": "GET", "path": path, "session": existing or "-"})
        if path.startswith("/api/"):
            if path.startswith("/api/records/"):
                return self._send(200 if existing else 401, '{"ok":%s}' % ("true" if existing else "false"), "application/json")
            if path == "/api/claim":
                STATE.claimed = True
            return self._send(200, '{"ok":true}', "application/json")
        if path == "/":
            links = "".join(f'<li><a href="{p}">{p.rsplit("/", 1)[-1].title()}</a></li>' for p in
                            DECOYS + list(PAGES) + ["/lab/claim", "/records/3", "/cart"])
            return self._page("Replay lab", f"<ul>{links}</ul>", set_sid)
        if path in DECOYS:
            topic = path.rsplit("/", 1)[-1]
            return self._page(topic.title(), f"<p>Articles about {topic}: {' '.join([topic] * 8)}.</p>", set_sid)
        if path in PAGES:
            title, body = PAGES[path]
            return self._page(title, body, set_sid)
        if path == "/lab/claim":
            body = "<p>Vouchers.</p>" + ("<p>No vouchers left.</p>" if STATE.claimed else
                                         "<button onclick=\"fetch('/api/claim')\">Claim voucher</button>")
            return self._page("Vouchers", body, set_sid)
        if path == "/records/3":
            return self._page("Record", "<p>Record details.</p><button onclick=\"fetch('/api/records/3/history')\">Show history</button>", set_sid)
        if path == "/cart":
            cart = STATE.cart(sid)
            return self._page("Cart", f"<p>Your cart.</p><button onclick=\"fetch('/api/carts/{cart}')\">Refresh cart</button>", set_sid)
        self._send(404, "not found", "text/plain", set_sid)

    def do_POST(self):
        with STATE.lock:
            STATE.log.append({"method": "POST", "path": urlsplit(self.path).path, "session": "-"})
        self._send(200, '{"ok":true}', "application/json")


def start_replay_lab() -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    STATE.reset()
    server = ThreadingHTTPServer(("127.0.0.1", 0), LabHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}/"
