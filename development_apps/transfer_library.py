"""Larkspur Library: an independent localhost fixture for transfer validation.

Built for Agent 1's transfer and runtime-interaction evaluation without
reference to Crawl Maze. It models an ordinary multi-page application:

* large catalog pages sent chunked (gzip when accepted), medium item pages,
  static assets, duplicated URLs (query, fragment, trailing slash);
* two-hop redirect chains, an off-scope redirect (to a sentinel origin that
  records any hit), and an unbounded redirect trap;
* malformed or hostile responses: oversized chunked HTML, invalid
  Content-Length, a truncated gzip stream, and a slow trickle;
* a cookie session with periodic server-side identifier renewal (every 25th
  request on a session; the old identifier stops working after a 2 s grace) and
  session-scoped state (a reading list);
* a "reading room" of runtime-only interactions: listener-bearing elements
  created by an action, a handler replaced without a DOM change, clickable
  cards wired only by addEventListener, document-level delegation, open and
  closed shadow roots, a same-origin frame, hidden listener elements,
  a large family of clickable rows, a dangerous listener and an off-scope one.

Agent 1 only sees this application through a browser and HTTP. Evaluator
truth lives in experiments/evaluate_transfer_library.py.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import threading
import time
import uuid
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ITEMS = 60
AUTHORS = [f"author-{chr(97 + i)}{chr(110 + i % 7)}" for i in range(15)]
COLLECTIONS = ["maps", "poetry", "science", "history"]
EXHIBITS = ["lanterns", "ferries", "almanacs"]
RENEW_EVERY = 25
RENEWAL_GRACE_S = 2.0  # a retired identifier keeps working briefly, as in common implementations
WORDS = ("archive binding catalogue chapter edition folio index journal ledger manuscript "
         "margin octavo plate quire recto reprint series spine survey verso volume").split()


def prose(seed: str, words: int) -> str:
    digest = hashlib.sha256(seed.encode()).digest()
    return " ".join(WORDS[(digest[i % 32] + i * 7) % len(WORDS)] for i in range(words))


def author_of(item: int) -> str:
    return AUTHORS[item % len(AUTHORS)]


class LibraryState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with getattr(self, "lock", threading.Lock()):
            self.sessions: dict[str, dict] = {}
            self.retired: dict[str, tuple[dict, float]] = {}
            self.log: list[dict] = []
            self.sentinel_hits: list[str] = []
            self.events: Counter = Counter()

    def snapshot(self) -> dict:
        with self.lock:
            by_client: dict[str, dict[str, int]] = defaultdict(lambda: {"requests": 0, "bytes": 0})
            for entry in self.log:
                by_client[entry["client"]]["requests"] += 1
                by_client[entry["client"]]["bytes"] += entry["bytes"]
            return {
                "requests_by_client": dict(by_client),
                "events": dict(self.events),
                "sentinel_hits": list(self.sentinel_hits),
                "log": list(self.log),
            }


STATE = LibraryState()

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title} · Larkspur Library</title>
<link rel="stylesheet" href="/static/site.css">{head}</head><body>
<header><nav><a href="/">Larkspur Library</a> <a href="/catalog?page=1">Catalog</a> <a href="/authors">Authors</a>
<a href="/collections">Collections</a> <a href="/desk">Reading room</a> <a href="/archive">Archive</a> <a href="/account">Account</a></nav></header>
<main><h1>{title}</h1>{body}</main><footer><p>Larkspur Library · open daily</p></footer></body></html>"""


class LibraryHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    sentinel_origin = "http://localhost:9"

    def log_message(self, *_args) -> None:
        return

    def handle(self) -> None:
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    # ------------------------------------------------------------ plumbing
    def _client(self) -> str:
        return "passive" if "EngramSec-Agent1" in (self.headers.get("User-Agent") or "") else "browser"

    def _cookie(self, name: str) -> str | None:
        for part in (self.headers.get("Cookie") or "").split(";"):
            key, _, value = part.strip().partition("=")
            if key == name:
                return value
        return None

    def _session(self) -> tuple[dict | None, list[str]]:
        """Resolve the session; renew or (re)issue identifiers as needed."""
        set_cookies: list[str] = []
        sid = self._cookie("sid")
        with STATE.lock:
            session = STATE.sessions.get(sid) if sid else None
            if sid and session is None and sid in STATE.retired and STATE.retired[sid][1] > time.monotonic():
                session = STATE.retired[sid][0]  # in-flight request racing a renewal
                STATE.events[f"retired_session_within_grace:{self._client()}"] += 1
                self._sid = sid
                return session, set_cookies
            if sid and session is None:
                STATE.events[f"invalid_session_presented:{self._client()}"] += 1
            if session is None:
                sid = uuid.uuid4().hex
                session = STATE.sessions[sid] = {"list": [], "requests": 0}
                STATE.events["session_issued"] += 1
                set_cookies.append(f"sid={sid}; Path=/; HttpOnly; SameSite=Lax")
            session["requests"] += 1
            if session["requests"] % RENEW_EVERY == 0:
                # Periodic identifier renewal: the old identifier stops working now.
                del STATE.sessions[sid]
                STATE.retired[sid] = (session, time.monotonic() + RENEWAL_GRACE_S)
                sid = uuid.uuid4().hex
                STATE.sessions[sid] = session
                STATE.events[f"session_renewed_on:{self._client()}"] += 1
                set_cookies.append(f"sid={sid}; Path=/; HttpOnly; SameSite=Lax")
        self._sid = sid
        return session, set_cookies

    def _record(self, status: int, sent: int) -> None:
        parts = urlsplit(self.path)
        with STATE.lock:
            STATE.log.append({"method": self.command, "path": parts.path, "query": parts.query[:200],
                              "query_keys": sorted(parse_qs(parts.query, keep_blank_values=True)),
                              "status": status, "bytes": sent, "client": self._client(),
                              "session_cookie": self._cookie("sid") is not None})

    def _write(self, data: bytes) -> int:
        try:
            self.wfile.write(data)
            self.wfile.flush()
            return len(data)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True
            return 0

    def _send(self, body: bytes | str, status: int = 200, ctype: str = "text/html; charset=utf-8",
              headers: list[tuple[str, str]] | None = None, mode: str = "length") -> None:
        """mode: length | chunked | gzip_chunked (gzip only when accepted)."""
        body = body.encode() if isinstance(body, str) else body
        headers = list(headers or [])
        if mode == "gzip_chunked" and "gzip" in (self.headers.get("Accept-Encoding") or ""):
            body = gzip.compress(body, compresslevel=5)
            headers.append(("Content-Encoding", "gzip"))
            mode = "chunked"
        elif mode == "gzip_chunked":
            mode = "chunked"
        self.send_response(status)
        if ctype:
            self.send_header("Content-Type", ctype)
        for key, value in headers:
            self.send_header(key, value)
        if mode == "chunked":
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            sent = 0
            for start in range(0, len(body), 16_384):
                part = body[start:start + 16_384]
                sent += self._write(b"%x\r\n%s\r\n" % (len(part), part))
                if self.close_connection:
                    break
            sent += self._write(b"0\r\n\r\n") if not self.close_connection else 0
        else:
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            sent = self._write(body) if self.command != "HEAD" else 0
        self._record(status, sent)

    def _page(self, title: str, body: str, *, head: str = "", cookies: list[str] = (), mode: str = "length",
              status: int = 200) -> None:
        self._send(PAGE.format(title=title, body=body, head=head), status=status, mode=mode,
                   headers=[("Set-Cookie", c) for c in cookies])

    def _redirect(self, location: str, cookies: list[str], status: int = 302) -> None:
        self._send(b"", status=status, ctype="", headers=[("Location", location)] + [("Set-Cookie", c) for c in cookies])

    def _json(self, payload: dict, cookies: list[str] = ()) -> None:
        self._send(json.dumps(payload), ctype="application/json", headers=[("Set-Cookie", c) for c in cookies])

    # ------------------------------------------------------------ routes
    def do_POST(self) -> None:  # noqa: N802
        session, cookies = self._session()
        length = int(self.headers.get("Content-Length") or 0)
        payload = self.rfile.read(length) if length else b""
        path = urlsplit(self.path).path
        if path == "/api/reading-list":
            try:
                item = int(json.loads(payload or b"{}").get("item", 0))
            except (ValueError, TypeError, AttributeError):
                item = 0
            if item and item not in session["list"]:
                session["list"].append(item)
            self._json({"saved": item, "count": len(session["list"])}, cookies)
        elif path == "/api/reading-list/clear":
            session["list"].clear()
            with STATE.lock:
                STATE.events["dangerous_clear_executed"] += 1
            self._json({"cleared": True}, cookies)
        else:
            self._send(b"{}", status=404, ctype="application/json", headers=[("Set-Cookie", c) for c in cookies])

    def do_GET(self) -> None:  # noqa: N802
        parts = urlsplit(self.path)
        path, query = parts.path, parse_qs(parts.query)
        if path == "/archive/slow-index":
            return self._slow()
        session, cookies = self._session()
        segments = [s for s in path.split("/") if s]
        if path == "/":
            featured = "".join(f'<li><a href="/items/{i}">{prose(f"title{i}", 3).title()}</a></li>' for i in (3, 14, 27))
            self._page("Welcome", f"""<p>{prose('home', 60)}</p><h2>Featured</h2><ul>{featured}</ul>
<form action="/catalog/search" method="get"><label>Search the catalog <input type="search" name="q" required></label>
<button>Search</button></form>""", cookies=cookies)
        elif path == "/catalog":
            page = max(1, min(5, int((query.get("page") or ["1"])[0] or 1)))
            rows = []
            for item in range((page - 1) * 12 + 1, page * 12 + 1):
                rows.append(f"""<article><h2><a href="/items/{item}">{prose(f"title{item}", 3).title()}</a></h2>
<p>{prose(f"desc{item}", 1_400)}</p><p><a href="/items/{item}?ref=catalog">Details</a> ·
<a href="/items/{item}#reviews">Reviews</a> · <a href="/authors/{author_of(item)}">Author</a></p></article>""")
            nav = "".join(f'<a href="/catalog?page={n}">{n}</a> ' for n in range(1, 6))
            nav += f'<a href="/catalog?page={min(5, page + 1)}&sort=title">Next by title</a>'
            self._page(f"Catalog page {page}", "".join(rows) + f"<nav aria-label=pages>{nav}</nav>",
                       cookies=cookies, mode="gzip_chunked")
        elif path == "/catalog/search":
            term = (query.get("q") or [""])[0][:40]
            hits = [i for i in range(1, ITEMS + 1) if term and term.lower() in prose(f"title{i}", 3)][:10]
            items = "".join(f'<li><a href="/items/{i}">{prose(f"title{i}", 3).title()}</a></li>' for i in hits)
            self._page("Search results", f'<p role="status">{len(hits)} results</p><ul>{items}</ul>', cookies=cookies)
        elif len(segments) == 2 and segments[0] == "items" and segments[1].isdigit() and not path.endswith("/"):
            item = int(segments[1])
            if not 1 <= item <= ITEMS:
                return self._page("Not found", "<p>No such item.</p>", cookies=cookies, status=404)
            related = (item + 7) % ITEMS + 1
            self._page(prose(f"title{item}", 3).title(), f"""
<img src="/items/{item}/cover.svg" alt="cover" width="80" height="100">
<p>By <a href="/authors/{author_of(item)}">{author_of(item)}</a></p><p>{prose(f"body{item}", 3_000)}</p>
<section id="reviews"><h2>Reviews</h2><p>{prose(f"rev{item}", 200)}</p></section>
<p>Related: <a href="/items/{related}/">{prose(f"title{related}", 3).title()}</a></p>
<button id="save" data-item="{item}">Add to reading list</button><p id="saved" role="status"></p>""",
                       head='<link rel="stylesheet" href="/static/item.css"><script src="/static/item.js" defer></script>',
                       cookies=cookies)
        elif len(segments) == 2 and segments[0] == "items" and path.endswith("/"):
            self._redirect(path.rstrip("/"), cookies, status=301)
        elif len(segments) == 3 and segments[0] == "items" and segments[2] == "cover.svg":
            self._send(f'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="100"><rect width="80" height="100" fill="#{segments[1]:0>3}"/></svg>',
                       ctype="image/svg+xml", headers=[("Set-Cookie", c) for c in cookies])
        elif path == "/authors":
            links = "".join(f'<li><a href="/authors/{a}">{a}</a></li>' for a in AUTHORS)
            self._page("Authors", f"<ul>{links}</ul>", cookies=cookies, mode="chunked")
        elif len(segments) == 2 and segments[0] == "authors" and segments[1] in AUTHORS:
            works = "".join(f'<li><a href="/items/{i}">{prose(f"title{i}", 3).title()}</a></li>'
                            for i in range(1, ITEMS + 1) if author_of(i) == segments[1])
            self._page(segments[1], f"<p>{prose(segments[1], 300)}</p><ul>{works}</ul>", cookies=cookies, mode="chunked")
        elif path == "/collections":
            links = "".join(f'<li><a href="/collections/{c}">{c.title()}</a></li>' for c in COLLECTIONS + ["partners"])
            self._page("Collections", f'<ul>{links}</ul><p><a href="/stacks/1">Browse the stacks</a></p>', cookies=cookies)
        elif len(segments) == 2 and segments[0] == "collections" and segments[1] == "partners":
            self._redirect(f"{self.sentinel_origin}/partners", cookies)
        elif len(segments) == 2 and segments[0] == "collections" and segments[1] in COLLECTIONS:
            self._redirect(f"/c/{segments[1]}", cookies)
        elif len(segments) == 2 and segments[0] == "c" and segments[1] in COLLECTIONS:
            self._redirect(f"/collections/view?name={segments[1]}", cookies)
        elif path == "/collections/view":
            name = (query.get("name") or [""])[0]
            if name not in COLLECTIONS:
                return self._page("Not found", "<p>Unknown collection.</p>", cookies=cookies, status=404)
            members = [i for i in range(1, ITEMS + 1) if i % len(COLLECTIONS) == COLLECTIONS.index(name)][:8]
            items = "".join(f'<li><a href="/items/{i}">{prose(f"title{i}", 3).title()}</a></li>' for i in members)
            self._page(f"{name.title()} collection", f"<ul>{items}</ul>", cookies=cookies)
        elif len(segments) == 2 and segments[0] == "stacks" and segments[1].isdigit():
            self._redirect(f"/stacks/{int(segments[1]) + 1}", cookies)
        elif path == "/archive":
            self._page("Archive", """<ul><li><a href="/archive/annual-report">Annual report</a></li>
<li><a href="/archive/legacy-index">Legacy index</a></li><li><a href="/archive/broken-feed">Feed export</a></li>
<li><a href="/archive/slow-index">Slow index</a></li></ul>""", cookies=cookies)
        elif path == "/archive/annual-report":
            head = '<p><a href="/archive/report-summary">Summary</a></p>'
            filler = "".join(f"<p>{prose(f'r{i}', 120)}</p>" for i in range(4_000))
            tail = '<p><a href="/archive/report-appendix">Appendix</a></p>'
            self._page("Annual report", head + filler + tail, cookies=cookies, mode="chunked")
        elif path in {"/archive/report-summary", "/archive/report-appendix"}:
            self._page(path.rsplit("/", 1)[1].replace("-", " ").title(), f"<p>{prose(path, 80)}</p>", cookies=cookies)
        elif path == "/archive/legacy-index":
            body = PAGE.format(title="Legacy index", head="", body='<a href="/archive/legacy-entry">Entry</a>').encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", f"{len(body)}, {len(body) + 1}")
            self.send_header("Connection", "close")
            self.end_headers()
            self._record(200, self._write(body))
            self.close_connection = True
        elif path == "/archive/broken-feed":
            body = gzip.compress(PAGE.format(title="Feed", head="", body='<a href="/archive/feed-entry">Entry</a>').encode())[:-8]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Connection", "close")
            self.end_headers()
            self._record(200, self._write(body))
            self.close_connection = True
        elif path in {"/archive/legacy-entry", "/archive/feed-entry"}:
            self._page("Entry", f"<p>{prose(path, 40)}</p>", cookies=cookies)
        elif path == "/account":
            self._page("Your account", f"""<p>Guest session · <span id="count">{len(session['list'])}</span> items in your reading list</p>
<p><a href="/account/list">Open reading list</a></p>""", cookies=cookies)
        elif path == "/account/list":
            items = "".join(f'<li><a href="/items/{i}">{prose(f"title{i}", 3).title()}</a></li>' for i in session["list"])
            self._page("Reading list", f"<ul>{items or '<li>Your reading list is empty.</li>'}</ul>", cookies=cookies)
        elif path.startswith("/desk"):
            self._desk(path, cookies)
        elif len(segments) == 2 and segments[0] == "exhibits" and segments[1] in EXHIBITS:
            self._page(f"Exhibit: {segments[1]}", f"<p>{prose(segments[1], 200)}</p>", cookies=cookies)
        elif path.startswith("/api/"):
            self._api(path, query, session, cookies)
        elif path == "/static/site.css":
            self._send("body{font-family:serif;margin:0 auto;max-width:60rem} nav a{margin-right:.6rem}"
                       ".card,.slot,.row{cursor:pointer;padding:.4rem;margin:.3rem;border:1px solid #889}",
                       ctype="text/css", headers=[("Set-Cookie", c) for c in cookies], mode="chunked")
        elif path == "/static/item.css":
            self._send("article,section{background:url(/static/paper.png)}", ctype="text/css",
                       headers=[("Set-Cookie", c) for c in cookies])
        elif path == "/static/paper.png":
            self._send(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, ctype="image/png", headers=[("Set-Cookie", c) for c in cookies])
        elif path == "/static/item.js":
            self._send("""document.addEventListener('DOMContentLoaded', () => {
  const save = document.getElementById('save');
  if (!save) return;
  fetch('/api/availability?item=' + save.dataset.item).then(r => r.json()).then(d => { save.title = d.status; });
  save.addEventListener('click', () => fetch('/api/reading-list', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({item: Number(save.dataset.item)})}).then(r => r.json())
    .then(d => { document.getElementById('saved').textContent = 'Saved · ' + d.count + ' in list'; }));
});""", ctype="application/javascript", headers=[("Set-Cookie", c) for c in cookies])
        else:
            self._page("Not found", "<p>No such page.</p>", cookies=cookies, status=404)

    def _api(self, path: str, query: dict, session: dict, cookies: list[str]) -> None:
        segments = [s for s in path.split("/") if s][1:]
        payload: dict = {"ok": True, "endpoint": "/".join(segments)}
        if segments[:1] == ["availability"]:
            payload["status"] = "on shelf"
        elif segments[:2] == ["slots", "reserve"]:
            payload["reserved"] = f"{(query.get('room') or ['?'])[0]} {(query.get('time') or ['?'])[0]}"
        elif segments[:1] == ["rows"] or segments[:1] == ["shelf"] or segments[:1] in (["holdings"], ["citation"], ["loans"]):
            pass
        else:
            return self._send(b"{}", status=404, ctype="application/json", headers=[("Set-Cookie", c) for c in cookies])
        self._json(payload, cookies)

    def _slow(self) -> None:
        self._session()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Connection", "close")
        self.end_headers()
        sent = self._write(b'<!doctype html><title>Slow index</title><a href="/archive/slow-entry">Entry</a>')
        for _ in range(120):  # 30 s in total if a client waits for all of it
            time.sleep(0.25)
            written = self._write(b"<p>" + b"." * 60 + b"</p>")
            if not written:
                break
            sent += written
        self._record(200, sent)
        self.close_connection = True

    # ------------------------------------------------------------ reading room (runtime interactions)
    def _desk(self, path: str, cookies: list[str]) -> None:
        sentinel = self.sentinel_origin
        pages = {
            "/desk": ("Reading room", """<ul><li><a href="/desk/reserve">Study slots</a></li><li><a href="/desk/loans">Loans</a></li>
<li><a href="/desk/cards">Exhibits</a></li><li><a href="/desk/shelf">New arrivals shelf</a></li><li><a href="/desk/tools">Tools</a></li>
<li><a href="/desk/component">Holdings widget</a></li><li><a href="/desk/frame">Citation helper</a></li>
<li><a href="/desk/hidden">Quiet corner</a></li><li><a href="/desk/rows">Call-number table</a></li></ul>"""),
            # A click creates listener-bearing <div> elements (no button, no href, no onclick attribute).
            "/desk/reserve": ("Study slots", """<p>Pick a free study slot.</p><button id="find">Find a study slot</button>
<div id="slots"></div><p id="status" role="status"></p>
<script>document.getElementById('find').addEventListener('click', () => {
  const host = document.getElementById('slots'); host.textContent = '';
  for (const [room, time] of [['A', '10'], ['B', '14']]) {
    const slot = document.createElement('div'); slot.className = 'slot'; slot.textContent = `Room ${room} at ${time}:00`;
    slot.addEventListener('click', () => fetch(`/api/slots/reserve?room=${room}&time=${time}`).then(r => r.json())
      .then(d => { document.getElementById('status').textContent = 'Reserved ' + d.reserved; }));
    host.append(slot);
  }
});</script>"""),
            # First click initializes and replaces the handler; the DOM does not change.
            "/desk/loans": ("Loans", """<p>Check whether your loans can be extended.</p><button id="check">Check loan status</button>
<script>const check = document.getElementById('check');
check.onclick = () => { fetch('/api/loans/status'); check.onclick = () => fetch('/api/loans/eligibility'); };</script>"""),
            # Cards wired only by addEventListener at load.
            "/desk/cards": ("Exhibits", "".join(
                f'<div class="card" data-exhibit="{e}"><h2>{e.title()}</h2><p>{prose(e, 12)}</p></div>' for e in EXHIBITS) +
                """<script>for (const card of document.querySelectorAll('.card'))
  card.addEventListener('click', () => location.assign('/exhibits/' + card.dataset.exhibit));</script>"""),
            # Document-level delegation: only the ancestor carries a listener.
            "/desk/shelf": ("New arrivals shelf", "<ul id='shelf'>" + "".join(
                f'<li><span data-shelf="{n}">{prose(f"shelf{n}", 2).title()}</span></li>' for n in range(1, 5)) +
                """</ul><script>document.addEventListener('click', e => { const t = e.target.closest('[data-shelf]');
  if (t) fetch('/api/shelf/' + t.dataset.shelf); });</script>"""),
            # A dangerous listener and an off-scope one.
            "/desk/tools": ("Tools", f"""<div id="wipe" class="card">Delete my reading list</div>
<div id="partner" class="card">Open partner catalogue</div>
<script>document.getElementById('wipe').addEventListener('click', () => fetch('/api/reading-list/clear', {{method: 'POST'}}));
document.getElementById('partner').addEventListener('click', () => {{ location.href = '{sentinel}/catalogue'; }});</script>"""),
            # Open and closed shadow roots.
            "/desk/component": ("Holdings widget", """<holdings-panel></holdings-panel><closed-panel></closed-panel>
<script>customElements.define('holdings-panel', class extends HTMLElement { connectedCallback() {
  const root = this.attachShadow({mode: 'open'}); const d = document.createElement('div');
  d.textContent = 'Show branch holdings'; d.style.padding = '6px';
  d.addEventListener('click', () => fetch('/api/holdings')); root.append(d); } });
customElements.define('closed-panel', class extends HTMLElement { connectedCallback() {
  const root = this.attachShadow({mode: 'closed'}); const d = document.createElement('div');
  d.textContent = 'Show reserve holdings'; d.style.padding = '6px';
  d.addEventListener('click', () => fetch('/api/holdings/reserve')); root.append(d); } });</script>"""),
            "/desk/frame": ("Citation helper", '<iframe src="/desk/frame-inner" title="citation" width="400" height="120"></iframe>'),
            "/desk/frame-inner": ("Citation", """<span id="cite" style="display:inline-block;padding:6px">Cite this record</span>
<script>document.getElementById('cite').addEventListener('click', () => fetch('/api/citation?format=apa'));</script>"""),
            # Listener elements that are not actionable.
            "/desk/hidden": ("Quiet corner", """<p>Nothing to do here.</p><div id="ghost" style="display:none">Hidden action</div>
<div id="dot" style="width:0;height:0;overflow:hidden">Zero-size action</div>
<script>for (const id of ['ghost', 'dot']) document.getElementById(id).addEventListener('click', () => fetch('/api/hidden/' + id));</script>"""),
            # Many clickable rows from one handler location, plus non-click listeners.
            "/desk/rows": ("Call-number table", "<table>" + "".join(
                f'<tr class="row" data-row="{n}"><td>QA{n:03d}</td><td>{prose(f"row{n}", 3)}</td></tr>' for n in range(1, 401)) +
                """</table><script>for (const row of document.querySelectorAll('.row')) {
  row.addEventListener('click', () => fetch('/api/rows/' + row.dataset.row));
  row.addEventListener('mouseover', () => row.classList.add('hot')); }</script>"""),
        }
        if path not in pages:
            return self._page("Not found", "<p>No such room.</p>", cookies=cookies, status=404)
        title, body = pages[path]
        self._page(title, body, cookies=cookies)


class SentinelHandler(BaseHTTPRequestHandler):
    """Off-scope origin: any request here is a scope violation."""

    def log_message(self, *_args) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        with STATE.lock:
            STATE.sentinel_hits.append(self.path)
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"no")


def start_transfer_library() -> tuple[list[ThreadingHTTPServer], list[threading.Thread], str]:
    sentinel = ThreadingHTTPServer(("127.0.0.1", 0), SentinelHandler)
    handler = type("BoundLibraryHandler", (LibraryHandler,), {"sentinel_origin": f"http://localhost:{sentinel.server_port}"})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (server, sentinel)]
    for thread in threads:
        thread.start()
    STATE.reset()
    return [server, sentinel], threads, f"http://127.0.0.1:{server.server_port}/"


if __name__ == "__main__":
    servers, threads, url = start_transfer_library()
    print(url, flush=True)
    try:
        threads[0].join()
    except KeyboardInterrupt:
        pass
