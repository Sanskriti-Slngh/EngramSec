"""Branching-workflow fixture (development only; stdlib; genuine state).

Two independent safe writes each gate a distinct deeper subtree, so a focused sweep must spread its
attention across BOTH unlocked workflows rather than exhausting one. Navigation breadth keeps both
writes deferred under the baseline (as in workflow_lab).

  GET  /                 landing
  GET  /<section>        one of SECTIONS index pages of item links   (navigation breadth)
  GET  /<leaf>/<n>       leaf item page                              (navigation)
  GET  /workspace        two create forms: project and report
  POST /projects         create project N -> /project/N              [UNLOCKING write A]
  GET  /project/N[/settings|/members]                                reachable only after write A
  POST /reports          create report N -> /report/N                [UNLOCKING write B]
  GET  /report/N[/summary|/export]                                   reachable only after write B

Ground truth: FUNCTIONAL_CAPABILITIES, ALWAYS_REACHABLE, WRITE_UNLOCKS. STATE.functions is the executed
ledger.
"""
from __future__ import annotations

import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

CATALOG_ITEMS = 60
SECTIONS = {"catalog": "item", "guides": "guide", "docs": "doc", "archive": "arch",
            "notes": "note", "wiki": "page"}

FUNCTIONAL_CAPABILITIES = {
    "home", "section_view", "item_view", "workspace",
    "project_create", "project_overview", "project_settings", "project_members",
    "report_create", "report_overview", "report_summary", "report_export",
}
ALWAYS_REACHABLE = {"home", "section_view", "item_view", "workspace"}
WRITE_UNLOCKS = {
    "project_create": {"project_overview", "project_settings", "project_members"},
    "report_create": {"report_overview", "report_summary", "report_export"},
}


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.projects: dict[int, dict] = {}
        self.reports: dict[int, dict] = {}
        self.pid = 0
        self.rid = 0
        self.functions: Counter[str] = Counter()
        self.log: list[dict] = []

    def executed(self, key: str) -> None:
        with self.lock:
            self.functions[key] += 1

    def snapshot(self) -> dict:
        with self.lock:
            return {"functions": dict(self.functions), "projects": len(self.projects),
                    "reports": len(self.reports), "distinct_paths": len({e["path"] for e in self.log})}


STATE = _State()


def _page(title: str, body: str) -> bytes:
    sections = " ".join(f"<a href='/{s}'>{s.title()}</a>" for s in SECTIONS)
    return (f"<!doctype html><html><head><title>{title}</title></head><body>"
            f"<nav aria-label='main'><a href='/'>Home</a> {sections} <a href='/workspace'>Workspace</a></nav>"
            f"<main>{body}</main></body></html>").encode()


class BranchLabHandler(BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        return

    def _send(self, body: bytes, status: int = 200, location: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if location:
            self.send_header("Location", location)
        self.end_headers()
        self.wfile.write(body)

    def _subtree(self, kind: str, store: dict, parts: list[str]):
        try:
            ident = int(parts[1])
        except (IndexError, ValueError):
            return self._send(_page("Not found", "<h1>404</h1>"), status=404)
        if ident not in store:
            return self._send(_page("Not found", "<h1>404</h1>"), status=404)
        sub = parts[2] if len(parts) > 2 else None
        if sub is None:
            STATE.executed(f"{kind}_overview")
            links = (f"<a href='/{kind}/{ident}/settings'>Settings</a> <a href='/{kind}/{ident}/members'>Members</a>"
                     if kind == "project" else
                     f"<a href='/{kind}/{ident}/summary'>Summary</a> <a href='/{kind}/{ident}/export'>Export</a>")
            return self._send(_page(f"{kind} {ident}", f"<h1>{kind} {ident}</h1>{links}"))
        valid = {"project": ("settings", "members"), "report": ("summary", "export")}[kind]
        if sub in valid:
            STATE.executed(f"{kind}_{sub}")
            return self._send(_page(f"{kind} {sub}", f"<h1>{sub} of {kind} {ident}</h1>"))
        return self._send(_page("Not found", "<h1>404</h1>"), status=404)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        with STATE.lock:
            STATE.log.append({"method": "GET", "path": path})
        parts = [p for p in path.split("/") if p]
        if path == "/":
            STATE.executed("home")
            return self._send(_page("Home", "<h1>Home</h1>"))
        if len(parts) == 1 and parts[0] in SECTIONS:
            STATE.executed("section_view")
            leaf = SECTIONS[parts[0]]
            links = "".join(f"<li><a href='/{leaf}/{i}'>{parts[0].title()} {i}</a></li>"
                            for i in range(1, CATALOG_ITEMS + 1))
            return self._send(_page(parts[0].title(), f"<h1>{parts[0].title()}</h1><ul>{links}</ul>"))
        if len(parts) == 2 and parts[0] in SECTIONS.values():
            n = int(parts[1]) if parts[1].isdigit() else 0
            if 1 <= n <= CATALOG_ITEMS:
                STATE.executed("item_view")
                return self._send(_page(f"Entry {n}", f"<h1>Entry {n}</h1>"))
            return self._send(_page("Not found", "<h1>404</h1>"), status=404)
        if path == "/workspace":
            STATE.executed("workspace")
            return self._send(_page("Workspace", "<h1>Workspace</h1>"
                                    "<form action='/projects' method='post'>"
                                    "<input name='name' aria-label='project name'><button>Create project</button></form>"
                                    "<form action='/reports' method='post'>"
                                    "<input name='title' aria-label='report title'><button>Create report</button></form>"))
        if parts[:1] == ["project"]:
            return self._subtree("project", STATE.projects, parts)
        if parts[:1] == ["report"]:
            return self._subtree("report", STATE.reports, parts)
        return self._send(_page("Not found", "<h1>404</h1>"), status=404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        path = urlsplit(self.path).path
        with STATE.lock:
            STATE.log.append({"method": "POST", "path": path})
        if path == "/projects":
            with STATE.lock:
                STATE.pid += 1
                pid = STATE.pid
                STATE.projects[pid] = {}
            STATE.executed("project_create")
            return self._send(b"", status=302, location=f"/project/{pid}")
        if path == "/reports":
            with STATE.lock:
                STATE.rid += 1
                rid = STATE.rid
                STATE.reports[rid] = {}
            STATE.executed("report_create")
            return self._send(b"", status=302, location=f"/report/{rid}")
        return self._send(_page("Not found", "<h1>404</h1>"), status=404)


def start_branch_lab(port: int = 0) -> tuple[ThreadingHTTPServer, str, _State]:
    STATE.reset()
    server = ThreadingHTTPServer(("127.0.0.1", port), BranchLabHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    return server, url, STATE


if __name__ == "__main__":
    srv, url, _ = start_branch_lab(8081)
    print(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
