"""spa_router_lab — a measurable client-rendered SPA fixture (Track A, capability ground truth).

Deliberately different from js_heavy_lab so passing it is real generalization, not overfitting:
  * client-side routing via history.pushState (URL changes, NO server navigation);
  * controls rendered OUTSIDE any <main> (in a <header> nav and a <div id="view">);
  * delayed hydration (nav enabled after a boot fetch; one late nav item appears later);
  * interaction-gated nested controls inside client-rendered views;
  * a role dimension (member cookie unlocks admin views) for authenticated-session mapping.

Every client view, when rendered, fires a tracking GET so the server request log is a clean
behavioral oracle (the VIEW is client-rendered; the ping proves it was reached). GET-only, no
destructive routes, no auth typing required (member surface is reached via an operator session cookie).
"""
from __future__ import annotations

import json
import threading
from collections import Counter
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

MEMBER_COOKIE = "spa_member=member-7c2a"


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

# Ground-truth capabilities. route = the server path that proves the capability fired.
# role: "anonymous" reachable without a session; "member" needs the member cookie.
CAPABILITIES: list[dict] = [
    {"id": "nav_home", "route": "/", "role": "anonymous"},
    {"id": "open_dashboard", "route": "/api/view?r=dashboard", "role": "anonymous"},
    {"id": "dashboard_metric", "route": "/api/metric", "role": "anonymous"},
    {"id": "open_reports", "route": "/api/view?r=reports", "role": "anonymous"},
    {"id": "report_export", "route": "/api/report/export", "role": "anonymous"},
    {"id": "open_settings", "route": "/api/view?r=settings", "role": "anonymous"},
    {"id": "settings_apply", "route": "/api/settings/apply", "role": "anonymous"},
    {"id": "open_profile", "route": "/api/view?r=profile", "role": "anonymous"},
    {"id": "profile_load", "route": "/api/profile/data", "role": "anonymous"},
    {"id": "open_activity", "route": "/api/view?r=activity", "role": "anonymous"},  # late-hydrated nav
    {"id": "open_admin", "route": "/api/view?r=admin", "role": "member"},
    {"id": "admin_audit", "route": "/api/admin/audit", "role": "member"},
]


def ground_truth() -> dict:
    return {
        "application": "spa_router_lab",
        "roles": ["anonymous", "member"],
        "member_cookie": MEMBER_COOKIE,
        "capabilities": CAPABILITIES,
        "anonymous_total": sum(1 for c in CAPABILITIES if c["role"] == "anonymous"),
        "member_total": sum(1 for c in CAPABILITIES if c["role"] == "member"),
    }


# View definitions: id -> (html inside #view, optional nested-control script)
_VIEWS = {
    "dashboard": "<h2>Dashboard</h2><button id='metric' data-ping='/api/metric'>Load metric</button>",
    "reports": "<h2>Reports</h2><button id='export' data-ping='/api/report/export'>Export report</button>",
    "settings": "<h2>Settings</h2><button id='apply' data-ping='/api/settings/apply'>Apply settings</button>",
    "profile": "<h2>Profile</h2><button id='pdata' data-ping='/api/profile/data'>Load profile data</button>",
    "activity": "<h2>Activity</h2><p>Recent activity feed.</p>",
    "admin": "<h2>Admin</h2><button id='audit' data-ping='/api/admin/audit'>Run audit</button>",
}

_SHELL = """<!doctype html><html><head><title>SPA Router Lab</title></head><body>
<header id="bar" aria-busy="true">
  <strong>SPA Router Lab</strong>
  <nav id="mainnav">
    <button class="route" data-route="dashboard" disabled>Dashboard</button>
    <button class="route" data-route="reports" disabled>Reports</button>
    <button class="route" data-route="settings" disabled>Settings</button>
    <button class="route" data-route="profile" disabled>Profile</button>
  </nav>
  <nav id="membernav"></nav>
</header>
<div id="view">Loading application…</div>
<script>
const MEMBER = document.cookie.includes('spa_member=');
const ping = (p) => fetch(p).catch(()=>{});
const VIEWS = __VIEWS__;
function render(route) {
  const html = VIEWS[route];
  if (!html) return;
  document.querySelector('#view').innerHTML = html;
  ping('/api/view?r=' + route);
  document.querySelectorAll('#view [data-ping]').forEach(b => {
    b.onclick = () => ping(b.getAttribute('data-ping'));
  });
}
function go(route) { history.pushState({route}, '', '/app/' + route); render(route); }
window.onpopstate = (e) => { if (e.state && e.state.route) render(e.state.route); };
// Boot: enable nav after a short fetch (hydration-gated controls, outside <main>).
setTimeout(async () => {
  await ping('/api/boot');
  document.querySelectorAll('#mainnav .route').forEach(b => {
    b.disabled = false;
    b.onclick = () => go(b.getAttribute('data-route'));
  });
  if (MEMBER) {
    const nav = document.querySelector('#membernav');
    const a = document.createElement('button');
    a.className = 'route'; a.setAttribute('data-route','admin'); a.textContent = 'Admin';
    a.onclick = () => go('admin'); nav.appendChild(a);
  }
  document.querySelector('#bar').setAttribute('aria-busy','false');
  // Deep-link support: if we loaded on /app/<route>, render it.
  const m = location.pathname.match(/^\\/app\\/([a-z]+)$/);
  if (m && VIEWS[m[1]]) render(m[1]); else document.querySelector('#view').textContent = 'Select a section.';
}, 350);
// A late-hydrated nav item appears after the initial boot.
setTimeout(() => {
  const nav = document.querySelector('#mainnav');
  const b = document.createElement('button');
  b.className = 'route'; b.setAttribute('data-route','activity'); b.textContent = 'Activity';
  b.onclick = () => go('activity'); nav.appendChild(b);
}, 750);
</script>
</body></html>"""


class SPARouterHandler(BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        return

    def _send(self, body: str, *, status: int = HTTPStatus.OK, content_type: str = "text/html",
              cookie: str | None = None) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(encoded)

    def _is_member(self) -> bool:
        return "spa_member=" in (self.headers.get("Cookie") or "")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/__eval__/stats":
            self._send(json.dumps(STATE.snapshot()), content_type="application/json")
            return
        if path == "/__eval__/ground_truth":
            self._send(json.dumps(ground_truth()), content_type="application/json")
            return
        STATE.record("GET", parsed.path if not parsed.query else f"{parsed.path}?{parsed.query}")
        # The SPA shell is served at / and any /app/<route> (deep-linkable client routes).
        if path == "/" or path.startswith("/app/"):
            self._send(_SHELL.replace("__VIEWS__", json.dumps(_VIEWS)))
            return
        if path == "/api/view":
            # Member gate: the admin view's data is only served to a member session.
            r = parse_qs(parsed.query).get("r", [""])[0]
            if r == "admin" and not self._is_member():
                self._send(json.dumps({"ok": False, "reason": "forbidden"}),
                           status=HTTPStatus.FORBIDDEN, content_type="application/json")
                return
            self._send(json.dumps({"ok": True, "view": r}), content_type="application/json")
            return
        if path in {"/api/admin/audit"} and not self._is_member():
            self._send(json.dumps({"ok": False}), status=HTTPStatus.FORBIDDEN, content_type="application/json")
            return
        if path.startswith("/api/"):
            self._send(json.dumps({"ok": True, "path": path}), content_type="application/json")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path == "/__eval__/reset":
            STATE.reset()
            self._send(json.dumps({"ok": True}), content_type="application/json")
            return
        STATE.record("POST", parsed.path)
        self.send_error(HTTPStatus.NOT_FOUND)


def start_spa_router_lab() -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    STATE.reset()
    server = ThreadingHTTPServer(("127.0.0.1", 0), SPARouterHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}/"
