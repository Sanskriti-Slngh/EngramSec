"""Volatile-state restoration fixture (development only; stdlib; deterministic server state).

Each area isolates one kind of difference between a saved page and the page a
restoration actually returns to:

- /board      a scoreboard whose counter and per-row marks change when a task page
              is visited (a GET that mutates server state, outside the target row);
- /clock      a live clock that changes on its own every 100 ms;
- /showcase   an auto-rotating carousel (slides and their links change on their own);
- /records    two records with identical controls (?id=1, ?id=2);
- /desk       a "current record" page whose record follows the last /records visit
              (same URL, different record: acting from it would hit the wrong record);
- /wrap       a link wrapped across two lines inside a narrow table cell.

The server-side reference is the set of functions executed (``STATE.functions``) and,
for the desk, the record each annotation was made against (``STATE.annotations``).
No endpoint writes outside this process; there are no POST endpoints.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

TASKS = {1: "Calibrate sensors", 2: "Rotate keys", 3: "Archive logs", 4: "Audit badges", 5: "Patch firmware",
         6: "Review alerts"}
RECORDS = {1: "Harbor survey", 2: "Quarry ledger"}
FUNCTIONS = ([f"task_run_{k}" for k in TASKS] + ["clock_check_in", "clock_check_out", "clock_status",
             "showcase_wishlist", "showcase_compare", "record_history_1", "record_history_2", "desk_annotate"])


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.visits: dict[int, int] = {}
        self.order = 0
        self.current_record = 1
        self.functions: dict[str, int] = {}
        self.annotations: list[dict[str, int]] = []
        self.log: list[dict[str, str]] = []

    def snapshot(self) -> dict:
        with self.lock:
            return {"visits": dict(self.visits), "current_record": self.current_record,
                    "functions": dict(self.functions), "annotations": list(self.annotations)}


STATE = _State()

NAV = ('<nav><a href="/">Home</a> <a href="/board">Board</a> <a href="/clock">Clock desk</a> '
       '<a href="/showcase">Showcase</a> <a href="/records?id=1">Record one</a> '
       '<a href="/records?id=2">Record two</a> <a href="/desk">Desk</a> <a href="/wrap">Index</a></nav>')
OUT = '<div id="out"></div>'
CALL = ("<script>document.querySelectorAll('button[data-call]').forEach(b => b.addEventListener('click', async () => {"
        "const r = await fetch(b.dataset.call); document.getElementById('out').textContent = await r.text();}));"
        "</script>")


def _page(title: str, body: str, script: str = "") -> str:
    return (f"<!doctype html><html><head><meta charset=utf-8><title>{title}</title></head><body>{NAV}"
            f"<main>{body}</main>{CALL}{script}</body></html>")


def _board() -> str:
    with STATE.lock:
        done = len(STATE.visits)
        rows = "".join(
            f'<tr><td><a href="/board/task/{k}">{name}</a></td>'
            f'<td>{"✓ visit #" + str(STATE.visits[k]) if k in STATE.visits else "—"}</td></tr>'
            for k, name in TASKS.items())
    return _page("Task board", f'<h1>Task board</h1><p class="summary">Completed: {done} / {len(TASKS)} '
                               f'({round(100 * done / len(TASKS))}%)</p><table><tbody>{rows}</tbody></table>')


def _task(k: int) -> str:
    with STATE.lock:
        STATE.order += 1
        STATE.visits.setdefault(k, STATE.order)
    return _page(f"Task {k}", f'<h1>{TASKS[k]}</h1><section><button data-call="/api/task/{k}/run">Run task {k}</button>'
                              f'</section><a href="/board">Back to board</a>{OUT}')


def _clock() -> str:
    script = ("<script>const c=document.getElementById('clock');const tick=()=>{const d=new Date();"
              "c.textContent='Local time '+d.toISOString().slice(11,23);};tick();setInterval(tick,100);</script>")
    body = ('<h1>Clock desk</h1><p><span id="clock">Local time</span></p><div class="actions">'
            '<button data-call="/api/clock/check_in">Check in</button> '
            '<button data-call="/api/clock/check_out">Check out</button> '
            '<button data-call="/api/clock/status">Show status</button></div>' + OUT)
    return _page("Clock desk", body, script)


def _showcase() -> str:
    slides = "".join(f'<div class="slide" style="display:{"block" if k == 1 else "none"}"><p>Slide {k}: '
                     f'{["Night trains", "Glass harbours", "Quiet forges"][k - 1]}</p>'
                     f'<a href="/showcase/slide/{k}">Learn about slide {k}</a></div>' for k in (1, 2, 3))
    script = ("<script>let i=0;const s=[...document.querySelectorAll('.slide')];setInterval(()=>{"
              "s[i].style.display='none';i=(i+1)%s.length;s[i].style.display='block';},200);</script>")
    body = (f'<h1>Showcase</h1><section class="carousel" aria-roledescription="carousel">{slides}</section>'
            '<div class="actions"><button data-call="/api/showcase/wishlist">Add to wishlist</button> '
            '<button data-call="/api/showcase/compare">Compare items</button></div>' + OUT)
    return _page("Showcase", body, script)


def _record(k: int) -> str:
    with STATE.lock:
        STATE.current_record = k
    return _page("Record", f'<h1>{RECORDS[k]}</h1><p>Record reference {k}</p>'
                           f'<button data-call="/api/records/{k}/history">Open history</button>{OUT}')


def _desk() -> str:
    with STATE.lock:
        k = STATE.current_record
    script = ("<script>document.getElementById('annotate').addEventListener('click',async()=>{"
              "const k=document.querySelector('input[name=record]').value;"
              "const r=await fetch('/api/desk/annotate?record='+k);"
              "document.getElementById('out').textContent=await r.text();});</script>")
    body = (f'<h1>Desk</h1><h2>Current record: {RECORDS[k]}</h2><input type="hidden" name="record" value="{k}">'
            f'<button id="annotate">Annotate current</button>{OUT}')
    return _page("Desk", body, script)


def _wrap() -> str:
    rows = "".join(f'<tr><td>{c}</td><td style="width:164px;line-height:2.4"><a href="/wrap/{i}">{t}</a></td><td>{m}</td></tr>'
                   for i, (c, t, m) in enumerate([("dynamic", "Link appears on scroll (IntersectionObserver)", "—"),
                                                  ("links", "Plain link", "—")], start=1))
    return _page("Index", f"<h1>Index</h1><table><tbody>{rows}</tbody></table>")


def _home() -> str:
    return _page("Volatile lab", "<h1>Volatile lab</h1><p>Operations console.</p>")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def _send(self, body: str, ctype: str = "text/html; charset=utf-8", status: int = 200) -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _function(self, name: str, **extra) -> None:
        with STATE.lock:
            STATE.functions[name] = STATE.functions.get(name, 0) + 1
        self._send(json.dumps({"ok": name, **extra}), "application/json")

    def do_GET(self) -> None:  # noqa: N802
        parts = urlsplit(self.path)
        path, query = parts.path, parse_qs(parts.query)
        with STATE.lock:
            STATE.log.append({"method": "GET", "path": path})
        seg = path.strip("/").split("/")
        try:
            if path == "/":
                return self._send(_home())
            if path == "/board":
                return self._send(_board())
            if len(seg) == 3 and seg[:2] == ["board", "task"] and int(seg[2]) in TASKS:
                return self._send(_task(int(seg[2])))
            if path == "/clock":
                return self._send(_clock())
            if path == "/showcase":
                return self._send(_showcase())
            if len(seg) == 3 and seg[:2] == ["showcase", "slide"]:
                return self._send(_page(f"Slide {seg[2]}", f"<h1>Slide {seg[2]}</h1>"))
            if path == "/records" and int(query.get("id", ["0"])[0]) in RECORDS:
                return self._send(_record(int(query["id"][0])))
            if path == "/desk":
                return self._send(_desk())
            if path == "/wrap":
                return self._send(_wrap())
            if len(seg) == 2 and seg[0] == "wrap":
                return self._send(_page("Wrapped", f"<h1>Wrapped {seg[1]}</h1>"))
            if len(seg) == 4 and seg[:2] == ["api", "task"] and seg[3] == "run" and int(seg[2]) in TASKS:
                return self._function(f"task_run_{int(seg[2])}")
            if len(seg) == 3 and seg[:2] == ["api", "clock"] and seg[2] in {"check_in", "check_out", "status"}:
                return self._function(f"clock_{seg[2]}")
            if len(seg) == 3 and seg[:2] == ["api", "showcase"] and seg[2] in {"wishlist", "compare"}:
                return self._function(f"showcase_{seg[2]}")
            if len(seg) == 4 and seg[:2] == ["api", "records"] and seg[3] == "history" and int(seg[2]) in RECORDS:
                return self._function(f"record_history_{int(seg[2])}")
            if path == "/api/desk/annotate":
                requested = int(query.get("record", ["0"])[0])
                with STATE.lock:
                    STATE.annotations.append({"requested": requested, "current": STATE.current_record})
                return self._function("desk_annotate", record=requested)
        except ValueError:
            pass
        self._send("missing", status=404)


def start_volatile_lab():
    STATE.reset()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/", STATE


if __name__ == "__main__":  # manual inspection
    srv, url, _ = start_volatile_lab()
    print(url)
    threading.Event().wait()
