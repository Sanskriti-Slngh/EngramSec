"""What the planner knows: indexes over its own evidence log and the materialized ACG.

Nothing here reads display text. Concrete controls are linked to ACG
affordance nodes structurally (template, kind, component, locator family,
target route, method, fields), using only fields the ACG exports.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit

from agent1.model.evidence import AffordanceEvidence, Record
from agent1.model.routes import path_route, strip_positions
from agent1.model.schema import ACGExport, Affordance, Capability, Claim, STATUS_RANK, Status

from .gate import writes as writes_request
from .interfaces import ExperimentPlan, ExperimentResult, Step


@dataclass(frozen=True)
class TrailStep:
    op: str                               # click | goto | back
    aff: AffordanceEvidence | None = None
    url: str | None = None
    action: str | None = None             # recorded action id a replay of this step re-executes
    stateful: bool = False                # may have changed session/client state (not a pure page load)
    writes: bool = False
    obs: str | None = None                # observation this step produced, when it was a page load
    sent: bool = False                    # sent a non-document request (its effect persists in the context)


@dataclass
class ObsInfo:
    record: Record
    epoch: int
    trail: tuple[TrailStep, ...]
    doc_entry: bool                        # produced by a document load
    prev: str | None = None
    via: TrailStep | None = None
    input_free_read: bool = True           # the step that produced it was input-free and read-only


def _troute(target: str | None) -> str:
    return path_route(urlsplit(target).path) if target else ""


def concrete_key(template_id: str, a: AffordanceEvidence) -> tuple:
    troute = _troute(a.target)
    locator = strip_positions(a.locator) if "{id}" in troute else a.locator
    return (template_id, a.kind, a.role_attr, a.interaction, a.component, locator, troute, (a.method or "").upper(),
            tuple((f.name, f.input_type, f.required) for f in a.fields), a.provenance)


def family_key(aff: Affordance) -> tuple:
    f = aff.family
    return (aff.template_id, f["kind"], f["role"], f["interaction"], f["component"], f["locator"],
            f["target_route"].split("?")[0], f["method"], tuple(tuple(x) for x in f["fields"]), f["provenance"])


def stateful(record: Record | None) -> bool:
    """A click that did more than load a page may have changed session or client state."""
    if record is None:
        return True
    reqs = record.requests or []
    return not reqs or any(q.resource_type != "document" or (q.method or "GET").upper() != "GET" for q in reqs)


@dataclass
class Knowledge:
    obs: dict[str, ObsInfo] = field(default_factory=dict)
    actions: dict[str, Record] = field(default_factory=dict)
    replays: dict[str, Record] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)          # obs ids in arrival order
    epoch: int = 0
    seen: int = 0
    # rebuilt from the ACG at every decision
    acg: ACGExport | None = None
    tpl_of_obs: dict[str, str] = field(default_factory=dict)
    view_of_obs: dict[str, str] = field(default_factory=dict)
    templates: dict = field(default_factory=dict)
    affs: dict[str, Affordance] = field(default_factory=dict)
    caps: dict[str, Capability] = field(default_factory=dict)
    cap_of_action: dict[str, str] = field(default_factory=dict)
    aff_of_action: dict[str, str] = field(default_factory=dict)
    claims: dict[str, list[Claim]] = field(default_factory=dict)
    reproduced_templates: set[str] = field(default_factory=set)
    obs_of_template: dict[str, list[str]] = field(default_factory=dict)
    _fam_index: dict[tuple, str] = field(default_factory=dict)
    # Recorded actions whose replay failed deterministically or changes state (live ledger only;
    # always empty in the simulator): restoration never plans through them.
    blocked_actions: set[str] = field(default_factory=set)
    blocked_restorations: set[tuple[str, str]] = field(default_factory=set)   # ("back", target) / ("goto", url)
    _occ_cache: dict[tuple[str, str], list[tuple[str, AffordanceEvidence]]] = field(default_factory=dict)

    # evidence ---------------------------------------------------------------------------
    def start(self, records: list[Record]) -> None:
        for r in records:
            if r.kind == "observation" and r.obs_id:
                self.obs[r.obs_id] = ObsInfo(record=r, epoch=0, trail=(), doc_entry=True)
                self.order.append(r.obs_id)
        self.seen = len(records)

    def ingest(self, plan: ExperimentPlan, result: ExperimentResult, prev_live: str) -> None:
        steps = list(plan.steps)
        observed = sum(1 for r in result.records if r.kind == "observation")
        if result.completed and observed != len(steps):
            # Observations are associated with steps by position; with any step's observation missing,
            # a later state would be credited to an earlier step. Refuse rather than guess.
            raise ValueError(f"execution association: {observed} observations for {len(steps)} executed steps")
        i, prev = 0, prev_live
        pending: tuple[str, Step] | None = None
        for r in result.records:
            if r.kind == "observation" and r.obs_id:
                step = steps[i] if i < len(steps) else Step(op="goto")
                i += 1
                self._add_obs(r, step, prev)
                pending = (r.obs_id, step) if step.op == "click" else None
                prev = r.obs_id
            elif r.kind in {"action", "replay"}:
                if r.kind == "action":
                    self.actions[r.action_id] = r
                else:
                    self.replays[r.replay_id] = r
                if pending and r.result_obs == pending[0]:
                    self._finish_click(pending[0], pending[1], r)
                    pending = None

    def _add_obs(self, r: Record, step: Step, prev: str) -> None:
        p = self.obs[prev]
        if step.op in {"fresh", "snapshot"}:
            self.epoch += 1
            info = ObsInfo(record=r, epoch=self.epoch, trail=(), doc_entry=True, prev=prev)
        elif step.op == "goto":
            keep = p.trail
            while keep and not keep[-1].stateful:
                keep = keep[:-1]
            info = ObsInfo(record=r, epoch=self.epoch, trail=keep + (TrailStep(op="goto", url=r.url, obs=r.obs_id),),
                           doc_entry=True, prev=prev)
        elif step.op == "back":
            # Back after a state-free page load returns to the earlier page's state; its trail is that
            # page's trail (a recorded "back" would depend on browser history that a replay does not have).
            back_to = self.obs.get(p.prev) if p.prev and p.via is not None and not p.via.stateful else None
            trail = back_to.trail if back_to is not None else p.trail + (TrailStep(op="back"),)
            info = ObsInfo(record=r, epoch=self.epoch, trail=trail, doc_entry=False, prev=prev)
        else:   # click: completed by _finish_click when its action/replay record arrives
            info = ObsInfo(record=r, epoch=self.epoch, trail=p.trail, doc_entry=False, prev=prev)
        self.obs[r.obs_id] = info
        self.order.append(r.obs_id)

    def _finish_click(self, oid: str, step: Step, rec: Record) -> None:
        info = self.obs[oid]
        if rec.status not in {"observed", "replay_validated"}:
            return
        original = step.replay_of or rec.action_id
        orig = self.actions.get(original)
        writes = writes_request(rec) or (orig is not None and writes_request(orig))
        url = urlsplit(info.record.url or "").path
        info.doc_entry = any(q.resource_type == "document" and urlsplit(q.url).path == url for q in rec.requests or [])
        sent = any(q.resource_type != "document" for q in rec.requests or [])
        ts = TrailStep(op="click", aff=step.affordance, action=original, stateful=stateful(rec), writes=writes,
                       url=info.record.url if info.doc_entry else None, obs=oid if info.doc_entry else None,
                       sent=sent)
        info.trail = self.obs[info.prev].trail + (ts,)
        info.via = ts
        info.input_free_read = not writes and not step.affordance.fields

    # ACG --------------------------------------------------------------------------------
    def refresh(self, acg: ACGExport) -> None:
        self.acg = acg
        self.templates = {t.id: t for t in acg.templates}
        self.tpl_of_obs = {o: t.id for t in acg.templates for o in t.observation_ids}
        self.view_of_obs = {o: v.id for v in acg.view_states for o in v.observation_ids}
        self.affs = {a.id: a for a in acg.affordances}
        self.caps = {c.id: c for c in acg.capabilities}
        self.cap_of_action = {a: c.id for c in acg.capabilities for a in c.action_ids}
        self.aff_of_action = {x: a.id for a in acg.affordances for x in a.action_ids}
        self.claims = {}
        for c in acg.claims:
            self.claims.setdefault(c.predicate, []).append(c)
        self._fam_index = {family_key(a): a.id for a in acg.affordances}
        self.obs_of_template = {t.id: [o for o in t.observation_ids if o in self.obs] for t in acg.templates}
        self.reproduced_templates = {
            e.target for c in acg.capabilities if STATUS_RANK.get(c.status, -1) >= STATUS_RANK[Status.REPRODUCED]
            and not self.cap_writes(c.id) for e in c.effects if e.kind == "navigated"}

    def occurrences(self, oid: str) -> list[tuple[str, AffordanceEvidence]]:
        """(ACG affordance id, concrete control) for every control rendered in an observation."""
        tid = self.tpl_of_obs.get(oid)
        if tid is None:
            return []
        key = (oid, tid)
        if key not in self._occ_cache:
            out = []
            for a in self.obs[oid].record.affordances or []:
                aid = self._fam_index.get(concrete_key(tid, a))
                if aid:
                    out.append((aid, a))
            self._occ_cache[key] = out
        return self._occ_cache[key]

    def status(self, cap_id: str) -> int:
        c = self.caps.get(cap_id)
        return STATUS_RANK.get(c.status, -1) if c else -1

    def cap_writes(self, cap_id: str) -> bool:
        c = self.caps.get(cap_id)
        if c is None:
            return True
        return any(writes_request(self.actions[a]) for a in c.action_ids if a in self.actions)

