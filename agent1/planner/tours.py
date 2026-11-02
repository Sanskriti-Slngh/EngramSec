"""Capability Tour Scheduler (Phase 1b-R).

A replacement for the Phase 1b selection policy, keeping its ACG question
structure. Instead of choosing one atomic question at a time by expected
information gain inside a UCB-chosen area, it runs *tours*: short, bounded
sequences of discovery experiments in the live browser context, continued
while useful permitted work remains there, and chooses where to go next by
whole-plan cost (restoration included). Independent verification is a
separate agenda that runs at tour boundaries, when the live context holds no
prerequisite progress, or from a bounded end-of-budget reserve.

Decision inputs (all observable): the risk gate, the remaining open
questions, actual plan cost in actions, observed new capabilities, witnessed
prerequisite progress (a control seen disabled, then enabled in the same
context), and the structure of what has been explored so far. No EIG,
Good–Turing estimate, Unlock bonus or UCB is used. No display text is read.

Modes: `full`; `no_local` (no tour continuation, chain priority, revisits or
context protection); `no_global` (remote plans chosen uniformly instead of by
cost-aware coverage).
"""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import Any
from urllib.parse import urlsplit

from agent1.model.routes import path_route
from agent1.model.schema import STATUS_RANK, Status

from .designer import Restore, _replay, restore
from .gate import RiskGate
from .interfaces import AgentView, ExperimentPlan, ExperimentResult, Step
from .knowledge import Knowledge
from .planner import RunState
from .questions import Question, area_of, enabled_targets, generate, instance_of

# Fixed once before any T2R result; not tuned.
TOUR = {
    "max_length": 20,             # experiments per tour
    "material": 2.0,              # a remote plan must be this many times better per action to interrupt a tour
    "verify_min_share": 0.10,     # verification share sought at tour boundaries
    "verify_max_share": 0.30,     # verification never exceeds this share while discovery has work
    "verify_reserve": 0.20,       # end-of-budget reserve for queued verification
    "fallback_min_binds": 15,     # structure evidence needed before a mode decision
    "fallback_unique": 0.80,      # share of bindings that each revealed a distinct capability
    "fallback_repeated": 0.10,    # share of affordances in repeated families or instance families
    "revisit_limit": 2,           # revisits of one page per browser context
}
DISCOVERY = {"bind_affordance", "sample_instance", "split_test", "find_entry_point", "revisit"}
VERIFICATION = {"reproduce", "verify_effect", "test_dependency", "test_equivalence"}
KIND_ORDER = {"bind_affordance": 0, "revisit": 1, "sample_instance": 2, "split_test": 3, "find_entry_point": 4,
              "reproduce": 5, "test_equivalence": 6, "verify_effect": 7, "test_dependency": 8}


class TourState:
    """Run-local bookkeeping the question generators need (no probability estimates)."""

    locator_order = staticmethod(RunState.locator_order)
    instance_links = RunState.instance_links

    def __init__(self) -> None:
        self.inconclusive: Counter = Counter()
        self.tested_claims: set[str] = set()
        self.split_done: dict[str, set] = defaultdict(set)
        self.family_out: dict[tuple, Counter] = defaultdict(Counter)
        self.minimal_failed: set[str] = set()

    def family_allows(self, fam: tuple) -> bool:
        """Open the next member of a repeated family only while every binding so far was distinct."""
        outs = [s for s, c in self.family_out[fam].items() if s != "FAIL" for _ in range(c)]
        return not outs or len(set(outs)) == len(outs)


def _url_area(url: str | None) -> str:
    path = urlsplit(url or "").path.strip("/")
    return path.split("/")[0] if path else "root"


class TourScheduler:
    uses_acg = True

    def __init__(self, isolation, costs, budget: int, seed: int = 0, mode: str = "full") -> None:
        self.iso, self.costs, self.budget, self.seed, self.variant = isolation, costs, budget, seed, mode
        self.name = {"full": "tour_full", "no_local": "tour_no_local", "no_global": "tour_no_global",
                     "v2": "tour_v2"}[mode]
        self.uniform_global = mode in {"no_global", "v2"}
        self.verif_log: list[tuple[str, str, int, bool]] = []
        self.global_suppressed: set[str] = set()
        # Questions the real executor's safety layer refused (populated only by the live adapter;
        # empty in the simulator): blocked with the executor's reason instead of being re-proposed.
        self.external_blocked: dict[str, str] = {}
        self.unrestorable: set[str] = set()
        self.no_oracle: set[str] = set()
        self.no_reproduce: set[str] = set()
        self.k = Knowledge()
        self.st = TourState()
        self.gate = RiskGate(isolation)
        self.live: str | None = None
        self.started = False
        self.mode = "tours"
        self.mode_log: list[dict[str, Any]] = []
        self.tour: dict[str, Any] | None = None
        self.tours: list[dict[str, Any]] = []
        self.log: list[dict[str, Any]] = []
        self.pending: dict[str, Any] | None = None
        self.used = 0
        self.verif_actions = 0
        self.binds = Counter()                     # outcome class counts of bind experiments
        self.new_q_per_template: list[int] = []
        self.seen_templates: set[str] = set()
        self.disabled_seen: dict[tuple[int, str], str] = {}    # (epoch, aff) -> first disabled obs
        self.disabled_any: dict[str, str] = {}                  # aff -> first disabled obs in any context
        self.chains: dict[tuple[int, str], dict[str, Any]] = {}
        self.revisits: Counter = Counter()
        self.verification_blocked: Counter = Counter()
        self.blocked_q: dict[str, str] = {}
        self.snapshot_failed = False
        self._draw = 0
        self._last_obs_seen = 0

    # ---------------------------------------------------------------------- helpers
    def _perm(self, key: str) -> str:
        return hashlib.sha256(f"{self.seed}:{key}".encode()).hexdigest()

    def _uniform(self, items: list):
        items = sorted(items, key=lambda x: x[0].id)
        i = int(self._perm(f"draw:{self._draw}"), 16) % len(items)
        self._draw += 1
        return items[i]

    def _gate_ok(self, steps: list[Step], r: Restore | None) -> bool:
        verified = bool(steps) and steps[0].op == "snapshot" and not self.snapshot_failed
        if steps and steps[0].op == "snapshot" and self.snapshot_failed:
            return False
        for st in steps:
            if st.op != "click":
                continue
            src_id = self.k.actions[st.replay_of].source_obs if st.replay_of in self.k.actions else (
                r.target if r else self.live)
            src = self.k.obs.get(src_id)
            if self.gate.check(st, src.record.url if src else None, verified):
                return False
        return True

    def _minimal(self, q: Question, aff_ids: list[str]) -> bool:
        disabled = {c.subject for c in self.k.claims.get("observed_disabled", [])}
        return q.id not in self.st.minimal_failed and not any(a in disabled for a in aff_ids)

    def _snapshot(self, src: str) -> Restore | None:
        if not (self.iso.snapshot and self.iso.level >= 3) or self.snapshot_failed:
            return None
        info = self.k.obs[src]
        steps = [Step(op="snapshot", role=info.record.role, purpose="restore")] + [_replay(t) for t in info.trail]
        return Restore(kind="snapshot", steps=steps, cost=sum(getattr(self.costs, s.op) for s in steps), target=src,
                       independent=True)

    def _at(self, targets, minimal: bool, same_context: bool = False):
        r = restore(self.k, self.live, [o for o, _ in targets], self.iso, self.costs, minimal=minimal)
        if r is None or (same_context and r.kind not in {"stay", "back", "epoch_goto"}):
            return None
        return r.steps + [Step(op="click", affordance=dict(targets)[r.target])], r, {}

    # ----------------------------------------------------------------------- design
    def _design(self, q: Question):
        k = self.k
        acts = [q.extra["action"]] if "action" in q.extra else []
        aff_ids = [k.aff_of_action[a] for a in acts if a in k.aff_of_action] + [x for x in q.subject_ids if x in k.affs]
        minimal = self._minimal(q, aff_ids)
        if q.kind == "find_entry_point":
            return [Step(op="fresh", role=q.extra["role"])], None, {}
        if q.kind == "revisit":
            return self._revisit_plan(q.extra["obs"])
        if q.kind == "bind_affordance":
            aid = q.subject_ids[0]
            targets = enabled_targets(k, aid)
            if "{id}" in k.affs[aid].family["target_route"]:
                route = k.affs[aid].family["target_route"].split("?")[0]
                seen = {instance_of(k.obs[o].record.url) for t in k.templates.values() if t.route == route
                        for o in k.obs_of_template.get(t.id, [])}
                targets = [(o, a) for o, a in targets if instance_of(a.target) in seen] or targets
            return self._at(targets, minimal) if targets else None
        if q.kind in {"sample_instance", "split_test"}:
            return self._at(q.targets, minimal) if q.targets else None
        if q.kind in {"reproduce", "test_equivalence"}:
            src, aff = q.targets[0]
            r = self._snapshot(src) if k.cap_writes(q.subject_ids[0]) else \
                restore(k, self.live, [src], self.iso, self.costs, independent=True, minimal=minimal)
            if r is None:
                return None
            return r.steps + [Step(op="click", affordance=aff, replay_of=q.extra["action"])], r, {}
        if q.kind == "verify_effect":
            src, aff = q.targets[0]
            act = q.extra["action"]
            if q.extra["oracle"] == "paired_search":
                r = restore(k, self.live, [src], self.iso, self.costs, independent=True, minimal=minimal)
                if r is None:
                    return None
                back = [Step(op="goto", url=k.obs[src].record.url, purpose="oracle")] \
                    if k.obs[src].doc_entry else [s.model_copy(update={"purpose": "oracle"}) for s in r.steps]
                steps = r.steps + [Step(op="click", affordance=aff, replay_of=act, input="primary",
                                        oracle_capture="before_after")] + back + \
                    [Step(op="click", affordance=aff, replay_of=act, input="contrast", oracle_capture="before_after")]
                return steps, r, {"oracle": "paired_search", "oracle_action": act}
            r = self._snapshot(src)
            coll = self._collection_view(src)
            if r is None or coll is None:
                return None
            steps = r.steps + [Step(op="click", affordance=aff, replay_of=act, oracle_capture="after"),
                               Step(op="goto", url=k.obs[coll].record.url, oracle_capture="after", purpose="oracle")]
            return steps, r, {"oracle": "cross_view", "oracle_action": act}
        if q.kind == "test_dependency":
            r = restore(k, self.live, [o for o, _ in q.targets], self.iso, self.costs, independent=True,
                        minimal=minimal)
            if r is None:
                return None
            return r.steps + [Step(op="click", affordance=dict(q.targets)[r.target], replay_of=q.extra["action"])], r, {}
        return None

    def _collection_view(self, src: str) -> str | None:
        """A page-load view of another template that lists links to the created record's template."""
        k = self.k
        detail_routes = {path_route(urlsplit(k.obs[src].record.url or "").path)}
        for c in k.caps.values():
            for e in c.effects:
                if e.kind == "navigated" and e.target in k.templates:
                    detail_routes.add(k.templates[e.target].route)
        src_tpl = k.tpl_of_obs.get(src)
        for oid in reversed(k.order):
            info = k.obs[oid]
            if not info.doc_entry or k.tpl_of_obs.get(oid) in {None, src_tpl}:
                continue
            routes = {path_route(urlsplit(a.target).path) for a in info.record.affordances or [] if a.target}
            if any("{id}" in r and r in detail_routes for r in routes):
                return oid
        return None

    # ------------------------------------------------------------------- questions
    def _revisits(self) -> list[Question]:
        """Pages with a control seen disabled, after a state change in the same area in the live context.

        The revisit navigates in the live context (page loads only; no request is re-sent), so a
        prerequisite satisfied in this session can show up as an enabled control.
        """
        if self.variant == "no_local":
            return []
        k, live = self.k, self.k.obs[self.live]
        epoch = live.epoch
        latest: dict[str, str] = {}
        for oid in k.order:
            if oid in k.tpl_of_obs:
                latest[k.tpl_of_obs[oid]] = oid
        out = []
        for tid, oid in sorted(latest.items()):
            if oid == self.live or self.revisits[(epoch, tid)] >= TOUR["revisit_limit"]:
                continue
            disabled = [aid for aid, a in k.occurrences(oid) if a.disabled]
            if not disabled or k.obs[oid].record.role != live.record.role:
                continue
            area = area_of(k, tid)
            later = k.order[k.order.index(oid) + 1:]
            changed = any(k.obs[o].via is not None and k.obs[o].via.stateful and k.obs[o].epoch == epoch
                          and area_of(k, k.tpl_of_obs.get(o, "")) == area for o in later)
            if changed:
                out.append(Question(id=f"revisit:{tid}:{epoch}:{self.revisits[(epoch, tid)]}", kind="revisit",
                                    area=area, subject_ids=[tid], claim=f"availability:{tid}",
                                    evidence_ids=[k.obs[oid].record.id], outcomes=["enabled", "unchanged"],
                                    extra={"obs": oid, "template": tid, "disabled": disabled}))
        return out

    def _revisit_plan(self, oid: str):
        """Navigate to the page of `oid` in the live context: a direct URL when addressable, else the
        start URL plus the page-load steps of its trail. Never a fresh context."""
        k = self.k
        from .designer import _gotoable, minimal_trail
        info = k.obs[oid]
        if _gotoable(k, oid):
            steps = [Step(op="goto", url=info.record.url)]
        else:
            nav = [t for t in minimal_trail(list(info.trail)) if not t.sent and not t.writes]
            if any(t.op == "back" for t in nav):
                return None
            steps = [Step(op="goto", url=self.iso.start_url, purpose="restore")] + \
                [_replay(t) for t in nav]
            steps[-1] = steps[-1].model_copy(update={"purpose": "experiment"})
        return steps, Restore(kind="same_context_nav", steps=steps[:-1], cost=len(steps) - 1, target=oid,
                              independent=False), {}

    def _chain_affs(self) -> set[str]:
        """Controls newly enabled in the live context after being seen disabled in it (witnessed progress)."""
        epoch = self.k.obs[self.live].epoch
        return {aff for (e, aff), c in self.chains.items() if e == epoch and not c["executed"]}

    def _scan_availability(self) -> None:
        """Record chain events: disabled observation -> preceding actions -> enabled observation (same context)."""
        k = self.k
        for oid in k.order[self._last_obs_seen:]:
            info = k.obs[oid]
            for aid, a in k.occurrences(oid):
                key = (info.epoch, aid)
                if a.disabled:
                    self.disabled_seen.setdefault(key, oid)
                    self.disabled_any.setdefault(aid, oid)
                elif key not in self.chains and (key in self.disabled_seen or aid in self.disabled_any):
                    same_context = key in self.disabled_seen
                    first = self.disabled_seen[key] if same_context else next(
                        (o for o in k.order if k.obs[o].epoch == info.epoch), oid)
                    between = k.order[k.order.index(first) + 1:k.order.index(oid) + 1]
                    acts = [k.obs[o].via.action for o in between if k.obs[o].via is not None and k.obs[o].via.stateful]
                    writes = any(k.obs[o].via.writes for o in between if k.obs[o].via is not None)
                    self.chains[key] = {
                        "disabled_obs": k.obs[self.disabled_seen.get(key, self.disabled_any.get(aid))].record.id,
                        "enabled_obs": info.record.id, "same_context": same_context,
                        "preceding_actions": acts, "candidate_claim": f"{aid} requires effect of {acts[-1:] or acts}",
                        "executed": False, "same_page": k.tpl_of_obs.get(first) == k.tpl_of_obs.get(oid),
                        "already_bound": k.affs[aid].status in {"bound", "executed_no_effect"} if aid in k.affs else False,
                        "to_verify": ("two-arm test from a fresh context replaying the preceding steps" +
                                      ("; needs a verified L3 snapshot (a preceding step writes)" if writes else ""))}
        self._last_obs_seen = len(k.order)

    # ------------------------------------------------------------------- mode
    def _structure_evidence(self) -> dict[str, Any]:
        k = self.k
        n = sum(self.binds.values())
        fams: Counter = Counter()
        for a in k.affs.values():
            fams[(a.template_id, a.family["locator"].split(":nth")[0], a.family["kind"])] += 1
        repeated = sum(1 for a in k.affs.values() if "{id}" in a.family["target_route"] or
                       fams[(a.template_id, a.family["locator"].split(":nth")[0], a.family["kind"])] > 1)
        return {"bindings": n, "unique_share": round(self.binds["NEW"] / n, 3) if n else None,
                "repeated_share": round(repeated / max(1, len(k.affs)), 3),
                "instance_templates": sum("{id}" in t.route for t in k.templates.values()),
                "disabled_controls": len(k.claims.get("observed_disabled", [])),
                "chain_events": len(self.chains)}

    def _update_mode(self) -> None:
        ev = self._structure_evidence()
        if ev["bindings"] < TOUR["fallback_min_binds"]:
            return
        flat = (ev["unique_share"] >= TOUR["fallback_unique"] and ev["repeated_share"] < TOUR["fallback_repeated"]
                and ev["instance_templates"] == 0 and ev["disabled_controls"] == 0 and ev["chain_events"] == 0)
        mode = "breadth" if flat else "tours"
        if mode != self.mode:
            self.mode_log.append({"t": len(self.log), "from": self.mode, "to": mode, "evidence": ev})
            self.mode = mode

    # ------------------------------------------------------------------- choose
    def next(self, view: AgentView) -> ExperimentPlan | None:
        if not self.started:
            self.started = True
            self.k.start(view.records)
        self.live, self.used = view.live_obs, view.used
        self.k.refresh(view.acg)
        self.gate.observe(view.records)
        if self.pending is not None:
            self._resolve()
        self._scan_availability()
        self._update_mode()
        qs = generate(self.k, self.st, self.iso) + self._revisits()
        for q in qs:
            if q.id in self.external_blocked and not q.blocked_reason:
                q.blocked_reason = self.external_blocked[q.id]
        if self.variant == "v2":
            qs = self._dedupe_global(qs)
            for q in qs:
                if q.kind in VERIFICATION and not q.blocked_reason and self._unrestorable(q):
                    q.blocked_reason = "blocked_unrestorable_context"
                elif q.id in self.no_oracle and not q.blocked_reason:
                    q.blocked_reason = "oracle_not_applicable"
                elif q.id in self.no_reproduce and not q.blocked_reason:
                    q.blocked_reason = "not_reproduced_independently"
        disc = [q for q in qs if q.kind in DISCOVERY and not q.blocked_reason]
        verif = [q for q in qs if q.kind in VERIFICATION]
        for q in verif:
            if q.blocked_reason:
                self.blocked_q.setdefault(q.id, q.blocked_reason)
        new_tpls = set(self.k.templates) - self.seen_templates
        for t in sorted(new_tpls):
            self.new_q_per_template.append(sum(1 for q in disc if q.kind == "bind_affordance"
                                               and self.k.affs[q.subject_ids[0]].template_id == t))
        self.seen_templates |= new_tpls
        planned: dict[str, Any] = {}

        def plan(q: Question):
            if q.id not in planned:
                d = self._design(q)
                planned[q.id] = d if d is not None and self._gate_ok(d[0], d[1]) else None
            return planned[q.id]
        choice, reason, considered = self._choose(disc, verif, plan, view)
        if choice is None:
            self._end_tour("no_useful_permitted_action")
            self.log.append({"t": len(self.log), "stop": "no_feasible_question", "open": len(disc) + len(verif),
                             "mode": self.mode})
            return None
        q, (steps, r, extra) = choice
        self._track_tour(q, r, reason)
        entry = {"t": len(self.log), "mode": self.mode, "live_view": self.k.view_of_obs.get(self.live),
                 "tour": self.tour["id"] if self.tour else None, "reason": reason,
                 "chosen": {"q": q.id, "kind": q.kind, "evidence": q.evidence_ids, "risk": q.risk, "tier": q.risk_tier,
                            "restoration": {"kind": r.kind if r else "none", "actions": r.cost if r else 0},
                            "plan_actions": sum(getattr(self.costs, s.op) for s in steps)},
                 "considered": considered, "open_discovery": len(disc), "open_verification": len(verif),
                 "verification_share": round(self.verif_actions / max(1, self.used), 4)}
        self.log.append(entry)
        self.pending = {"q": q, "entry": entry, "caps_before": set(self.k.caps), "steps": steps,
                        "target_obs": r.target if r is not None else self.live}
        return ExperimentPlan(question_id=q.id, kind=q.kind, steps=steps, oracle=extra.get("oracle"),
                              oracle_action=extra.get("oracle_action"))

    def _cost(self, d) -> int:
        return sum(getattr(self.costs, s.op) for s in d[0])

    def _context_valuable(self) -> bool:
        if self.variant == "no_local":
            return False
        return bool(self._chain_affs()) or any(q.kind == "revisit" for q in self._revisits())

    def _choose(self, disc, verif, plan, view):
        considered: dict[str, Any] = {}
        live_tpl = self.k.tpl_of_obs.get(self.live)
        on_tpl = Counter(self.k.affs[q.subject_ids[0]].template_id for q in disc if q.kind == "bind_affordance")
        avg_new = (sum(self.new_q_per_template) / len(self.new_q_per_template)) if self.new_q_per_template else 1.0

        feasible = []
        for q in disc:
            d = plan(q)
            if d is not None:
                feasible.append((q, d))
        considered["feasible_discovery"] = len(feasible)
        considered["infeasible_discovery"] = len(disc) - len(feasible)
        disc_choice, disc_reason = self._discover(feasible, considered, on_tpl, avg_new)
        share = self.verif_actions / max(1, self.used)
        queued = [q for q in verif if not q.blocked_reason]
        due = None
        if queued:
            vplans = [(q, plan(q)) for q in queued]
            ok = [(q, d) for q, d in vplans if d is not None]
            for q, d in vplans:
                if d is None:
                    self.blocked_q.setdefault(q.id, self._block_reason(q))
            est = sum(self._cost(d) for _, d in ok)
            if disc_choice is None:
                due = "discovery_exhausted"
            elif share < TOUR["verify_max_share"] and ok:
                if view.remaining <= min(TOUR["verify_reserve"] * self.budget, est):
                    due = "end_of_budget_reserve"
                elif self.mode == "tours" and self.variant != "no_local" and disc_reason.startswith("move") \
                        and share < TOUR["verify_min_share"] and not self._context_valuable():
                    due = "tour_boundary"
                elif self.variant == "no_local" and share < TOUR["verify_min_share"]:
                    due = "fixed_share"
            if due and ok:
                ok.sort(key=lambda x: (KIND_ORDER[x[0].kind] > 6, self._cost(x[1]), x[0].id))
                considered["verification_top"] = [(q.id, self._cost(d)) for q, d in ok[:3]]
                return ok[0], "verify:" + due, considered
        if disc_choice is None:
            return None, "", considered
        return disc_choice, disc_reason, considered

    def _discover(self, feasible, considered, on_tpl, avg_new):
        def yld(q: Question, d) -> float:
            if q.kind == "bind_affordance":
                aff = self.k.affs[q.subject_ids[0]]
                route = aff.family["target_route"].split("?")[0]
                unseen = route and not any(t.route == route for t in self.k.templates.values())
                return 1 + (on_tpl[aff.template_id] - 1) + (avg_new if unseen else 0)
            if q.kind == "revisit":
                return float(len(q.extra["disabled"]))
            return 1.0

        if not feasible:
            return None, ""
        tier = min(q.risk_tier for q, _ in feasible)
        considered["deferred_by_tier"] = sum(q.risk_tier > tier for q, _ in feasible)
        feasible = [(q, d) for q, d in feasible if q.risk_tier == tier]

        def local(item) -> bool:
            r = item[1][1]
            return r is not None and r.kind in {"stay", "back"} or (r is None and item[0].kind != "find_entry_point")

        chain = self._chain_affs()
        live_affs = {aid for aid, _ in self.k.occurrences(self.live)}
        prev = self.k.obs[self.live].prev
        prev_affs = {aid for aid, _ in self.k.occurrences(prev)} if prev in self.k.obs else set()

        def cls(item) -> int:
            q = item[0]
            if self.variant != "no_local" and q.kind == "bind_affordance" and q.subject_ids[0] in chain and local(item):
                return 0                                   # witnessed prerequisite progress
            if self.variant != "no_local" and q.kind == "bind_affordance" and q.subject_ids[0] in live_affs - prev_affs \
                    and local(item):
                return 1                                   # newly revealed on the live view
            return 2 if local(item) else 3

        def value(item) -> float:
            return yld(item[0], item[1]) / max(1, self._cost(item[1]))

        def key(item):
            return (cls(item), -value(item), self._cost(item[1]), KIND_ORDER[item[0].kind], self._perm(item[0].id))

        locals_ = [x for x in feasible if cls(x) <= 2]
        remote = [x for x in feasible if cls(x) == 3]
        if self.mode == "breadth":
            # Fallback: legacy-style local burst, then breadth-first order over the agenda
            # (earliest-observed question first), cheapest restoration; same question pool.
            if locals_ and (self.tour is None or self.tour["length"] < 8):
                best = min(locals_, key=lambda x: (cls(x), self._first_seen(x[0]), self._perm(x[0].id)))
                return best, "breadth:local"
            best = min(feasible, key=lambda x: (self._first_seen(x[0]), self._cost(x[1]), self._perm(x[0].id)))
            return best, "breadth:order"
        if self.variant == "no_local":
            best = min(feasible, key=lambda x: (-value(x), self._cost(x[1]), KIND_ORDER[x[0].kind],
                                                self._perm(x[0].id)))
            return best, "global:cost_aware"
        protect = self._context_valuable()
        if protect:
            same_ctx = [x for x in remote if x[1][1] is None or x[1][1].kind in {"stay", "back", "epoch_goto"}]
            if same_ctx:
                remote = same_ctx
        best_local = min(locals_, key=key) if locals_ else None
        if remote:
            best_remote = self._uniform(remote) if self.uniform_global else min(remote, key=key)
        else:
            best_remote = None
        considered["top"] = [(q.id, cls((q, d)), round(value((q, d)), 3), self._cost(d))
                             for q, d in sorted(feasible, key=key)[:3]]
        if best_local is not None:
            length = self.tour["length"] if self.tour else 0
            interrupt = best_remote is not None and not self.uniform_global and cls(best_local) == 2 and \
                value(best_remote) >= TOUR["material"] * value(best_local)
            if (length < TOUR["max_length"] or cls(best_local) == 0) and not interrupt:
                return best_local, ("continue:" if self.tour else "start:") + \
                    ("prerequisite_progress", "revealed_control", "local_question")[cls(best_local)]
            if best_remote is None:
                self._end_tour("max_length")
                return best_local, "start:local_question_after_bound"
            self._end_tour("max_length" if not interrupt else "remote_materially_better")
        self._end_tour("no_local_questions")
        return best_remote, "move:" + ("protected_context" if protect else "cost_aware_coverage"
                                       if not self.uniform_global else "uniform")

    def _first_seen(self, q: Question) -> int:
        evidence = [self.k.order.index(o) for o in self.k.obs_of_template.get(
            self.k.affs[q.subject_ids[0]].template_id if q.subject_ids and q.subject_ids[0] in self.k.affs else "", [])[:1]]
        return evidence[0] if evidence else len(self.k.order)

    def _block_reason(self, q: Question) -> str:
        if self.k.cap_writes(q.subject_ids[0]) if q.subject_ids and q.subject_ids[0] in self.k.caps else False:
            if self.snapshot_failed:
                return "unverified_start_state"
            return "write_needs_verified_snapshot" if not self.iso.snapshot else "write_plan_unavailable"
        return "no_independent_route"

    # ----------------------------------------------------------------- tours
    def _track_tour(self, q: Question, r: Restore | None, reason: str) -> None:
        if q.kind in VERIFICATION:
            self._end_tour("verification")
            return
        if (reason.startswith("continue") or reason == "breadth:local") and self.tour:
            self.tour["length"] += 1
            self.tour["reasons"][reason.split(":")[1]] += 1
            return
        self._end_tour("moved")
        self.tour = {"id": len(self.tours), "start_reason": reason, "area": q.area,
                     "epoch": self.k.obs[self.live].epoch, "length": 1, "reasons": Counter()}

    def _end_tour(self, why: str) -> None:
        if self.tour is not None:
            self.tour["end_reason"] = why
            self.tour["reasons"] = dict(self.tour["reasons"])
            self.tours.append(self.tour)
            self.tour = None

    # --------------------------------------------------------------- outcomes
    def update(self, plan: ExperimentPlan, result: ExperimentResult, view: AgentView) -> None:
        self.k.ingest(plan, result, self.live)
        if plan.kind in VERIFICATION:
            self.verif_actions += result.actions
        if self.pending is not None:
            self.pending["result"] = result

    def _resolve(self) -> None:
        pend, self.pending = self.pending, None
        q, result, entry = pend["q"], pend.get("result"), pend["entry"]
        if result is None:
            return
        k, outcome = self.k, "inconclusive"
        if result.abort_reason == "unverified_start_state":
            self.snapshot_failed = True
            self.blocked_q[q.id] = "unverified_start_state"
        if result.abort_reason in {"control_not_found", "control_disabled"}:
            self.st.minimal_failed.add(q.id)
        if q.kind == "bind_affordance":
            act = k.actions.get(result.action_ids[-1]) if result.action_ids else None
            if act is None:
                self.st.inconclusive[q.id] += 1
            elif act.status != "observed":
                outcome = "FAIL"
                self.st.family_out[q.family]["FAIL"] += 1
                self.st.inconclusive[q.id] += 1
            else:
                cap = k.cap_of_action.get(act.action_id)
                outcome = "NEW" if cap and cap not in pend["caps_before"] else ("KNOWN" if cap else "NO_EFFECT")
                self.st.family_out[q.family][cap or "NO_EFFECT"] += 1
                epoch = k.obs[act.source_obs].epoch if act.source_obs in k.obs else -1
                if (epoch, q.subject_ids[0]) in self.chains:
                    self.chains[(epoch, q.subject_ids[0])]["executed"] = True
                    self.chains[(epoch, q.subject_ids[0])]["executed_action"] = act.id
            self.binds[outcome] += 1
        elif q.kind == "revisit":
            self.revisits[(k.obs[self.live].epoch if self.live in k.obs else -1, q.extra["template"])] += 1
            outcome = "observed"
        elif q.kind in {"split_test", "sample_instance"}:
            outcome = "executed" if result.completed else "inconclusive"
            if q.kind == "split_test" and result.completed:
                self.st.split_done[q.subject_ids[0]].add(q.extra["instance"])
            if not result.completed:
                self.st.inconclusive[q.id] += 1
        elif q.kind in VERIFICATION:
            outcome = "executed" if result.completed else "inconclusive"
            self.verif_log.append((q.kind, q.subject_ids[0] if q.subject_ids else "", result.actions,
                                   result.completed))
            if self.variant == "v2" and result.abort_reason in {"control_not_found", "control_disabled"}:
                self.unrestorable.add(q.id)      # the session state it needs could not be rebuilt
            if self.variant == "v2" and q.kind == "verify_effect" and result.completed and \
                    q.extra.get("oracle") == "paired_search" and not self._differential(result):
                self.no_oracle.add(q.id)         # observed: the contrast pair adds no distinguishable results
            if self.variant == "v2" and q.kind == "reproduce" and result.completed:
                rep = next((r for r in reversed(result.records) if r.kind == "replay"
                            and r.action_id == q.extra.get("action")), None)
                cap = k.caps.get(q.subject_ids[0])
                if rep is not None and rep.status == "replay_validated" and cap is not None and \
                        STATUS_RANK.get(cap.status, -1) < STATUS_RANK[Status.REPRODUCED]:
                    self.no_reproduce.add(q.id)  # a conclusive mismatch, not noise: do not retry
            # At most two attempts per verification item: an item that is still open afterwards is
            # recorded as blocked (inconclusive) with its evidence, not retried indefinitely.
            self.st.inconclusive[q.id] += 1
            if q.kind in {"test_dependency", "test_equivalence"} and result.completed:
                self.st.tested_claims.add(q.id)
        else:
            outcome = "executed" if result.completed else "inconclusive"
        entry.update({"actual_actions": result.actions, "abort": result.abort_reason, "outcome": outcome,
                      "new_records": [r.id for r in result.records][-3:]})

    # ----------------------------------------------------------------- report
    def summary(self) -> dict[str, Any]:
        tours = self.tours + ([self.tour] if self.tour else [])
        chains = list(self.chains.values())
        return {
            "mode_switches": self.mode_log, "final_mode": self.mode, "tours": len(tours),
            "mean_tour_length": round(sum(t["length"] for t in tours) / len(tours), 2) if tours else 0,
            "tour_end_reasons": dict(Counter(t.get("end_reason", "open") for t in tours)),
            "chain_events": len(chains), "chain_continuations_executed": sum(c["executed"] for c in chains),
            "chain_events_cross_page": sum(not c["same_page"] for c in chains),
            "chain_events_across_contexts": sum(not c["same_context"] for c in chains),
            "chain_events_not_executed": sum(not c["executed"] and not c["already_bound"] for c in chains),
            "revisits": sum(self.revisits.values()), "verification_actions": self.verif_actions,
            "verification_blocked": len(self.blocked_q),
            "verification_blocked_reasons": dict(Counter(self.blocked_q.values())),
            "snapshot_failed": self.snapshot_failed,
            "bind_outcomes": dict(self.binds), "chains": chains[:20],
            "verification_wasted_actions": self._wasted(),
            "global_navigation_suppressed": len(self.global_suppressed),
        }

    def decisions(self) -> list[dict[str, Any]]:
        return self.log

    # ------------------------------------------------------------ v2 additions
    def _wasted(self) -> int:
        """Verification actions spent on items that did not reach their target status by the end."""
        goal = {"reproduce": Status.REPRODUCED, "verify_effect": Status.VERIFIED}
        out = 0
        for kind, subject, actions, completed in self.verif_log:
            cap = self.k.caps.get(subject)
            if kind in goal:
                reached = cap is not None and STATUS_RANK.get(cap.status, -1) >= STATUS_RANK[goal[kind]]
            else:
                reached = completed
            out += 0 if reached else actions
        return out

    def _differential(self, result: ExperimentResult) -> bool:
        """Whether a paired-search experiment showed results that differ between the two inputs."""
        rep = next((r for r in result.records if r.kind == "replay" and r.verification_kind == "paired_search"), None)
        ids = (rep.verification or {}).get("verification_observation_ids", []) if rep else []
        obs = {r.obs_id: r for r in result.records if r.kind == "observation"}
        if len(ids) != 4 or not all(i in obs for i in ids):
            return False
        t = lambda o: {a.target for a in o.affordances or [] if a.target}
        b1, r1, b2, r2 = (obs[i] for i in ids)
        primary, contrast = t(r1) - t(b1), t(r2) - t(b2)
        return primary != contrast and bool(primary or contrast)

    def _global_key(self, aff) -> tuple | None:
        f = aff.family
        route = f["target_route"].split("?")[0]
        if not route:
            return None          # untargeted controls are never assumed global
        role = self.k.templates[aff.template_id].role if aff.template_id in self.k.templates else ""
        return (role, f["kind"], f["interaction"], f["component"], f["locator"].split(":nth")[0], route, f["method"],
                tuple(tuple(x) for x in f["fields"]))

    def _dedupe_global(self, qs: list[Question]) -> list[Question]:
        """One binding question per globally available control family (seen on >= 2 templates).

        Equivalence across templates is a recorded, reversible hypothesis: once any member is
        bound, the other members' binding questions are suppressed, not marked bound.
        """
        groups: dict[tuple, set[str]] = defaultdict(set)
        bound: set[tuple] = set()
        for a in self.k.affs.values():
            key = self._global_key(a)
            if key is None:
                continue
            groups[key].add(a.template_id)
            if a.status in {"bound", "executed_no_effect"}:
                bound.add(key)
        out = []
        for q in qs:
            if q.kind == "bind_affordance" and not q.blocked_reason:
                key = self._global_key(self.k.affs[q.subject_ids[0]])
                if key is not None and len(groups[key]) >= 2 and key in bound:
                    self.global_suppressed.add(q.id)
                    continue
            out.append(q)
        return out

    def _unrestorable(self, q: Question) -> bool:
        """Independent replay would need session state that cannot be rebuilt safely."""
        if q.id in self.unrestorable:
            return True
        if not q.targets or q.targets[0][0] not in self.k.obs:
            return False
        subject = q.subject_ids[0] if q.subject_ids else ""
        if subject in self.k.caps and self.k.cap_writes(subject):
            return False         # write verification is governed by snapshot availability, reported separately
        trail = self.k.obs[q.targets[0][0]].trail
        snapshot = self.iso.snapshot and self.iso.level >= 3 and not self.snapshot_failed
        acts = [q.extra["action"]] if "action" in q.extra else []
        affs = [self.k.aff_of_action[a] for a in acts if a in self.k.aff_of_action]
        dependent = any(c.subject in affs for c in self.k.claims.get("observed_disabled", []))
        return dependent and any(t.writes for t in trail) and not snapshot


def make_tour(name: str):
    mode = {"tour_full": "full", "tour_no_local": "no_local", "tour_no_global": "no_global", "tour_v2": "v2"}[name]

    def factory(isolation, costs, budget, seed=0):
        return TourScheduler(isolation, costs, budget, seed, mode=mode)
    return factory
