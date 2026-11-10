"""Breadth-starved coverage fixture (development only; stdlib; GET-only; no writes, auth, JS, or
destructive routes).

Purpose (Stage 0 of the LLM-augmentation study): a fixture where functional coverage is genuinely
*budget-starved* by breadth, so that any missed capability is attributable to exploration prioritization
rather than authentication, writes, restoration, or JS/implementation gating. Every functional capability
below is reachable by an ordinary GET to a plainly-linked URL; the only thing standing between the explorer
and full coverage is how it spends a fixed wall-clock budget.

Structure
---------
- BREADTH: six listing sections, each a single repeated template of ``ITEMS`` entries. Each section
  contributes exactly TWO capabilities — its index view and "an item view" — no matter how many items are
  visited. Visiting the 2nd..Nth item yields no new capability (the honest value of a uniform catalog).
  These lists compete for budget and tempt redundant enumeration.
- FUNCTIONAL HUBS (template-distinct): ``/reports``, ``/settings``, ``/ops``. Each hub index links to
  several children with DISTINCT route templates, and those children link to further distinct views —
  genuinely different operations two to three levels deep. A template-aware explorer can recognise these as
  functional areas (>=2 distinct child templates) once it REACHES them; the question is whether it reaches
  and descends them before breadth exhausts the budget.
- AMBIGUOUS LIST: ``/updates`` looks structurally like a breadth list (one template ``/updates/<id>``), but
  a minority of items ("releases") have a deeper changelog workflow while the rest are trivial notes. The
  list page gives no structural tell (one template); only the item CONTENT distinguishes a release from a
  note. A template-count heuristic cannot flag ``/updates`` as functional from its index.

Labels are ordinary and neutral (no "important"/"duplicate"/"workflow" clues). Nav order interleaves
functional hubs among breadth sections so no hardcoded route order is rewarded. Content is fully
deterministic, so matched trials are identical.

Ground truth (evaluation-only; never exposed to the explorer):
  FUNCTIONAL_CAPABILITIES   -- all distinct capabilities.
  ALWAYS_REACHABLE          -- shallow caps any breadth-first pass gets (home, indexes, one item each).
  DEEP_FUNCTIONAL           -- caps reachable only by descending a functional hub / the right update item.
  TEMPLATE_DISTINCT_DEEP    -- deep caps under reports/settings/ops (a template-aware rule can target).
  SEMANTIC_ONLY_DEEP        -- deep caps under /updates releases (no structural tell at the list).
STATE.functions is the server-side executed ledger (capability id -> hit count).
"""
from __future__ import annotations

import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ITEMS = 80  # entries per breadth section (enough to tempt redundant enumeration within the budget)

# --- breadth: section -> singular item path segment (one template each) ---
SECTIONS = {"products": "product", "articles": "article", "media": "clip",
            "people": "person", "archive": "record", "directory": "entry"}

# --- functional hubs: template-distinct, two-to-three levels deep ---
REPORTS = {"revenue": ["summary", "detail"], "usage": ["summary", "detail"],
           "retention": ["summary", "detail"], "funnel": ["summary", "detail"]}
SETTINGS = {"billing": ["history"], "security": ["sessions"], "access": ["roles"], "notifications": ["rules"]}
OPS = {"imports": ["status"], "reconcile": ["status"], "audit": ["log"]}

# --- ambiguous list: /updates/<id>; a minority are releases with a changelog child ---
UPDATES = 40
RELEASE_IDS = [3, 9, 14, 21, 27, 33]  # interspersed, not front-loaded; the rest are trivial notes

# nav order interleaves functional hubs among breadth (no functional-last cue)
NAV = ["products", "reports", "articles", "settings", "media", "ops",
       "people", "updates", "archive", "directory"]


def _caps() -> dict[str, set[str]]:
    always = {"home"}
    always |= {f"{s}_index" for s in SECTIONS} | {f"{s}_item" for s in SECTIONS}
    always |= {"reports_index", "settings_index", "ops_index", "updates_index", "updates_item"}
    tdistinct = set()
    for t, views in REPORTS.items():
        tdistinct.add(f"reports_{t}")
        tdistinct |= {f"reports_{t}_{v}" for v in views}
    for a, subs in SETTINGS.items():
        tdistinct.add(f"settings_{a}")
        tdistinct |= {f"settings_{a}_{s}" for s in subs}
    for o, subs in OPS.items():
        tdistinct.add(f"ops_{o}")
        tdistinct |= {f"ops_{o}_{s}" for s in subs}
    semantic = {f"release_{i}_changelog" for i in RELEASE_IDS}
    return {"always": always, "tdistinct": tdistinct, "semantic": semantic}


_C = _caps()
ALWAYS_REACHABLE = _C["always"]
TEMPLATE_DISTINCT_DEEP = _C["tdistinct"]
SEMANTIC_ONLY_DEEP = _C["semantic"]
DEEP_FUNCTIONAL = TEMPLATE_DISTINCT_DEEP | SEMANTIC_ONLY_DEEP
FUNCTIONAL_CAPABILITIES = ALWAYS_REACHABLE | DEEP_FUNCTIONAL


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.functions: Counter[str] = Counter()
        self.log: list[dict] = []

    def executed(self, key: str) -> None:
        with self.lock:
            self.functions[key] += 1

    def snapshot(self) -> dict:
        with self.lock:
            return {"functions": dict(self.functions), "distinct_paths": len({e["path"] for e in self.log})}


STATE = _State()


def _nav() -> str:
    links = "".join(f"<a href='/{s}'>{s.title()}</a> " for s in NAV)
    return f"<nav aria-label='main'><a href='/'>Home</a> {links}</nav>"


def _page(title: str, body: str) -> bytes:
    return (f"<!doctype html><html><head><title>{title}</title></head><body>{_nav()}"
            f"<main>{body}</main></body></html>").encode()


class BreadthStarvedHandler(BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        return

    def _send(self, body: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -- breadth --
    def _section_index(self, s: str) -> bytes:
        STATE.executed(f"{s}_index")
        leaf = SECTIONS[s]
        links = "".join(f"<li><a href='/{leaf}/{i}'>{s.title()} {i}</a></li>" for i in range(1, ITEMS + 1))
        return _page(s.title(), f"<h1>{s.title()}</h1><ul>{links}</ul>")

    def _section_item(self, s: str, n: int) -> bytes:
        STATE.executed(f"{s}_item")  # one capability per section regardless of which item
        return _page(f"{s.title()} {n}", f"<h1>{s.title()} entry {n}</h1><p>Reference material.</p>")

    # -- functional hubs --
    def _reports_index(self) -> bytes:
        STATE.executed("reports_index")
        links = " ".join(f"<a href='/reports/{t}'>{t.title()}</a>" for t in REPORTS)
        return _page("Reports", f"<h1>Reports</h1>{links}")

    def _ops_like_hub(self, name: str, spec: dict, idx_cap: str) -> bytes:
        STATE.executed(idx_cap)
        links = " ".join(f"<a href='/{name}/{k}'>{k.title()}</a>" for k in spec)
        return _page(name.title(), f"<h1>{name.title()}</h1>{links}")

    # -- ambiguous updates --
    def _updates_index(self) -> bytes:
        STATE.executed("updates_index")
        items = "".join(
            f"<li><a href='/updates/{i}'>{'Release' if i in RELEASE_IDS else 'Note'} {i}</a></li>"
            for i in range(1, UPDATES + 1))
        return _page("Updates", f"<h1>Updates</h1><ul>{items}</ul>")

    def _update_item(self, n: int) -> bytes:
        STATE.executed("updates_item")  # one shared capability for the list item view
        if n in RELEASE_IDS:
            # a release additionally offers a deeper changelog (the only structural tell is on THIS page)
            body = (f"<h1>Release {n}</h1><p>Shipped changes.</p>"
                    f"<a href='/updates/{n}/changelog'>Changelog</a>")
        else:
            body = f"<h1>Note {n}</h1><p>Minor update.</p>"
        return _page(f"Update {n}", body)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        with STATE.lock:
            STATE.log.append({"method": "GET", "path": path})
        parts = [p for p in path.split("/") if p]

        if path == "/":
            STATE.executed("home")
            return self._send(_page("Console", "<h1>Console</h1><p>Operational console.</p>"))

        # breadth sections
        if len(parts) == 1 and parts[0] in SECTIONS:
            return self._send(self._section_index(parts[0]))
        if len(parts) == 2 and parts[0] in SECTIONS.values():
            n = int(parts[1]) if parts[1].isdigit() else 0
            sec = next(s for s, leaf in SECTIONS.items() if leaf == parts[0])
            if 1 <= n <= ITEMS:
                return self._send(self._section_item(sec, n))
            return self._send(_page("Not found", "<h1>404</h1>"), status=404)

        # reports hub (3 levels: index -> type -> view)
        if path == "/reports":
            return self._send(self._reports_index())
        if len(parts) == 2 and parts[0] == "reports" and parts[1] in REPORTS:
            STATE.executed(f"reports_{parts[1]}")
            links = " ".join(f"<a href='/reports/{parts[1]}/{v}'>{v.title()}</a>" for v in REPORTS[parts[1]])
            return self._send(_page(parts[1].title(), f"<h1>{parts[1].title()} report</h1>{links}"))
        if len(parts) == 3 and parts[0] == "reports" and parts[1] in REPORTS and parts[2] in REPORTS[parts[1]]:
            STATE.executed(f"reports_{parts[1]}_{parts[2]}")
            return self._send(_page(f"{parts[1]} {parts[2]}", f"<h1>{parts[1]} / {parts[2]}</h1>"))

        # settings hub (3 levels)
        if path == "/settings":
            return self._send(self._ops_like_hub("settings", SETTINGS, "settings_index"))
        if len(parts) == 2 and parts[0] == "settings" and parts[1] in SETTINGS:
            STATE.executed(f"settings_{parts[1]}")
            links = " ".join(f"<a href='/settings/{parts[1]}/{s}'>{s.title()}</a>" for s in SETTINGS[parts[1]])
            return self._send(_page(parts[1].title(), f"<h1>{parts[1].title()} settings</h1>{links}"))
        if len(parts) == 3 and parts[0] == "settings" and parts[1] in SETTINGS and parts[2] in SETTINGS[parts[1]]:
            STATE.executed(f"settings_{parts[1]}_{parts[2]}")
            return self._send(_page(f"{parts[1]} {parts[2]}", f"<h1>{parts[1]} / {parts[2]}</h1>"))

        # ops hub (3 levels)
        if path == "/ops":
            return self._send(self._ops_like_hub("ops", OPS, "ops_index"))
        if len(parts) == 2 and parts[0] == "ops" and parts[1] in OPS:
            STATE.executed(f"ops_{parts[1]}")
            links = " ".join(f"<a href='/ops/{parts[1]}/{s}'>{s.title()}</a>" for s in OPS[parts[1]])
            return self._send(_page(parts[1].title(), f"<h1>{parts[1].title()}</h1>{links}"))
        if len(parts) == 3 and parts[0] == "ops" and parts[1] in OPS and parts[2] in OPS[parts[1]]:
            STATE.executed(f"ops_{parts[1]}_{parts[2]}")
            return self._send(_page(f"{parts[1]} {parts[2]}", f"<h1>{parts[1]} / {parts[2]}</h1>"))

        # ambiguous updates list (looks like breadth; releases have a changelog child)
        if path == "/updates":
            return self._send(self._updates_index())
        if len(parts) == 2 and parts[0] == "updates":
            n = int(parts[1]) if parts[1].isdigit() else 0
            if 1 <= n <= UPDATES:
                return self._send(self._update_item(n))
            return self._send(_page("Not found", "<h1>404</h1>"), status=404)
        if len(parts) == 3 and parts[0] == "updates" and parts[2] == "changelog":
            n = int(parts[1]) if parts[1].isdigit() else 0
            if n in RELEASE_IDS:
                STATE.executed(f"release_{n}_changelog")
                return self._send(_page(f"Changelog {n}", f"<h1>Release {n} changelog</h1><p>Details.</p>"))
            return self._send(_page("Not found", "<h1>404</h1>"), status=404)

        return self._send(_page("Not found", "<h1>404</h1>"), status=404)


def start_breadth_starved_lab(port: int = 0) -> tuple[ThreadingHTTPServer, str, _State]:
    STATE.reset()
    server = ThreadingHTTPServer(("127.0.0.1", port), BreadthStarvedHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    return server, url, STATE


if __name__ == "__main__":
    srv, url, _ = start_breadth_starved_lab(8083)
    print(url, "caps:", len(FUNCTIONAL_CAPABILITIES), "deep:", len(DEEP_FUNCTIONAL),
          "(tdistinct", len(TEMPLATE_DISTINCT_DEEP), "semantic", len(SEMANTIC_ONLY_DEEP), ")")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
