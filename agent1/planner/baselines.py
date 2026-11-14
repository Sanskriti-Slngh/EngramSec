"""Baseline selectors on the shared Selector interface (§10.1).

`BFS` is ordinary breadth-first exploration over (state, control).

`LegacyFrontier` is an offline approximation of the frozen `f6744ba`
frontier in its best documented configuration (policy `multidimensional`,
persistent session with a local burst of up to 8 live-page items, state-aware
exploration, the fixed 30% replay reserve). Approximations, recorded in the
report: wall time is replaced by browser actions; prefix and history-return
reuse are omitted (the hierarchy report found prefix reuse fired 0 times in
persistent mode); restoration replays the saved path from the start URL in
the same context, or from a fresh context when the role differs; replay
order prefers unseen request structures first, then the cheapest path.
Both baselines may read display labels; that is what the legacy code does.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any
from urllib.parse import urlsplit

from agent1.model.evidence import AffordanceEvidence, Record
from agent1.model.routes import identifier_segments, path_route, strip_positions

from .gate import READ_METHODS, control_key, writes
from .interfaces import AgentView, ExperimentPlan, ExperimentResult, Step

LOW_VALUE_REPORT = re.compile(r"^(?:view\s+)?(?:results?|score(?:board)?|reports?|status|exports?)(?:\s|$)", re.I)
AMBIGUOUS_LABEL = re.compile(r"^(|click|submit|go|ok|more|next|button|link)$", re.I)
GLOBAL_COMPONENT = re.compile(r"^(nav|header|footer|aside)(?::|>|$)", re.I)


def _d(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]


def same_control(a: AffordanceEvidence, b: AffordanceEvidence) -> bool:
    return (a.kind, a.component, a.locator, a.target, a.method) == (b.kind, b.component, b.locator, b.target, b.method)


def usable(a: AffordanceEvidence) -> bool:
    return a.safe and not a.disabled


class _Log:
    """Incremental index over the evidence records a selector has received."""

    def __init__(self) -> None:
        self.obs: dict[str, Record] = {}
        self.actions: dict[str, Record] = {}
        self.n = 0

    def ingest(self, records: list[Record]) -> list[Record]:
        new = records[self.n:]
        for r in new:
            if r.kind == "observation" and r.obs_id:
                self.obs[r.obs_id] = r
            elif r.kind == "action" and r.action_id:
                self.actions[r.action_id] = r
        self.n = len(records)
        return new


def _restore(start: str, role_now: str | None, role: str | None, path: list[tuple[AffordanceEvidence, str]],
             fresh: bool = False) -> list[Step]:
    first = Step(op="fresh", role=role, purpose="restore") if fresh or role_now != role else \
        Step(op="goto", url=start, purpose="restore")
    return [first] + [Step(op="click", affordance=a, replay_of=act, purpose="restore") for a, act in path]


class BFS:
    name = "bfs"
    uses_acg = False

    def __init__(self, isolation, costs, budget: int, seed: int = 0) -> None:
        self.iso = isolation
        self.log = _Log()
        self.queue: list[dict[str, Any]] = []
        self.states: dict[str, list[tuple[AffordanceEvidence, str]]] = {}
        self.state_role: dict[str, str | None] = {}
        self.tried: set[tuple[str, tuple]] = set()
        self.pending: dict[str, Any] | None = None
        self._decisions: list[dict[str, Any]] = []
        self.started = False

    @staticmethod
    def state_id(o: Record) -> str:
        affs = sorted((a.kind, a.component, a.locator, a.target or "", bool(a.disabled)) for a in o.affordances or [])
        return _d([o.role, urlsplit(o.url or "").path, urlsplit(o.url or "").query, affs])

    def _discover(self, o: Record, path: list[tuple[AffordanceEvidence, str]]) -> None:
        sid = self.state_id(o)
        if sid in self.states:
            return
        self.states[sid] = path
        self.state_role[sid] = o.role
        for a in o.affordances or []:
            key = (sid, (a.kind, a.component, a.locator, a.target, a.method))
            if usable(a) and key not in self.tried:
                self.tried.add(key)
                self.queue.append({"state": sid, "aff": a})

    def next(self, view: AgentView) -> ExperimentPlan | None:
        self.log.ingest(view.records)
        live = self.log.obs[view.live_obs]
        if not self.started:
            self.started = True
            self._discover(live, [])
            for role in view.isolation.roles:
                if role != live.role:
                    self.queue.append({"state": None, "role": role})
        while self.queue:
            item = self.queue.pop(0)
            if item["state"] is None:
                self.pending = {"path": [], "aff": None}
                self._decisions.append({"op": "role_root", "role": item["role"]})
                return ExperimentPlan(kind="explore", steps=[Step(op="fresh", role=item["role"], purpose="restore")])
            path = self.states[item["state"]]
            here = self.state_id(live) == item["state"]
            steps = [] if here else _restore(view.isolation.start_url, live.role, self.state_role[item["state"]], path)
            steps.append(Step(op="click", affordance=item["aff"]))
            self.pending = {"path": path, "aff": item["aff"]}
            self._decisions.append({"op": "explore", "state": item["state"], "control": list(
                (item["aff"].kind, item["aff"].component, item["aff"].locator, item["aff"].target or "")),
                "restore": len(steps) - 1})
            return ExperimentPlan(kind="explore", steps=steps)
        return None

    def update(self, plan: ExperimentPlan, result: ExperimentResult, view: AgentView) -> None:
        self.log.ingest(view.records + result.records)
        if self.pending is None:
            return
        if self.pending["aff"] is None:
            self._discover(self.log.obs[result.live_obs], [])
        for aid in result.action_ids:
            act = self.log.actions[aid]
            if act.status == "observed" and act.result_obs:
                self._discover(self.log.obs[act.result_obs], self.pending["path"] + [(act.affordance, aid)])
        self.pending = None

    def decisions(self) -> list[dict[str, Any]]:
        return self._decisions


class LegacyFrontier:
    name = "legacy_frontier"
    uses_acg = False
    REPLAY_RESERVE = 0.30
    LOCAL_BURST = 8

    def __init__(self, isolation, costs, budget: int, seed: int = 0) -> None:
        self.iso, self.budget = isolation, budget
        self.log = _Log()
        self.frontier: list[dict[str, Any]] = []
        self.tried: set[str] = set()
        self.seen_shapes: set[str] = set()
        self.seen_targets: set[str] = set()
        self.seen_components: set[str] = set()
        self.seen_forms: set[str] = set()
        self.scheduled_global: set[str] = set()
        self.ineffective: dict[str, int] = defaultdict(int)
        self.known_writes: set[tuple] = set()
        self.transitions: list[dict[str, Any]] = []
        self.return_paths: dict[str, list] = {}
        self.live_path: list[tuple[AffordanceEvidence, str]] = []
        self.local_burst = 0
        self.burst_group: str | None = None
        self.phase = "explore"
        self.replays: list[dict[str, Any]] | None = None
        self.pending: dict[str, Any] | None = None
        self._decisions: list[dict[str, Any]] = []
        self.started = False

    # legacy state abstractions ------------------------------------------------------------
    @staticmethod
    def signature(a: AffordanceEvidence) -> str:
        target = path_route(urlsplit(a.target).path) if a.target else ""
        return _d([a.kind, a.role_attr, a.label, target, (a.method or "").upper(), a.interaction, a.component])

    @staticmethod
    def group(o: Record) -> str:
        shapes = sorted(_d([a.kind, a.role_attr, "" if a.kind == "link" else a.label,
                            path_route(urlsplit(a.target).path) if a.target else "", (a.method or "").upper(),
                            [(f.name, f.input_type, f.required) for f in a.fields], a.interaction, a.component])
                        for a in o.affordances or [] if usable(a))
        return _d([o.role, path_route(urlsplit(o.url or "").path), shapes])

    @staticmethod
    def instance(o: Record) -> str:
        segs = identifier_segments(urlsplit(o.url or "").path)
        return segs[0][2] if segs else ""

    def _known_write(self, o: Record, a: AffordanceEvidence) -> bool:
        return control_key(o.url, a) in self.known_writes

    def _enqueue(self, o: Record, path: list[tuple[AffordanceEvidence, str]]) -> None:
        safe = [a for a in o.affordances or [] if usable(a)]
        order = sorted(safe, key=lambda a: ({"form_submit": 3, "button": 2, "link": 1}[a.kind],
                                            not AMBIGUOUS_LABEL.match(a.label), a.label.lower()), reverse=True)
        identity = self.group(o) + (":" + self.instance(o) if self.instance(o) else "")
        for rank, a in enumerate(order):
            if self._known_write(o, a):
                continue
            sig = self.signature(a)
            tried_key = identity + ":" + sig
            if tried_key in self.tried:
                continue
            global_component = bool(GLOBAL_COMPONENT.match(a.component))
            global_key = _d([a.interaction, a.target or "", a.role_attr, a.label])
            if global_component and global_key in self.scheduled_global:
                self.tried.add(tried_key)
                continue
            self.tried.add(tried_key)
            if global_component:
                self.scheduled_global.add(global_key)
            score = {"form_submit": 3.0, "button": 2.0, "link": 1.0}[a.kind]
            search = a.kind == "form_submit" and (a.method or "GET").upper() == "GET" and bool(a.fields)
            if a.kind == "form_submit" and not search and any(x.kind != "form_submit" for x in safe):
                score -= 45.0
            novel = sig not in self.seen_shapes
            self.seen_shapes.add(sig)
            target_key = a.target or ""
            target_novel = bool(target_key and target_key not in self.seen_targets)
            component_key = f"{a.component}:{a.role_attr}:{a.label}"
            component_novel = component_key not in self.seen_components
            form_shape = _d([a.method or "", a.target or "", [(f.input_type, f.name, f.required) for f in a.fields]])
            form_novel = bool(a.fields and form_shape not in self.seen_forms)
            score += 15.0 if target_novel else 0.0
            score += 8.0 if component_novel else 0.0
            score += 12.0 if form_novel else 0.0
            score += 10.0 if a.interaction not in {"click", "navigate"} else 0.0
            score += 5.0 if novel else 0.0
            score -= 0.6 * len(path)
            score -= 8.0 * self.ineffective[sig]
            if global_component and not target_novel:
                score -= 10.0
            if global_component:
                score -= 18.0
            if a.kind == "link" and LOW_VALUE_REPORT.match(a.label):
                score -= 28.0
            if target_key:
                self.seen_targets.add(target_key)
            self.seen_components.add(component_key)
            if a.fields:
                self.seen_forms.add(form_shape)
            self.frontier.append({"source": o.obs_id, "group": self.group(o), "instance": self.instance(o),
                                  "role": o.role, "path": list(path), "aff": a, "sig": sig,
                                  "priority": score - rank / max(1, len(order))})
        self.frontier.sort(key=lambda i: (-i["priority"], len(i["path"]), i["sig"]))

    # selection ----------------------------------------------------------------------------
    def next(self, view: AgentView) -> ExperimentPlan | None:
        self._ingest(view.records)
        live = self.log.obs[view.live_obs]
        if not self.started:
            self.started = True
            self._enqueue(live, [])
            self.return_paths[self.group(live)] = []
        if self.phase == "explore":
            plan = self._explore(view, live)
            if plan is not None:
                return plan
            self.phase = "replay"
        return self._replay(view, live)

    def _explore(self, view: AgentView, live: Record) -> ExperimentPlan | None:
        live_group = self.group(live)
        if live_group != self.burst_group:
            self.burst_group, self.local_burst = live_group, 0
        while self.frontier:
            index, local = 0, False
            if self.local_burst < self.LOCAL_BURST:
                for i, item in enumerate(self.frontier):
                    if item["group"] == live_group and item["instance"] == self.instance(live) and \
                            any(same_control(item["aff"], a) and usable(a) for a in live.affordances or []):
                        index, local = i, True
                        break
            item = self.frontier.pop(index)
            source = self.log.obs[item["source"]]
            if self._known_write(source, item["aff"]):
                continue
            cost = 1 if local else 2 + len(item["path"])
            if view.used + cost > self.budget * (1 - self.REPLAY_RESERVE):
                self.frontier.insert(index, item)
                return None
            self.local_burst = self.local_burst + 1 if local else 0
            steps = [] if local else _restore(view.isolation.start_url, live.role, item["role"], item["path"])
            steps.append(Step(op="click", affordance=item["aff"]))
            path = self.live_path if local else item["path"]
            self.pending = {"path": list(path), "aff": item["aff"]}
            self._decisions.append({"op": "explore", "sig": item["sig"], "priority": round(item["priority"], 6),
                                    "local": local})
            return ExperimentPlan(kind="explore", steps=steps)
        return None

    def _replay(self, view: AgentView, live: Record) -> ExperimentPlan | None:
        if self.replays is None:
            cands = sorted((t for t in self.transitions if not self._known_write(t["source"], t["aff"])),
                           key=lambda t: (1 + len(t["path"]), t["action"]))
            seen, first, rest = set(), [], []
            for t in cands:
                (rest if t["structure"] in seen else first).append(t)
                seen.add(t["structure"])
            self.replays = first + rest
        while self.replays:
            t = self.replays.pop(0)
            steps = _restore(view.isolation.start_url, live.role, t["role"], t["path"], fresh=True)
            steps.append(Step(op="click", affordance=t["aff"], replay_of=t["action"]))
            if view.used + len(steps) > self.budget:
                continue
            self.pending = None
            self._decisions.append({"op": "replay", "action": t["action"]})
            return ExperimentPlan(kind="reproduce", steps=steps)
        return None

    def _ingest(self, records: list[Record]) -> None:
        for r in self.log.ingest(records):
            if r.kind == "action" and r.affordance is not None and writes(r):
                src = self.log.obs.get(r.source_obs or "")
                self.known_writes.add(control_key(src.url if src else None, r.affordance))

    def update(self, plan: ExperimentPlan, result: ExperimentResult, view: AgentView) -> None:
        self._ingest(view.records + result.records)
        live = self.log.obs[result.live_obs]
        if self.pending is None:
            self.live_path = list(self.return_paths.get(self.group(live), [])) if result.completed else []
            return
        path = self.pending["path"]
        for aid in result.action_ids:
            act = self.log.actions[aid]
            if act.status != "observed" or not act.result_obs:
                continue
            src, res = self.log.obs[act.source_obs], self.log.obs[act.result_obs]
            new_path = path + [(act.affordance, aid)]
            if self.group(src) == self.group(res) and not act.requests:
                self.ineffective[self.signature(act.affordance)] += 1
            structure = _d(sorted(((q.method or "GET").upper(), path_route(urlsplit(q.url).path))
                                  for q in act.requests or [] if q.resource_type != "document"))
            self.transitions.append({"action": aid, "path": path, "aff": act.affordance, "source": src,
                                     "role": src.role, "structure": structure})
            key = self.group(res)
            if key not in self.return_paths or len(self.return_paths[key]) > len(new_path):
                self.return_paths[key] = new_path
            self._enqueue(res, new_path)
        self.live_path = list(self.return_paths.get(self.group(live), [])) if result.completed else []
        self.pending = None

    def decisions(self) -> list[dict[str, Any]]:
        return self._decisions


__all__ = ["BFS", "LegacyFrontier", "same_control", "usable", "READ_METHODS", "strip_positions"]
