"""Held-out variants of the Stage-0 breadth-starved fixture (development only; stdlib; GET-only; no
writes, auth, JS, or destructive routes).

Stage 1 of the LLM-augmentation study compares exploration *scheduling* policies. To avoid an arm tuning
to the Stage-0 instance, the comparison runs on two variants built here that preserve the Stage-0 WORKLOAD
(breadth lists that compete for budget, functional hubs two-to-three levels deep, and one structurally
ambiguous list whose releases carry a deeper changelog) while changing everything an explorer could
latch onto: section names, the three hubs' names and ARITY/DEPTH, the ambiguous list's name, the release
positions, and the nav interleave order. No label hints ("important"/"duplicate"/"workflow"), no hardcoded
route order rewarded, fully deterministic. Ground truth is evaluation-only and never exposed to the
explorer; capabilities are recorded exactly as in Stage 0 (one capability per breadth section regardless
of item count; one shared item capability for the ambiguous list; a deeper changelog only for releases).

Each variant is a frozen :class:`Spec`; :func:`start_variant` returns ``(server, url, state, truth)`` where
``truth`` carries the capability inventory and the three evaluation classes.
"""
from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Spec:
    """A breadth-starved application shape. ``hubs`` maps a hub path -> {child -> [grandchild, ...]};
    a hub with grandchildren is 3 levels deep, one without is 2. ``sections`` maps a listing path -> its
    singular item segment. ``ambiguous`` is the one-template list whose ``release_ids`` carry a changelog."""
    name: str
    items: int
    sections: dict[str, str]
    hubs: dict[str, dict[str, list[str]]]
    ambiguous: str
    ambiguous_items: int
    release_ids: tuple[int, ...]
    nav: tuple[str, ...]


@dataclass
class Truth:
    inventory: set[str]
    always_reachable: set[str]
    template_distinct_deep: set[str]
    semantic_only_deep: set[str]
    deep_functional: set[str] = field(default_factory=set)


def _truth(spec: Spec) -> Truth:
    always = {"home"}
    always |= {f"{s}_index" for s in spec.sections} | {f"{s}_item" for s in spec.sections}
    always |= {f"{h}_index" for h in spec.hubs}
    always |= {f"{spec.ambiguous}_index", f"{spec.ambiguous}_item"}
    tdistinct: set[str] = set()
    for h, children in spec.hubs.items():
        for child, grandkids in children.items():
            tdistinct.add(f"{h}_{child}")
            tdistinct |= {f"{h}_{child}_{g}" for g in grandkids}
    semantic = {f"{spec.ambiguous}_release_{i}_changelog" for i in spec.release_ids}
    deep = tdistinct | semantic
    return Truth(inventory=always | deep, always_reachable=always,
                 template_distinct_deep=tdistinct, semantic_only_deep=semantic, deep_functional=deep)


# --- two held-out variants: different names, hub arity, hub depth mix, release positions, nav order ---

VARIANT_A = Spec(
    name="atlas",
    items=80,
    sections={"regions": "region", "routes": "route", "vessels": "vessel",
              "berths": "berth", "cargo": "lot", "crews": "crew"},
    # three functional hubs; mixed depth; arity differs from Stage 0 (3x2 / 4x1 / 2x1)
    hubs={
        "ledgers": {"freight": ["monthly", "annual"], "fuel": ["monthly", "annual"],
                    "tariff": ["monthly", "annual"]},                 # 3 types x 2 views (3-level)
        "controls": {"berthing": ["windows"], "pilots": ["roster"],
                     "customs": ["rules"], "signals": ["bands"]},     # 4 areas x 1 sub (3-level)
        "pipelines": {"ingest": ["status"], "settle": ["status"]},    # 2 areas x 1 sub (3-level)
    },
    ambiguous="bulletins",
    ambiguous_items=36,
    release_ids=(4, 11, 19, 25, 31),
    nav=("regions", "ledgers", "routes", "controls", "vessels",
         "pipelines", "berths", "bulletins", "cargo", "crews"),
)

VARIANT_B = Spec(
    name="orchard",
    items=72,
    sections={"orchards": "orchard", "lots": "lot", "trees": "tree",
              "crates": "crate", "shipments": "shipment", "buyers": "buyer"},
    # different hub names, arity, and depth mix again (4x2 / 2x2 / 3x1)
    hubs={
        "yields": {"harvest": ["weekly", "seasonal"], "grade": ["weekly", "seasonal"],
                   "loss": ["weekly", "seasonal"], "price": ["weekly", "seasonal"]},  # 4x2 (3-level)
        "policies": {"irrigation": ["schedule", "audit"], "labor": ["schedule", "audit"]},  # 2x2 (3-level)
        "jobs": {"sort": ["status"], "pack": ["status"], "dispatch": ["status"]},     # 3x1 (3-level)
    },
    ambiguous="releases",
    ambiguous_items=44,
    release_ids=(6, 13, 17, 28, 35, 41),
    nav=("orchards", "yields", "lots", "policies", "trees",
         "jobs", "crates", "releases", "shipments", "buyers"),
)

VARIANTS = {"atlas": VARIANT_A, "orchard": VARIANT_B}


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
            return {"functions": dict(self.functions),
                    "distinct_paths": len({e["path"] for e in self.log}),
                    "log_paths": [e["path"] for e in self.log]}  # arrival-ordered (for request-AUC)


def _handler(spec: Spec, state: _State):
    leaf_to_section = {leaf: sec for sec, leaf in spec.sections.items()}

    def nav_html() -> str:
        links = "".join(f"<a href='/{s}'>{s.title()}</a> " for s in spec.nav)
        return f"<nav aria-label='main'><a href='/'>Home</a> {links}</nav>"

    def page(title: str, body: str) -> bytes:
        return (f"<!doctype html><html><head><title>{title}</title></head><body>{nav_html()}"
                f"<main>{body}</main></body></html>").encode()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            return

        def _send(self, body: bytes, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _404(self) -> None:
            self._send(page("Not found", "<h1>404</h1>"), status=404)

        def do_GET(self) -> None:  # noqa: N802
            path = urlsplit(self.path).path
            with state.lock:
                state.log.append({"method": "GET", "path": path})
            parts = [p for p in path.split("/") if p]

            if path == "/":
                state.executed("home")
                return self._send(page("Console", "<h1>Console</h1><p>Operational console.</p>"))

            # breadth sections (index + one shared item capability)
            if len(parts) == 1 and parts[0] in spec.sections:
                s = parts[0]
                state.executed(f"{s}_index")
                leaf = spec.sections[s]
                links = "".join(f"<li><a href='/{leaf}/{i}'>{s.title()} {i}</a></li>"
                                for i in range(1, spec.items + 1))
                return self._send(page(s.title(), f"<h1>{s.title()}</h1><ul>{links}</ul>"))
            if len(parts) == 2 and parts[0] in leaf_to_section:
                n = int(parts[1]) if parts[1].isdigit() else 0
                if 1 <= n <= spec.items:
                    state.executed(f"{leaf_to_section[parts[0]]}_item")
                    return self._send(page(f"{parts[0].title()} {n}",
                                           f"<h1>{parts[0].title()} entry {n}</h1><p>Reference material.</p>"))
                return self._404()

            # functional hubs (index -> child -> optional grandchild; children are distinct templates)
            if len(parts) >= 1 and parts[0] in spec.hubs:
                hub = parts[0]
                children = spec.hubs[hub]
                if len(parts) == 1:
                    state.executed(f"{hub}_index")
                    links = " ".join(f"<a href='/{hub}/{c}'>{c.title()}</a>" for c in children)
                    return self._send(page(hub.title(), f"<h1>{hub.title()}</h1>{links}"))
                if len(parts) == 2 and parts[1] in children:
                    c = parts[1]
                    state.executed(f"{hub}_{c}")
                    links = " ".join(f"<a href='/{hub}/{c}/{g}'>{g.title()}</a>" for g in children[c])
                    return self._send(page(c.title(), f"<h1>{c.title()}</h1>{links}"))
                if len(parts) == 3 and parts[1] in children and parts[2] in children[parts[1]]:
                    state.executed(f"{hub}_{parts[1]}_{parts[2]}")
                    return self._send(page(f"{parts[1]} {parts[2]}", f"<h1>{parts[1]} / {parts[2]}</h1>"))
                return self._404()

            # ambiguous list (one template; releases additionally expose a changelog child)
            amb = spec.ambiguous
            if parts[0] == amb:
                if len(parts) == 1:
                    state.executed(f"{amb}_index")
                    items = "".join(
                        f"<li><a href='/{amb}/{i}'>{'Release' if i in spec.release_ids else 'Note'} {i}</a></li>"
                        for i in range(1, spec.ambiguous_items + 1))
                    return self._send(page(amb.title(), f"<h1>{amb.title()}</h1><ul>{items}</ul>"))
                if len(parts) == 2:
                    n = int(parts[1]) if parts[1].isdigit() else 0
                    if 1 <= n <= spec.ambiguous_items:
                        state.executed(f"{amb}_item")
                        if n in spec.release_ids:
                            body = (f"<h1>Release {n}</h1><p>Shipped changes.</p>"
                                    f"<a href='/{amb}/{n}/changelog'>Changelog</a>")
                        else:
                            body = f"<h1>Note {n}</h1><p>Minor update.</p>"
                        return self._send(page(f"{amb.title()} {n}", body))
                    return self._404()
                if len(parts) == 3 and parts[2] == "changelog":
                    n = int(parts[1]) if parts[1].isdigit() else 0
                    if n in spec.release_ids:
                        state.executed(f"{amb}_release_{n}_changelog")
                        return self._send(page(f"Changelog {n}",
                                               f"<h1>Release {n} changelog</h1><p>Details.</p>"))
                    return self._404()
            return self._404()

    return Handler


def start_variant(name: str, port: int = 0) -> tuple[ThreadingHTTPServer, str, _State, Truth]:
    spec = VARIANTS[name]
    state = _State()
    server = ThreadingHTTPServer(("127.0.0.1", port), _handler(spec, state))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    return server, url, state, _truth(spec)


if __name__ == "__main__":
    for nm, sp in VARIANTS.items():
        t = _truth(sp)
        print(f"{nm}: inventory={len(t.inventory)} always={len(t.always_reachable)} "
              f"tdistinct={len(t.template_distinct_deep)} semantic={len(t.semantic_only_deep)} "
              f"deep={len(t.deep_functional)}")
