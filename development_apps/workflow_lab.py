"""Multi-step workflow fixture (development only; stdlib; genuine server state).

Isolates the scheduler question from authentication: everything is anonymous. Its purpose is a write that
**unlocks deeper functionality** versus a write that unlocks **nothing useful**, under the same deferral
condition seen on real apps and on role_lab (the write sits behind lots of same-depth navigation, so the
baseline scheduler does not reach it before the discovery deadline).

Layout (navigation breadth so the create write stays deferred under the baseline):
  GET  /                      landing: links to /catalog, /guides, /workspace, /feedback
  GET  /catalog               CATALOG_ITEMS item links  (navigation)
  GET  /item/<n>              leaf item page            (navigation)
  GET  /guides                CATALOG_ITEMS guide links (navigation)
  GET  /guide/<n>             leaf guide page           (navigation)

Positive control — "create project" is a safe POST on a sibling page that gates a whole subtree:
  GET  /workspace             the create-project form
  POST /projects              create project N, redirect /project/N            [UNLOCKING write]
  GET  /project/N             overview (settings / members / tasks)            reachable only after create
  GET  /project/N/settings|members|tasks
  POST /project/N/tasks       create task M                                    [deeper UNLOCKING write]
  GET  /project/N/task/M      task detail                                      reachable only after task create

Negative control — "feedback" is a safe POST that unlocks only a dead-end:
  GET  /feedback ; POST /feedback -> /feedback/thanks ; GET /feedback/thanks   [write that unlocks nothing deeper]

Ground truth: FUNCTIONAL_CAPABILITIES, ALWAYS_REACHABLE, and WRITE_UNLOCKS (write -> capabilities
reachable only after it). STATE.functions is the server-side executed ledger.
"""
from __future__ import annotations

import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

# Same-depth navigation breadth across many pages (not one capped page), so the create write stays
# deferred under the baseline scheduler until the discovery deadline -- as on role_lab and real apps.
CATALOG_ITEMS = 60

# Four section pages (catalog/guides/docs/archive) provide enough same-depth navigation that the create
# write stays deferred under the baseline across a range of budgets.
SECTIONS = {"catalog": "item", "guides": "guide", "docs": "doc", "archive": "arch",
            "notes": "note", "wiki": "page"}

FUNCTIONAL_CAPABILITIES = {
    "home", "section_view", "item_view", "workspace", "feedback_form",      # navigation / no write
    "feedback_submit", "feedback_thanks",                                   # negative-control write
    "project_create", "project_overview", "project_settings", "project_members", "project_tasks",
    "task_create", "task_detail",                                           # positive-control write
}
ALWAYS_REACHABLE = {"home", "section_view", "item_view", "workspace", "feedback_form"}
WRITE_UNLOCKS = {
    "project_create": {"project_overview", "project_settings", "project_members", "project_tasks", "task_create"},
    "task_create": {"task_detail"},
    "feedback_submit": {"feedback_thanks"},     # negative control: one dead-end, nothing deeper
}


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.projects: dict[int, dict] = {}
        self.tasks: dict[int, dict] = {}
        self.pid = 0
        self.tid = 0
        self.functions: Counter[str] = Counter()
        self.log: list[dict] = []

    def executed(self, key: str) -> None:
        with self.lock:
            self.functions[key] += 1

    def snapshot(self) -> dict:
        with self.lock:
            return {"functions": dict(self.functions), "projects": len(self.projects),
                    "tasks": len(self.tasks), "distinct_paths": len({e["path"] for e in self.log})}


STATE = _State()


def _page(title: str, body: str) -> bytes:
    sections = " ".join(f"<a href='/{s}'>{s.title()}</a>" for s in SECTIONS)
    return (f"<!doctype html><html><head><title>{title}</title></head><body>"
            f"<nav aria-label='main'><a href='/'>Home</a> {sections} "
            f"<a href='/workspace'>Workspace</a> <a href='/feedback'>Feedback</a></nav>"
            f"<main>{body}</main></body></html>").encode()


class WorkflowLabHandler(BaseHTTPRequestHandler):
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

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        with STATE.lock:
            STATE.log.append({"method": "GET", "path": path})
        parts = [p for p in path.split("/") if p]

        if path == "/":
            STATE.executed("home")
            with STATE.lock:
                plist = "".join(f"<li><a href='/project/{i}'>{p['name']}</a></li>" for i, p in STATE.projects.items())
            return self._send(_page("Home", f"<h1>Home</h1><ul>{plist}</ul>"))
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
                return self._send(_page(f"Entry {n}", f"<h1>Entry {n}</h1><p>Reference content {n}.</p>"))
            return self._send(_page("Not found", "<h1>404</h1>"), status=404)
        if path == "/workspace":
            STATE.executed("workspace")
            return self._send(_page("Workspace", "<h1>Workspace</h1>"
                                    "<form action='/projects' method='post'>"
                                    "<input name='name' aria-label='project name'><button>Create project</button></form>"))
        if path == "/feedback":
            STATE.executed("feedback_form")
            return self._send(_page("Feedback", "<form action='/feedback' method='post'>"
                                    "<input name='message' aria-label='message'><button>Send</button></form>"))
        if path == "/feedback/thanks":
            STATE.executed("feedback_thanks")
            return self._send(_page("Thanks", "<h1>Thank you</h1><p>Your feedback was recorded.</p>"))

        if parts[:1] == ["project"]:
            try:
                pid = int(parts[1])
            except (IndexError, ValueError):
                return self._send(_page("Not found", "<h1>404</h1>"), status=404)
            with STATE.lock:
                exists = pid in STATE.projects
            if not exists:
                return self._send(_page("Not found", "<h1>404</h1>"), status=404)    # unlocked only after create
            sub = parts[2] if len(parts) > 2 else None
            if sub is None:
                STATE.executed("project_overview")
                return self._send(_page("Project", f"<h1>Project {pid}</h1>"
                                        f"<a href='/project/{pid}/settings'>Settings</a> "
                                        f"<a href='/project/{pid}/members'>Members</a> "
                                        f"<a href='/project/{pid}/tasks'>Tasks</a>"))
            if sub == "settings":
                STATE.executed("project_settings")
                return self._send(_page("Settings", f"<h1>Settings for project {pid}</h1>"
                                        f"<form action='/project/{pid}/settings' method='post'>"
                                        "<input name='name' aria-label='rename'><button>Rename</button></form>"))
            if sub == "members":
                STATE.executed("project_members")
                return self._send(_page("Members", f"<h1>Members of project {pid}</h1><ul><li>owner</li></ul>"))
            if sub == "tasks":
                STATE.executed("project_tasks")
                with STATE.lock:
                    tl = "".join(f"<li><a href='/project/{pid}/task/{t}'>{d['title']}</a></li>"
                                 for t, d in STATE.tasks.items() if d["project"] == pid)
                return self._send(_page("Tasks", f"<h1>Tasks</h1><ul>{tl or '<li>No tasks</li>'}</ul>"
                                        f"<form action='/project/{pid}/tasks' method='post'>"
                                        "<input name='title' aria-label='task title'><button>Add task</button></form>"))
            if sub == "task":
                try:
                    tid = int(parts[3])
                except (IndexError, ValueError):
                    return self._send(_page("Not found", "<h1>404</h1>"), status=404)
                with STATE.lock:
                    task = STATE.tasks.get(tid)
                if not task or task["project"] != pid:
                    return self._send(_page("Not found", "<h1>404</h1>"), status=404)
                STATE.executed("task_detail")
                return self._send(_page("Task", f"<h1>{task['title']}</h1><p>in project {pid}</p>"))
        return self._send(_page("Not found", "<h1>404</h1>"), status=404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode() if length else "").items()}
        path = urlsplit(self.path).path
        with STATE.lock:
            STATE.log.append({"method": "POST", "path": path})
        parts = [p for p in path.split("/") if p]

        if path == "/projects":
            with STATE.lock:
                STATE.pid += 1
                pid = STATE.pid
                STATE.projects[pid] = {"name": form.get("name") or f"Project {pid}"}
            STATE.executed("project_create")
            return self._send(b"", status=302, location=f"/project/{pid}")
        if path == "/feedback":
            STATE.executed("feedback_submit")
            return self._send(b"", status=302, location="/feedback/thanks")
        if parts[:1] == ["project"] and parts[-1] == "tasks":
            try:
                pid = int(parts[1])
            except (IndexError, ValueError):
                return self._send(_page("Not found", "<h1>404</h1>"), status=404)
            with STATE.lock:
                if pid not in STATE.projects:
                    return self._send(_page("Not found", "<h1>404</h1>"), status=404)
                STATE.tid += 1
                tid = STATE.tid
                STATE.tasks[tid] = {"project": pid, "title": form.get("title") or f"Task {tid}"}
            STATE.executed("task_create")
            return self._send(b"", status=302, location=f"/project/{pid}/tasks")
        if parts[:1] == ["project"] and parts[-1] == "settings":
            STATE.executed("project_settings")         # rename: safe content update, no new capability
            return self._send(b"", status=302, location=self.path)
        return self._send(_page("Not found", "<h1>404</h1>"), status=404)


def start_workflow_lab(port: int = 0) -> tuple[ThreadingHTTPServer, str, _State]:
    STATE.reset()
    server = ThreadingHTTPServer(("127.0.0.1", port), WorkflowLabHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    return server, url, STATE


if __name__ == "__main__":
    srv, url, _ = start_workflow_lab(8079)
    print(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
