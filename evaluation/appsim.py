"""Deterministic abstract-application simulator (Phase 1b; evaluation side only).

EXPLORATION_PLANNER_DESIGN.md §10.2. Four layers, kept apart on purpose:

1. Hidden truth (`AppSpec`): pages, controls, capabilities, entities and
   prerequisite flags, generated from (architecture, seed). Never given to an
   agent.
2. World (`_World`): the hidden application state. It renders only what a
   browser agent would capture: `acg-evidence/1` observation, action and replay
   records (URLs, structural affordances, requests, storage keys, region
   digests, disabled flags).
3. Adapter (`SimAdapter`): the only object an agent touches. It executes plans
   step by step, charges declared action costs, applies the shared risk gate and
   returns evidence records.
4. Evaluation (`Oracle`): reads the hidden truth to score runs. Only
   `evaluation/sim_eval.py` uses it.

Labels are random display strings; identity never depends on them.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from agent1.model.evidence import AffordanceEvidence, Capture, FieldShape, Record, RequestEvidence, Source
from agent1.planner.gate import RiskGate
from agent1.planner.interfaces import Costs, ExperimentPlan, ExperimentResult, Isolation, Step

SIM_VERSION = "appsim/1"
ORIGIN = "http://app.sim"
ALL = frozenset({"anonymous", "member"})
ARCHITECTURES = ("crud", "large_list", "workflow", "client_only", "duplicate_pages", "state_variants", "roles",
                 "hidden_ids", "flat", "flaky")


def _h(*parts: Any) -> float:
    """Deterministic uniform [0, 1) from any parts."""
    return int(hashlib.sha256(repr(parts).encode()).hexdigest()[:12], 16) / 16 ** 12


# ----------------------------------------------------------------------------- 1. hidden truth
@dataclass
class Control:
    key: str
    page: str
    cap: str
    kind: str = "button"                  # link | button | form_submit
    component: str = "main"
    locator: str = ""
    label: str = ""
    target: str | None = None             # page key navigated to
    op: tuple | None = None               # (method, path with {id}, params, encoding, resource_type)
    effect: str = "fetch"                 # navigate|fetch|toggle|storage|region|none|create|update|search
    fields: tuple = ()                    # ((name, input_type, required), ...)
    requires: str | None = None           # flag needed ("role:member" or a session flag)
    gate: str = "disabled"                # how an unmet requirement shows: disabled | fail
    sets: str | None = None               # session flag set on success
    opens: str | None = None              # component toggled
    in_component: str | None = None       # rendered only while this component is open
    dangerous: bool = False
    roles: frozenset = ALL
    per_instance: str | None = None       # entity key: one rendered control per instance
    hidden_id: bool = False               # per-instance control whose URL carries no identifier
    variant: tuple | None = None          # (cap, op, effect) used on odd-numbered instances


@dataclass
class Page:
    key: str
    route: str
    area: str
    entity: str | None = None
    roles: frozenset = ALL
    title: str = ""
    regions: bool = False
    results_of: str | None = None         # search results page listing this entity


@dataclass
class Entity:
    key: str
    ids: list[str]
    large: bool = False


@dataclass
class CapTruth:
    id: str
    area: str
    cls: str
    gated: bool = False
    observable: bool = True
    writes: bool = False


@dataclass
class AppSpec:
    arch: str
    seed: int
    pages: dict[str, Page] = field(default_factory=dict)
    controls: list[Control] = field(default_factory=list)
    entities: dict[str, Entity] = field(default_factory=dict)
    caps: dict[str, CapTruth] = field(default_factory=dict)
    isolation: Isolation = field(default_factory=Isolation)
    costs: Costs = field(default_factory=Costs)
    flaky: float = 0.0
    capture: Capture = field(default_factory=lambda: Capture(websocket=False, visual_regions=False))
    snapshot_drift: bool = False
    root: str = "root"
    row_style: str = "latin"              # display text of list rows (relabel changes it)

    def summary(self) -> dict[str, Any]:
        obs = [c for c in self.caps.values() if c.observable]
        return {"arch": self.arch, "seed": self.seed, "pages": len(self.pages), "controls": len(self.controls),
                "capabilities": len(self.caps), "observable_capabilities": len(obs),
                "gated": sum(c.gated for c in obs), "instances": {k: len(e.ids) for k, e in self.entities.items()}}


class _Builder:
    def __init__(self, arch: str, seed: int) -> None:
        self.rng = random.Random(f"{SIM_VERSION}:{arch}:{seed}")
        self.spec = AppSpec(arch=arch, seed=seed)
        self.words: set[str] = set()
        self.slots: dict[tuple[str, str, str], int] = {}
        self.nav_caps: dict[str, str] = {}
        self.global_nav = False
        self.page("root", "/", "root")

    def word(self) -> str:
        while True:
            w = "".join(self.rng.choice("bdfgklmnprstvz") + self.rng.choice("aeiou") for _ in range(self.rng.randint(2, 3)))
            if w not in self.words:
                self.words.add(w)
                return w

    def label(self) -> str:
        return " ".join(self.word().capitalize() for _ in range(self.rng.randint(1, 2)))

    def page(self, key: str, route: str, area: str, **kw: Any) -> Page:
        p = Page(key=key, route=route, area=area, title=self.label(), **kw)
        self.spec.pages[key] = p
        return p

    def cap(self, area: str, cls: str, **kw: Any) -> str:
        cid = f"c{len(self.spec.caps) + 1}:{cls}"
        self.spec.caps[cid] = CapTruth(id=cid, area=area, cls=cls, **kw)
        return cid

    def control(self, page: str, cap: str, kind: str = "button", component: str = "main", **kw: Any) -> Control:
        tag = {"link": "a", "button": "button", "form_submit": "form"}[kind]
        slot = (page, component, tag)
        self.slots[slot] = self.slots.get(slot, 0) + 1
        locator = f"{component}>li>{tag}" if kw.get("per_instance") else f"{component}>{tag}:nth-of-type({self.slots[slot]})"
        c = Control(key=f"k{len(self.spec.controls) + 1}", page=page, cap=cap, kind=kind, component=component,
                    locator=locator, label=self.label(), **kw)
        self.spec.controls.append(c)
        return c

    def entity(self, n: int, style: str = "int", large: bool = False) -> str:
        key = f"E{len(self.spec.entities) + 1}"
        if style == "hex":
            ids = ["%024x" % self.rng.getrandbits(96) for _ in range(n)]
            ids = [i if any(ch.isdigit() for ch in i) else "1" + i[1:] for i in ids]
        else:
            ids = [str(i) for i in sorted(self.rng.sample(range(1000, 99999), n))]
        self.spec.entities[key] = Entity(key=key, ids=ids, large=large)
        return key

    def hub(self, area: str, roles: frozenset = ALL) -> tuple[str, str]:
        """An area entry page, linked from the root (and from every page if global nav is on)."""
        w = self.word()
        key = f"hub_{area}"
        self.page(key, f"/{w}", area, roles=roles)
        self.nav_caps[key] = self.cap(area, "navigation")
        self.control("root", self.nav_caps[key], "link", "nav", target=key, op=None, effect="navigate", roles=roles)
        return key, w

    def finish(self) -> AppSpec:
        if self.global_nav:
            for pkey in list(self.spec.pages):
                if pkey == "root":
                    continue
                for hub, cap in self.nav_caps.items():
                    self.control(pkey, cap, "link", "header", target=hub, effect="navigate",
                                 roles=self.spec.pages[hub].roles)
                self.control(pkey, self.nav_caps.setdefault("root", self.cap("root", "navigation")), "link", "header",
                             target="root", effect="navigate")
        return self.spec


# --------------------------------------------------------------- architecture building blocks
def _collection(b: _Builder, area: str, n: int, *, style: str = "int", large: bool = False, create: bool = False,
                edit: bool = False, search: bool = False, hidden: bool = False, variants: bool = False,
                detail_controls: int = 2) -> str:
    hub, w = b.hub(area)
    ent = b.entity(n, style, large)
    if hidden:
        detail = b.page(f"detail_{area}", f"/{w}/{b.word()}", area, entity=ent).key
        view = b.cap(area, "instance_view")
        b.control(hub, view, "button", "main>ul", per_instance=ent, hidden_id=True, target=detail, effect="navigate",
                  op=("GET", f"/api/{w}/item", (), None, "fetch"))
    else:
        detail = b.page(f"detail_{area}", f"/{w}/{{id}}", area, entity=ent).key
        view = b.cap(area, "instance_view")
        b.control(hub, view, "link", "main>ul", per_instance=ent, target=detail, effect="navigate")
    b.control(detail, b.nav_caps[hub], "link", "header", target=hub, effect="navigate")
    for i in range(detail_controls):
        if i % 2 == 0:
            b.control(detail, b.cap(area, "fetch"), "button", "main",
                      op=("GET", f"/api/{w}/{{id}}/{b.word()}", (), None, "fetch"), effect="fetch")
        else:
            dlg = f"dialog{len(b.spec.controls)}"
            b.control(detail, b.cap(area, "client_view_change"), "button", "main", opens=dlg, effect="toggle")
            b.control(detail, b.cap(area, "fetch"), "button", dlg, in_component=dlg,
                      op=("GET", f"/api/{w}/{{id}}/{b.word()}", (), None, "fetch"), effect="fetch")
    if variants:
        v1, v2 = b.cap(area, "fetch"), b.cap(area, "update", writes=True)
        b.control(detail, v1, "button", "aside", op=("GET", f"/api/{w}/{{id}}/{b.word()}", (), None, "fetch"),
                  effect="fetch", variant=(v2, ("POST", f"/api/{w}/{{id}}/{b.word()}", ("state",), "json", "xhr"),
                                           "fetch"))
    if create:
        b.control(hub, b.cap(area, "instance_creation", writes=True), "form_submit", "main>section",
                  op=("POST", f"/{w}/{b.word()}", ("name",), "form", "document"), effect="create",
                  fields=(("name", "text", True),), target=detail)
    if edit and not hidden:
        e = b.word()
        edit_page = b.page(f"edit_{area}", f"/{w}/{{id}}/{e}", area, entity=ent).key
        b.control(detail, b.cap(area, "navigation"), "link", "main", target=edit_page, effect="navigate")
        b.control(edit_page, b.cap(area, "instance_modification", writes=True), "form_submit", "main",
                  op=("POST", f"/{w}/{{id}}/{e}", ("name",), "form", "document"), effect="update",
                  fields=(("name", "text", True),), target=detail)
    if search:
        s = b.word()
        results = b.page(f"results_{area}", f"/{w}/{s}", area, results_of=ent).key
        b.control(hub, b.cap(area, "collection_query"), "form_submit", "header>form", effect="search",
                  op=("GET", f"/{w}/{s}", ("q",), None, "document"), fields=(("q", "search", False),), target=results)
        b.control(results, view, "link", "main>ul", per_instance=ent, target=detail, effect="navigate")
    return hub


def _static(b: _Builder, area: str, pages: int, controls: int, *, roles: frozenset = ALL) -> str:
    hub, w = b.hub(area, roles)
    kinds = ("fetch", "toggle", "storage", "fetch")
    for p in range(pages):
        key = f"{area}_p{p}"
        b.page(key, f"/{w}/{b.word()}", area, roles=roles)
        b.control(hub, b.cap(area, "navigation"), "link", "main", target=key, effect="navigate", roles=roles)
        for i in range(controls):
            _distinct_control(b, key, area, kinds[(p + i) % len(kinds)], w, roles)
    return hub


def _distinct_control(b: _Builder, page: str, area: str, kind: str, w: str, roles: frozenset = ALL) -> None:
    if kind == "fetch":
        b.control(page, b.cap(area, "fetch"), "button", "main", op=("GET", f"/api/{w}/{b.word()}", (), None, "fetch"),
                  effect="fetch", roles=roles)
    elif kind == "storage":
        b.control(page, b.cap(area, "client_view_change"), "button", "aside", effect="storage", roles=roles)
    elif kind == "region":
        b.control(page, b.cap(area, "client_view_change"), "button", "main>canvas", effect="region", roles=roles)
    elif kind == "none":
        b.control(page, b.cap(area, "unobservable", observable=False), "button", "main>canvas", effect="none",
                  roles=roles)
    else:
        dlg = f"dialog{len(b.spec.controls)}"
        b.control(page, b.cap(area, "client_view_change"), "button", "main", opens=dlg, effect="toggle", roles=roles)
        b.control(page, b.cap(area, "fetch"), "button", dlg, in_component=dlg, roles=roles,
                  op=("GET", f"/api/{w}/{b.word()}", (), None, "fetch"), effect="fetch")


def _chain(b: _Builder, area: str, *, cross_page: bool, steps: int = 3, decoy: bool = False) -> str:
    """A capability behind a chain of `steps` prerequisite actions, each control
    disabled until the previous one has run in this session."""
    hub, w = b.hub(area)
    page = hub
    if cross_page:
        page = b.page(f"{area}_w", f"/{w}/{b.word()}", area).key
        b.control(hub, b.cap(area, "navigation"), "link", "main", target=page, effect="navigate")
    for i in range(steps + 1):
        on = hub if (cross_page and i == 0) else page
        need = f"{area}:s{i}" if i else None
        kind = ("toggle_enable", "fetch", "post")[int(_h(b.spec.seed, area, i) * 3)] if i < steps else "final"
        sets = f"{area}:s{i + 1}" if i < steps else None
        cap = b.cap(area, "step" if i < steps else "gated_capability", gated=i > 0, writes=kind == "post")
        comp = "main>section" if not cross_page or i else "main"
        if kind == "toggle_enable":
            b.control(on, cap, "button", comp, effect="enable", requires=need, sets=sets)
        elif kind == "post":
            b.control(on, cap, "button", comp, effect="fetch", requires=need, sets=sets,
                      op=("POST", f"/api/{w}/{b.word()}", ("step",), "json", "xhr"))
        else:
            b.control(on, cap, "button", comp, effect="fetch", requires=need, sets=sets,
                      op=("GET", f"/api/{w}/{b.word()}", (), None, "fetch"))
    if decoy:
        b.control(page, b.cap(area, "never_enabled", gated=True, observable=False), "button", "main>section",
                  effect="fetch", requires=f"{area}:never", op=("GET", f"/api/{w}/{b.word()}", (), None, "fetch"))
    return hub


def _deep(b: _Builder, area: str, depth: int) -> str:
    """A path of `depth` pages, each with one distinct control; long restoration paths."""
    hub, w = b.hub(area)
    prev = hub
    for i in range(depth):
        key = f"{area}_l{i}"
        b.page(key, f"/{w}/{b.word()}", area)
        b.control(prev, b.cap(area, "navigation"), "link", "main", target=key, effect="navigate")
        _distinct_control(b, key, area, ("fetch", "storage")[i % 2], w)
        prev = key
    return hub


def _duplicates(b: _Builder, area: str, n: int) -> str:
    hub, w = b.hub(area)
    nav, fetch = b.cap(area, "navigation"), b.cap(area, "fetch")
    for i in range(n):
        key = f"{area}_d{i}"
        b.page(key, f"/{w}/{b.word()}", area)
        b.control(hub, nav, "link", "main>ul", target=key, effect="navigate")
        b.control(key, fetch, "button", "main", op=("GET", f"/api/{w}/feed", (), None, "fetch"), effect="fetch")
    return hub


def _client_only(b: _Builder, area: str, page: str = "root") -> None:
    b.spec.capture = Capture(websocket=False, visual_regions=True)
    b.spec.pages[page].regions = True
    for kind in ("toggle", "storage", "region", "region", "toggle", "none", "none", "storage"):
        if kind == "toggle":
            dlg = f"dialog{len(b.spec.controls)}"
            b.control(page, b.cap(area, "client_view_change"), "button", "main", opens=dlg, effect="toggle")
            b.control(page, b.cap(area, "client_view_change"), "button", dlg, in_component=dlg, effect="storage")
        else:
            _distinct_control(b, page, area, kind, "x")


def build(arch: str, seed: int, **kw: Any) -> AppSpec:
    """Generate one application. `kw` overrides scenario sizes (scenarios are frozen in sim_scenarios.py)."""
    b = _Builder(arch, seed)
    r = b.rng
    iso = Isolation(level=2, exploratory_writes=True, snapshot=False, roles=["anonymous"], start_url="/")
    if arch == "crud":
        b.global_nav = True
        _collection(b, "a1", r.randint(5, 10), create=True, edit=True, search=True)
        _static(b, "a2", 2, 3)
    elif arch == "large_list":
        _collection(b, "a1", kw.get("instances", r.randint(120, 200)), large=True, detail_controls=2)
        _static(b, "a2", kw.get("other_pages", 2), kw.get("other_controls", 3))
    elif arch == "workflow":
        for i in range(kw.get("chains", 2)):
            _chain(b, f"w{i + 1}", cross_page=bool(i % 2), decoy=kw.get("decoys", False))
        for i in range(kw.get("distractor_areas", 2)):
            _static(b, f"a{i + 1}", kw.get("distractor_pages", 2), kw.get("distractor_controls", 3))
        for i in range(kw.get("deep_areas", 0)):
            _deep(b, f"d{i + 1}", kw.get("depth", 6))
        if kw.get("collection", 0):
            _collection(b, "c1", kw["collection"], large=True)
    elif arch == "client_only":
        _client_only(b, "root")
    elif arch == "duplicate_pages":
        _duplicates(b, "a1", kw.get("duplicates", r.randint(15, 30)))
        _static(b, "a2", 2, 3)
    elif arch == "state_variants":
        _collection(b, "a1", r.randint(6, 12), variants=True)
        _static(b, "a2", 2, 3)
    elif arch == "roles":
        b.global_nav = True
        iso = Isolation(level=2, exploratory_writes=True, roles=["anonymous", "member"], start_url="/")
        _static(b, "a1", 2, 3)
        _static(b, "m1", 2, 3, roles=frozenset({"member"}))
        gated = b.cap("a1", "fetch", gated=True)
        b.control("hub_a1", gated, "button", "aside", requires="role:member", gate="fail",
                  op=("GET", "/api/account/data", (), None, "fetch"), effect="fetch")
        b.control("root", b.cap("root", "session_end", observable=False), "button", "header", dangerous=True,
                  effect="none", roles=frozenset({"member"}))
    elif arch == "hidden_ids":
        _collection(b, "a1", r.randint(30, 80), hidden=True)
        _static(b, "a2", 2, 3)
    elif arch == "flat":
        for p in range(kw.get("pages", 12)):
            key = f"f{p}"
            b.page(key, f"/{b.word()}", key)
            b.control("root", b.cap(key, "navigation"), "link", "nav", target=key, effect="navigate")
            for i in range(kw.get("controls", 5)):
                _distinct_control(b, key, key, ("fetch", "storage", "toggle", "fetch", "region")[(i + p) % 5], key)
        b.spec.capture = Capture(websocket=False, visual_regions=True)
        for p in b.spec.pages.values():
            p.regions = True
    elif arch == "flaky":
        b.global_nav = True
        _collection(b, "a1", r.randint(5, 10), create=True, search=True)
        _static(b, "a2", 2, 3)
        b.spec.flaky = kw.get("flaky", 0.2)
        iso = Isolation(level=3, exploratory_writes=True, snapshot=True, roles=["anonymous"], start_url="/")
    else:
        raise ValueError(arch)
    for key, value in kw.items():
        if key == "isolation":
            iso = value
        elif key == "flaky_rate":
            b.spec.flaky = value
        elif key == "snapshot_drift":
            b.spec.snapshot_drift = value
    b.spec.isolation = iso
    return b.finish()


def relabel(spec: AppSpec, mode: str) -> AppSpec:
    """Replace every display string (labels and titles) with random or zh-CN text (T3a)."""
    rng = random.Random(f"relabel:{mode}:{spec.arch}:{spec.seed}")
    zh = "数据设置项目页面用户列表详情保存删除搜索创建编辑提交登录分享"

    def text() -> str:
        if mode == "zh":
            return "".join(rng.choice(zh) for _ in range(rng.randint(2, 5)))
        return "".join(rng.choice("qwxyzjQWXYZJ0123456789") for _ in range(rng.randint(3, 12)))
    for c in spec.controls:
        c.label = text()
    for p in spec.pages.values():
        p.title = text()
    spec.row_style = mode
    return spec


# ------------------------------------------------------------------------------- 2. world
class _World:
    def __init__(self, spec: AppSpec) -> None:
        self.spec = spec
        self.instances = {k: list(e.ids) for k, e in spec.entities.items()}
        self.created = 0
        self.by_page: dict[str, list[Control]] = {}
        for c in spec.controls:
            self.by_page.setdefault(c.page, []).append(c)
        self.fresh(spec.isolation.default_role)

    def fresh(self, role: str) -> None:
        self.role, self.session, self.storage, self.open = role, set(), set(), set()
        self.region_state: dict[str, int] = {}
        self.page, self.inst, self.query = self.spec.root, None, None
        self.history: list[tuple[str, str | None, str | None]] = []

    def snapshot_restore(self, role: str) -> None:
        self.instances = {k: list(e.ids) for k, e in self.spec.entities.items()}
        self.fresh(role)

    # rendering ---------------------------------------------------------------------------
    def url(self, page: str | None = None, inst: str | None = None, query: str | None = None) -> str:
        p = self.spec.pages[page or self.page]
        path = p.route.replace("{id}", inst or self.inst or "0") if "{id}" in p.route else p.route
        q = query if page else self.query
        return ORIGIN + path + (f"?q={q}" if p.results_of and q else "")

    def met(self, c: Control) -> bool:
        if c.requires is None:
            return True
        if c.requires.startswith("role:"):
            return self.role == c.requires[5:]
        return c.requires in self.session

    def visible(self) -> list[tuple[Control, str | None]]:
        page = self.spec.pages[self.page]
        out: list[tuple[Control, str | None]] = []
        for c in self.by_page.get(self.page, []):
            if self.role not in c.roles or (c.in_component and c.in_component not in self.open):
                continue
            if c.per_instance:
                ids = self.instances[c.per_instance]
                if page.results_of:
                    ids = [i for i in ids if self.query and _h("match", self.query, i) < 0.3]
                out.extend((c, i) for i in ids)
            else:
                out.append((c, None))
        return out

    def render(self, c: Control, inst: str | None, index: int) -> AffordanceEvidence:
        target = None
        if c.target and not c.hidden_id and c.kind == "link":
            target = self.url(c.target, inst if c.per_instance else self.inst)
        elif c.kind == "form_submit" and c.op:
            target = ORIGIN + c.op[1].replace("{id}", self.inst or "0")
        locator = c.locator.replace(">li>", f">li:nth-of-type({index + 1})>") if c.per_instance else c.locator
        return AffordanceEvidence(
            kind=c.kind, component=c.component, locator=locator, target=target,
            method=(c.op[0] if c.op and c.kind == "form_submit" else None),
            fields=[FieldShape(name=n, input_type=t, required=q) for n, t, q in c.fields],
            safe=not c.dangerous, skip_reason="destructive_possible" if c.dangerous else None,
            disabled=(not self.met(c)) and c.gate == "disabled",
            label=c.label + (" " + _row_word(c.key, inst, self.spec.row_style) if c.per_instance and inst else ""))

    def affordances(self) -> list[tuple[AffordanceEvidence, Control, str | None]]:
        out, counters = [], {}
        for c, inst in self.visible():
            i = counters.get(c.key, 0)
            counters[c.key] = i + 1
            out.append((self.render(c, inst, i), c, inst))
        return out

    def page_allowed(self, page: str) -> bool:
        return self.role in self.spec.pages[page].roles


def _row_word(key: str, inst: str, style: str) -> str:
    """Per-row display text (record titles differ per row in real lists)."""
    x = int(hashlib.sha256(f"{style}:{key}:{inst}".encode()).hexdigest()[:8], 16)
    if style == "zh":
        return "".join("数据项目页面用户列表详情"[(x >> (4 * i)) % 12] for i in range(3))
    if style == "random":
        return "".join("qwxyzj0123456789"[(x >> (4 * i)) % 16] for i in range(6))
    return "".join("bdfgklmnprstvz"[(x >> (4 * i)) % 14] + "aeiou"[(x >> (4 * i + 2)) % 5] for i in range(3))


def _same(a: AffordanceEvidence, b: AffordanceEvidence) -> bool:
    return (a.kind, a.component, a.locator, a.target, a.method) == (b.kind, b.component, b.locator, b.target, b.method)


# ------------------------------------------------------------------------------ 3. adapter
class SimAdapter:
    """Executor for plans against a hidden world. Agents receive evidence only."""

    def __init__(self, spec: AppSpec) -> None:
        self.__world = _World(spec)
        self.__spec = spec
        self.isolation = spec.isolation
        self.costs = spec.costs
        self.__seq = 0
        self.__n = {"obs": 0, "act": 0, "rep": 0}
        self.__truth_actions: dict[str, str | None] = {}      # action/replay id -> capability (hidden)
        self.__truth_obs: dict[str, tuple[str, str | None]] = {}
        self.__plan_kind_of_obs: dict[str, str] = {}
        self.__clicks = 0
        self.__initial_root: list[tuple] | None = None
        self.__live: Record | None = None

    # evaluation access ------------------------------------------------------------------
    def oracle(self) -> "Oracle":
        return Oracle(self.__spec, self.__truth_actions, self.__truth_obs, self.__plan_kind_of_obs)

    # records ----------------------------------------------------------------------------
    def _rid(self, kind: str) -> tuple[str, str, int]:
        self.__n[kind] += 1
        self.__seq += 1
        n = self.__n[kind]
        return f"sim:{kind}:{n}", {"obs": "o", "act": "a", "rep": "r"}[kind] + str(n), self.__seq

    def _observe(self, context: str, plan_kind: str) -> Record:
        w = self.__world
        rid, oid, seq = self._rid("obs")
        affs = [a for a, _, _ in w.affordances()]
        page = self.__spec.pages[w.page]
        regions = None
        if self.__spec.capture.visual_regions:
            regions = {"canvas": hashlib.sha256(repr(sorted(w.region_state.items())).encode()).hexdigest()[:8]} \
                if page.regions else {}
        self.__truth_obs[oid] = (w.page, w.inst)
        self.__plan_kind_of_obs[oid] = plan_kind
        return Record(id=rid, seq=seq, kind="observation", source=Source(artifact="appsim", pointer=oid), obs_id=oid,
                      context=context, url=w.url(), role=w.role, storage_keys=sorted(w.storage), affordances=affs,
                      regions=regions, title=page.title)

    def start(self) -> list[Record]:
        self.__seq += 1
        manifest = Record(id="sim:manifest", seq=self.__seq, kind="capture_manifest",
                          source=Source(artifact="appsim", pointer="manifest"), capture=self.__spec.capture,
                          synthetic=True, application=f"sim-{self.__spec.arch}")
        first = self._observe("exploration", "start")
        self.__initial_root = sorted((a.kind, a.locator, a.target or "") for a in first.affordances or [])
        self.__live = first
        return [manifest, first]

    # execution --------------------------------------------------------------------------
    def _click(self, aff: AffordanceEvidence, inp: str | None) -> tuple[list[RequestEvidence], str | None, str | None]:
        """Perform a click on the live page. Returns (requests, failure, truth capability)."""
        w = self.__world
        match = next(((c, inst) for a, c, inst in w.affordances() if _same(a, aff)), None)
        if match is None:
            return [], "control_not_found", None
        c, inst = match
        if not w.met(c) and c.gate == "disabled":
            return [], "control_disabled", None
        self.__clicks += 1
        if self.__spec.flaky and _h("flaky", self.__spec.seed, self.__clicks) < self.__spec.flaky:
            return [], "timeout", None
        cap, op, effect = c.cap, c.op, c.effect
        if c.variant and w.inst and int(hashlib.sha256(w.inst.encode()).hexdigest(), 16) % 2:
            cap, op, effect = c.variant
        reqs: list[RequestEvidence] = []
        if not w.met(c):          # gate == "fail": the request is refused
            m, path = (op[0], op[1]) if op else ("GET", "/")
            reqs.append(RequestEvidence(method=m, url=ORIGIN + path.replace("{id}", w.inst or "0"),
                                        status=401 if c.requires and c.requires.startswith("role:") else 422,
                                        resource_type=op[4] if op else "fetch"))
            return reqs, f"http_{reqs[0].status}", None
        filled = [f[0] for f in c.fields]
        value = {"primary": "alpha", "contrast": "omega"}.get(inp or "", "v" + str(self.__clicks))
        if op:
            method, path, params, enc, rtype = op
            url = ORIGIN + path.replace("{id}", w.inst or "0")
            if method == "GET" and filled:
                url += "?" + "&".join(f"{n}={value}" for n in filled)
            reqs.append(RequestEvidence(method=method, url=url, status=200, resource_type=rtype,
                                        param_names=list(params), body_encoding=enc, engine_filled=filled))
        prev = (w.page, w.inst, w.query)
        if effect == "navigate":
            target = c.target or w.page
            new_inst = inst if c.per_instance else (w.inst if self.__spec.pages[target].entity else None)
            self._go(target, new_inst, None)
            if not c.hidden_id:
                reqs.append(RequestEvidence(method="GET", url=w.url(), status=200, resource_type="document"))
        elif effect == "search":
            self._go(c.target, None, value)
            reqs = [RequestEvidence(method="GET", url=w.url(), status=200, resource_type="document",
                                    param_names=["q"], engine_filled=["q"])]
        elif effect == "create":
            ent = self.__spec.pages[c.target].entity
            self.__world.created += 1
            new = str(100000 + self.__world.created)
            w.instances[ent].append(new)
            self._go(c.target, new, None)
            reqs.append(RequestEvidence(method="GET", url=w.url(), status=200, resource_type="document"))
        elif effect == "update":
            self._go(c.target, w.inst, None)
            reqs.append(RequestEvidence(method="GET", url=w.url(), status=200, resource_type="document"))
        elif effect == "toggle":
            w.open ^= {c.opens}
        elif effect == "storage":
            w.storage.add("k_" + c.key)
        elif effect == "region":
            w.region_state[c.key] = w.region_state.get(c.key, 0) + 1
        if c.sets:
            w.session.add(c.sets)
        if (w.page, w.inst, w.query) != prev and effect in {"navigate", "search", "create", "update"}:
            w.history.append(prev)
        return reqs, None, cap

    def _go(self, page: str, inst: str | None, query: str | None) -> None:
        w = self.__world
        w.page, w.inst, w.query = page, inst, query
        w.open = set()

    def _goto(self, url: str) -> bool:
        w = self.__world
        parts = urlsplit(url if "://" in url else ORIGIN + url)
        path = parts.path or "/"
        q = dict(parse_qsl(parts.query)).get("q")
        for key, p in self.__spec.pages.items():
            if "{id}" in p.route:
                pre, post = p.route.split("{id}", 1)
                if path.startswith(pre) and path.endswith(post) and len(path) > len(pre) + len(post):
                    inst = path[len(pre):len(path) - len(post)]
                    if "/" not in inst and inst in w.instances.get(p.entity or "", []) and w.page_allowed(key):
                        w.history.append((w.page, w.inst, w.query))
                        self._go(key, inst, None)
                        return True
            elif p.route == path and w.page_allowed(key) and not p.entity:
                w.history.append((w.page, w.inst, w.query))
                self._go(key, None, q if p.results_of else None)
                return True
        return False

    def run(self, plan: ExperimentPlan, remaining: int, gate: RiskGate, records: list[Record]) -> ExperimentResult:
        w = self.__world
        out: list[Record] = []
        used, refused, action_ids, replay_ids, record_actions = 0, [], [], [], []
        purpose: dict[str, int] = {}
        live = self.__live
        independent = bool(plan.steps) and plan.steps[0].op in {"fresh", "snapshot"}
        snapshot_ok = False
        captured: list[str] = []
        oracle_reqs: list[RequestEvidence] | None = None
        abort = None
        for step in plan.steps:
            cost = getattr(self.costs, step.op)
            if used + cost > remaining:
                abort = "budget"
                break
            reason = gate.check(step, live.url, snapshot_ok)
            if reason:
                refused.append(reason)
                abort = "refused:" + reason
                break
            if step.op == "click":
                reqs, failure, cap = self._click(step.affordance, step.input)
                if failure in {"control_not_found", "control_disabled"}:
                    abort = failure
                    break
            used += cost
            purpose[step.purpose] = purpose.get(step.purpose, 0) + cost
            if step.op == "fresh":
                w.fresh(step.role or self.isolation.default_role)
            elif step.op == "snapshot":
                w.snapshot_restore(step.role or self.isolation.default_role)
            elif step.op == "back":
                if w.history:
                    page, inst, query = w.history.pop()
                    self._go(page, inst, query)
            elif step.op == "goto":
                if not self._goto(step.url or "/"):
                    self._go(w.page, w.inst, w.query)
            context = "replay" if step.replay_of or plan.oracle else "exploration"
            obs = self._observe(context, plan.kind)
            if step.op == "snapshot":
                fingerprint_ok = not self.__spec.snapshot_drift
                probe_ok = sorted((a.kind, a.locator, a.target or "") for a in obs.affordances or []) == self.__initial_root
                snapshot_ok = fingerprint_ok and probe_ok
                if not snapshot_ok:
                    out.append(obs)
                    record_actions.append(used)
                    abort = "unverified_start_state"
                    break
            if step.op == "click":
                status = "observed" if failure is None else "failed"
                if step.replay_of:
                    rid, rep_id, seq = self._rid("rep")
                    rec = Record(id=rid, seq=seq, kind="replay", source=Source(artifact="appsim", pointer=rep_id),
                                 replay_id=rep_id, action_id=step.replay_of, result_obs=obs.obs_id, requests=reqs,
                                 status="replay_validated" if failure is None else "replay_failed", error=failure,
                                 independent_context=independent, verification_kind="standard")
                    replay_ids.append(rep_id)
                    self.__truth_actions[rep_id] = cap
                else:
                    rid, act_id, seq = self._rid("act")
                    rec = Record(id=rid, seq=seq, kind="action", source=Source(artifact="appsim", pointer=act_id),
                                 action_id=act_id, source_obs=live.obs_id, result_obs=obs.obs_id,
                                 affordance=step.affordance, status=status, requests=reqs, error=failure)
                    action_ids.append(act_id)
                    self.__truth_actions[act_id] = cap
                out.extend([obs, rec])
                record_actions.extend([used, used])
                if step.oracle_capture == "before_after":
                    captured.extend([live.obs_id, obs.obs_id])
                elif step.oracle_capture == "after":
                    captured.append(obs.obs_id)
                if step.oracle_capture and oracle_reqs is None:
                    oracle_reqs = reqs
                if failure is not None:
                    live = obs
                    abort = "action_failed:" + failure
                    break
            else:
                out.append(obs)
                record_actions.append(used)
                if step.oracle_capture == "after":
                    captured.append(obs.obs_id)
            live = obs
        completed = abort is None
        self.__live = live
        if plan.oracle and completed and plan.oracle_action:
            rid, rep_id, seq = self._rid("rep")
            out.append(Record(id=rid, seq=seq, kind="replay", source=Source(artifact="appsim", pointer=rep_id),
                              replay_id=rep_id, action_id=plan.oracle_action, result_obs=captured[1 if plan.oracle == "paired_search" else 0],
                              requests=oracle_reqs or [], status="replay_validated", independent_context=independent,
                              verification_kind=plan.oracle, verification={"verification_observation_ids": captured}))
            record_actions.append(used)
            replay_ids.append(rep_id)
        out.sort(key=lambda r: r.seq)
        return ExperimentResult(records=out, actions=used, completed=completed, abort_reason=abort, refused=refused,
                                live_obs=live.obs_id, action_ids=action_ids, replay_ids=replay_ids,
                                record_actions=record_actions, purpose_actions=purpose)


# ------------------------------------------------------------------------- 4. evaluation
class Oracle:
    """Hidden truth for scoring. Never passed to a selector."""

    def __init__(self, spec: AppSpec, actions: dict[str, str | None], obs: dict[str, tuple[str, str | None]],
                 plan_kind_of_obs: dict[str, str]) -> None:
        self.spec, self.actions, self.obs, self.plan_kind_of_obs = spec, actions, obs, plan_kind_of_obs
