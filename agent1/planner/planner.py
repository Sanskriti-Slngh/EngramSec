"""Question-driven exploration planner (EXPLORATION_PLANNER_DESIGN.md §4–§6).

Each decision:
1. refresh indexes from the ACG materialized over the planner's own evidence;
2. resolve the previous experiment's outcome from that evidence (never from
   beliefs) and update run-local counts, posteriors and the area allocator;
3. generate questions (questions.py);
4. choose a question: class floors, then area floor, then discounted-UCB
   area; lowest permitted risk tier; highest (EIG + λ·Unlock) / Cost;
5. design the experiment (designer.py) and log the decision with its
   predictions before execution.

Modes, sharing everything else: `full`; `no_unlock` (λ = 0); `uniform`
(seeded uniform choice inside the same pool instead of value ranking).
The planner never reads display labels or the environment.
"""
from __future__ import annotations

import hashlib
import math
import statistics
from collections import Counter, defaultdict
from typing import Any

from agent1.model.schema import STATUS_RANK, Status

from .allocator import Allocator
from .constants import (AGENDA_CAP_PER_AREA, CHANNELS, EPS_ENV_INITIAL, LAMBDA_UNLOCK, MAX_INCONCLUSIVE,
                        SATURATION_MIN_N, SATURATION_P_NEW, SATURATION_VALUE_FRACTION)
from .designer import Restore, restore
from .gate import RiskGate
from .interfaces import AgentView, ExperimentPlan, ExperimentResult, Step
from .knowledge import Knowledge
from .questions import Question, area_of, enabled_targets, generate, instance_of
from .value import bayes, bind_distribution, binary_eig, h, hb, kl_bernoulli, run_local_prior


class RunState:
    """Run-local counts and posteriors. Nothing carries over between runs."""

    def __init__(self) -> None:
        self.kind_attempts: Counter = Counter()
        self.kind_fails: Counter = Counter()
        self.area_sigs: dict[str, Counter] = defaultdict(Counter)
        self.family_sigs: dict[tuple, Counter] = defaultdict(Counter)
        self.claim_p: dict[str, float] = {}
        self.tested: Counter = Counter()
        self.confirmed: Counter = Counter()
        self.inconclusive: Counter = Counter()
        self.tested_claims: set[str] = set()
        self.split_done: dict[str, set] = defaultdict(set)
        self.eps_trials = self.eps_mismatch = 0
        self.enable_trials = self.enable_events = 0
        self.yields: list[float] = []
        self.minimal_failed: set[str] = set()

    def eps(self) -> float:
        """ε_env: mismatching reproductions of REPRODUCED read-only capabilities (starts at 0.10)."""
        return min(0.5, (self.eps_mismatch + EPS_ENV_INITIAL * 10) / (self.eps_trials + 10))

    def area_n(self, area: str) -> int:
        return sum(self.area_sigs[area].values())

    def area_f1(self, area: str) -> int:
        return sum(1 for c in self.area_sigs[area].values() if c == 1)

    def family_allows(self, fam: tuple) -> bool:
        sigs = {s: c for s, c in self.family_sigs[fam].items() if s != "FAIL"}
        n = sum(sigs.values())
        return n == 0 or (sum(1 for c in sigs.values() if c == 1) + 1) / (n + 2) >= SATURATION_P_NEW

    @staticmethod
    def locator_order(aff) -> tuple:
        import re
        return tuple(int(x) for x in re.findall(r"\((\d+)\)", aff.family["locator"]))

    def prior(self, kind: str) -> float:
        return run_local_prior(self.confirmed[kind], self.tested[kind])

    def instance_links(self, k: Knowledge, t, sampled: set) -> list:
        out = []
        for aff in sorted(k.affs.values(), key=lambda a: a.id):
            if aff.family["target_route"].split("?")[0] != t.route or k.templates[aff.template_id].role != t.role:
                continue
            for oid in k.obs_of_template.get(aff.template_id, []):
                for aid, a in k.occurrences(oid):
                    if aid == aff.id and a.safe and not a.disabled and instance_of(a.target) not in sampled:
                        out.append((oid, a))
                        break
        return out


def _claim_kind(q: Question) -> str:
    return {"reproduce": "reproducible", "verify_effect": "oracle", "sample_instance": "uniform",
            "split_test": "uniform", "test_dependency": "requires", "test_equivalence": "equivalent",
            "find_entry_point": "entry"}.get(q.kind, q.kind)


def _targets(o) -> set[str]:
    return {a.target for a in o.affordances or [] if a.target}


class Planner:
    uses_acg = True

    def __init__(self, isolation, costs, budget: int, seed: int = 0, mode: str = "full") -> None:
        self.iso, self.costs, self.seed, self.mode = isolation, costs, seed, mode
        self.name = {"full": "acg_full", "no_unlock": "acg_no_unlock", "uniform": "acg_uniform"}[mode]
        self.k = Knowledge()
        self.st = RunState()
        self.alloc = Allocator()
        self.started = False
        self.live: str | None = None
        self.pending: dict[str, Any] | None = None
        self.log: list[dict[str, Any]] = []
        self._uniform_draw = 0
        self.gate = RiskGate(isolation)          # same evidence-only rules as the executor's gate

    # ---------------------------------------------------------------------------- helpers
    def _perm(self, qid: str) -> str:
        return hashlib.sha256(f"{self.seed}:{qid}".encode()).hexdigest()

    def _channel(self, q: Question) -> tuple[float, float]:
        eps = self.st.eps()
        name = {"reproduce": "reproduce", "sample_instance": "split", "split_test": "split",
                "test_dependency": "dependency", "test_equivalence": "equivalence"}.get(q.kind)
        if q.kind == "verify_effect":
            name = "differential" if q.extra["oracle"] == "paired_search" else "cross_view"
        if q.kind == "find_entry_point":
            return 1.0, 0.0
        s, f = CHANNELS[name]
        if s is None:
            s = 1 - eps
        elif s == "squared":
            s = (1 - eps) ** 2
        return s, f

    def _posterior(self, q: Question) -> float:
        if q.kind == "reproduce":
            cap = self.k.caps[q.subject_ids[0]]
            tested = [c for c in self.k.caps.values() if c.reproduction_ids or self._against(c.id)]
            p = run_local_prior(sum(1 for c in tested if c.reproduction_ids), len(tested))
            s, f = self._channel(q)
            for _ in cap.reproduction_ids:
                p = bayes(p, True, s, f)
            for _ in range(self._against(cap.id)):
                p = bayes(p, False, s, f)
            return min(max(p, 1e-6), 1 - 1e-6)
        return self.st.claim_p.get(q.claim, self.st.prior(_claim_kind(q)))

    def _against(self, cap_id: str) -> int:
        for c in self.k.claims.get("has_behavior_signature", []):
            if c.subject == cap_id:
                return c.against
        return 0

    def _bind_dist(self, q: Question) -> dict[str, float]:
        aff = self.k.affs[q.subject_ids[0]]
        kind = aff.family["kind"]
        fam_counts = {s: c for s, c in self.st.family_sigs[q.family].items() if s != "FAIL"}
        return bind_distribution(self.st.kind_fails[kind], self.st.kind_attempts[kind], self.st.area_f1(q.area),
                                 self.st.area_n(q.area), fam_counts)

    def _p_fail(self, kind: str) -> float:
        return (self.st.kind_fails[kind] + 1) / (self.st.kind_attempts[kind] + 2)

    # --------------------------------------------------------------------------- design
    def _minimal(self, q: Question, aff_ids: list[str]) -> bool:
        """Shortened restoration only for controls never observed disabled (evidence), and not after it failed."""
        disabled = {c.subject for c in self.k.claims.get("observed_disabled", [])}
        return q.id not in self.st.minimal_failed and not any(a in disabled for a in aff_ids)

    def _design(self, q: Question) -> tuple[list[Step], Restore | None, dict[str, Any]] | None:
        k, live = self.k, self.live
        acts = [q.extra["action"]] if "action" in q.extra else []
        aff_ids = [k.aff_of_action[a] for a in acts if a in k.aff_of_action] + \
            [x for x in q.subject_ids if x in k.affs]
        minimal = self._minimal(q, aff_ids)
        if q.kind == "find_entry_point":
            return [Step(op="fresh", role=q.extra["role"], purpose="experiment")], None, {}
        if q.kind == "bind_affordance":
            aid = q.subject_ids[0]
            targets = enabled_targets(k, aid)
            if "{id}" in k.affs[aid].family["target_route"]:
                tpl_route = k.affs[aid].family["target_route"].split("?")[0]
                seen = {instance_of(k.obs[o].record.url) for t in k.templates.values() if t.route == tpl_route
                        for o in k.obs_of_template.get(t.id, [])}
                known = [(o, a) for o, a in targets if instance_of(a.target) in seen]
                targets = known or targets
            return self._at(targets, independent=False, minimal=minimal)
        if q.kind in {"sample_instance", "split_test"}:
            plan = self._at(q.targets, independent=False, minimal=minimal)
            if q.kind == "sample_instance":
                t = k.templates[q.extra["template"]]
                live_role = k.obs[live].record.role
                if t.id in k.reproduced_templates and t.role == live_role and q.targets:
                    url = q.targets[0][1].target
                    if plan is None or plan[1] is None or plan[1].cost > self.costs.goto:
                        return [Step(op="goto", url=url, purpose="experiment")], \
                            Restore(kind="direct_url", steps=[], cost=0, target=live, independent=False), {}
            return plan
        if q.kind in {"reproduce", "test_equivalence"}:
            src, aff = q.targets[0]
            writes = k.cap_writes(q.subject_ids[0])
            r = self._snapshot_restore(src) if writes else restore(k, live, [src], self.iso, self.costs,
                                                                   independent=True, minimal=minimal)
            if r is None:
                return None
            return r.steps + [Step(op="click", affordance=aff, replay_of=q.extra["action"])], r, {}
        if q.kind == "verify_effect":
            src, aff = q.targets[0]
            act = q.extra["action"]
            if q.extra["oracle"] == "paired_search":
                r = restore(k, live, [src], self.iso, self.costs, independent=True, minimal=minimal)
                if r is None:
                    return None
                second = [Step(op="goto", url=k.obs[src].record.url, purpose="oracle")] \
                    if k.obs[src].doc_entry and k.tpl_of_obs.get(src) in k.reproduced_templates else \
                    [s.model_copy(update={"purpose": "oracle"}) for s in r.steps]
                steps = r.steps + [Step(op="click", affordance=aff, replay_of=act, input="primary",
                                        oracle_capture="before_after")] + second + \
                    [Step(op="click", affordance=aff, replay_of=act, input="contrast", oracle_capture="before_after")]
                return steps, r, {"oracle": "paired_search", "oracle_action": act,
                                  "oracle_actions": len(second) + 1}
            if not k.obs[src].doc_entry:
                return None
            r = self._snapshot_restore(src)
            if r is None:
                return None
            steps = r.steps + [Step(op="click", affordance=aff, replay_of=act, oracle_capture="after"),
                               Step(op="goto", url=k.obs[src].record.url, oracle_capture="after", purpose="oracle")]
            return steps, r, {"oracle": "cross_view", "oracle_action": act, "oracle_actions": 1}
        if q.kind == "test_dependency":
            r = restore(k, live, [o for o, _ in q.targets], self.iso, self.costs, independent=True, minimal=minimal)
            if r is None:
                return None
            aff = dict(q.targets)[r.target]
            return r.steps + [Step(op="click", affordance=aff, replay_of=q.extra["action"])], r, {}
        return None

    def _at(self, targets, independent: bool, minimal: bool = False):
        r = restore(self.k, self.live, [o for o, _ in targets], self.iso, self.costs, independent=independent,
                    minimal=minimal)
        if r is None:
            return None
        aff = dict(targets)[r.target]
        return r.steps + [Step(op="click", affordance=aff)], r, {}

    def _snapshot_restore(self, src: str) -> Restore | None:
        if not (self.iso.snapshot and self.iso.level >= 3):
            return None
        info = self.k.obs[src]
        from .designer import _replay
        steps = [Step(op="snapshot", role=info.record.role, purpose="restore")] + [_replay(t) for t in info.trail]
        return Restore(kind="snapshot", steps=steps, cost=sum(getattr(self.costs, s.op) for s in steps), target=src,
                       independent=True)

    # ---------------------------------------------------------------------------- value
    def _gate_ok(self, steps: list[Step], r: Restore | None) -> bool:
        """Predict the shared risk gate for every click of a plan from evidence (no refused attempts)."""
        verified = bool(steps) and steps[0].op == "snapshot"
        for st in steps:
            if st.op != "click":
                continue
            if st.replay_of and st.replay_of in self.k.actions:
                src = self.k.obs.get(self.k.actions[st.replay_of].source_obs)
            else:
                src = self.k.obs.get(r.target if r else self.live)
            if self.gate.check(st, src.record.url if src else None, verified):
                return False
        return True

    def _value(self, q: Question, blocked_by: dict[str, list[Question]]) -> dict[str, Any] | None:
        design = self._design(q)
        if design is None or not self._gate_ok(design[0], design[1]):
            return None
        steps, r, extra = design
        out: dict[str, Any] = {"steps": steps, "restore": r, "extra": extra}
        aff = q.targets[0][1] if q.targets and q.targets[0][1] is not None else None
        kind = self.k.affs[q.subject_ids[0]].family["kind"] if q.kind == "bind_affordance" else \
            (aff.kind if aff is not None else "context")
        p_fail = self._p_fail(kind)
        if q.kind == "bind_affordance":
            dist = self._bind_dist(q)
            eig = h(list(dist.values()))
            out.update(dist=dist, p_new=dist["NEW"])
            p_fail = dist["FAIL"]
        else:
            p = self._posterior(q)
            s, f = self._channel(q)
            eig = hb(p) if q.kind == "find_entry_point" else binary_eig(p, s, f)
            out.update(p=p, s=s, f=f)
        unlock, unlocks = 0.0, []
        if q.kind == "bind_affordance":
            node = self.k.affs[q.subject_ids[0]]
            blocked = blocked_by.get(f"disabled:{node.template_id}:{node.family['component']}", [])
            if blocked:
                p_ok = run_local_prior(self.st.enable_events, self.st.enable_trials)
                unlock = p_ok * sum(h(list(self._bind_dist(b).values())) for b in blocked)
                unlocks = [b.id for b in blocked]
        elif q.kind == "find_entry_point":
            blocked = blocked_by.get("auth", [])
            if blocked:
                unlock = self.st.prior("entry") * sum(h(list(self._bind_dist(b).values())) for b in blocked)
                unlocks = [b.id for b in blocked]
        restore_cost = r.cost if r else 0
        actions = sum(getattr(self.costs, s.op) for s in steps) - restore_cost
        oracle = extra.get("oracle_actions", 0)
        cost = (restore_cost + max(1, actions - oracle) + oracle) / max(1e-6, 1 - p_fail)
        lam = 0.0 if self.mode == "no_unlock" else LAMBDA_UNLOCK
        out.update(eig=eig, unlock=unlock, unlocks=unlocks, cost=cost, value=(eig + lam * unlock) / cost)
        return out

    # ----------------------------------------------------------------------- selection
    def next(self, view: AgentView) -> ExperimentPlan | None:
        if not self.started:
            self.started = True
            self.k.start(view.records)
        self.live = view.live_obs
        self.k.refresh(view.acg)
        self.gate.observe(view.records)
        if self.pending is not None:
            self._resolve()
        qs = generate(self.k, self.st, self.iso)
        open_q = [q for q in qs if not q.blocked_reason]
        blocked_by: dict[str, list[Question]] = defaultdict(list)
        for q in qs:
            if q.blocked_reason:
                blocked_by[q.blocked_reason].append(q)
        by_area: dict[str, list[Question]] = defaultdict(list)
        for q in open_q:
            by_area[q.area].append(q)
        evicted = 0
        for area, items in by_area.items():
            if len(items) > AGENDA_CAP_PER_AREA:
                items.sort(key=lambda q: (q.risk_tier, q.id))
                evicted += len(items) - AGENDA_CAP_PER_AREA
                del items[AGENDA_CAP_PER_AREA:]
        values: dict[str, dict[str, Any] | None] = {}

        def val(q: Question):
            if q.id not in values:
                values[q.id] = self._value(q, blocked_by)
            return values[q.id]

        saturated = {a for a in by_area if self._saturated(a, by_area[a], val)}
        live_areas = {a for a in by_area if a not in saturated}
        observed = sum(1 for c in self.k.caps.values() if STATUS_RANK.get(c.status, -1) >= 1)
        open_classes = {q.qclass for a in live_areas for q in by_area[a]}
        global_saturated = not any(q.qclass == "discovery" for a in live_areas for q in by_area[a])
        rule, pool, area = None, [], None
        for qclass in self.alloc.starved_classes(open_classes, observed, global_saturated):
            cands = [q for a in sorted(live_areas) for q in by_area[a] if q.qclass == qclass and val(q)]
            if cands:
                rule, pool = f"class_floor:{qclass}", cands
                break
        if not pool:
            disc = {q.area for a in live_areas for q in by_area[a] if q.qclass == "discovery"}
            starving = self.alloc.starving_areas(disc)
            order = starving + [a for a in self.alloc.ranked(live_areas) if a not in starving]
            for a in order:
                cands = [q for q in by_area[a] if val(q)]
                if cands:
                    rule = "area_floor" if a in starving else "ucb"
                    pool, area = cands, a
                    break
        if not pool:
            self.log.append({"t": len(self.log), "stop": "no_feasible_question", "open": len(open_q),
                             "saturated_areas": sorted(saturated)})
            return None
        tier = min(q.risk_tier for q in pool)
        deferred = sum(1 for q in pool if q.risk_tier > tier)
        pool = [q for q in pool if q.risk_tier == tier]
        ranked = sorted(pool, key=lambda q: (-val(q)["value"], val(q)["cost"], self._perm(q.id)))
        if self.mode == "uniform":
            ordered = sorted(pool, key=lambda q: q.id)
            idx = int(hashlib.sha256(f"{self.seed}:uniform:{self._uniform_draw}".encode()).hexdigest(), 16) % len(ordered)
            self._uniform_draw += 1
            chosen = ordered[idx]
        else:
            chosen = ranked[0]
        v = val(chosen)
        area = chosen.area
        self.alloc.note(area, chosen.qclass)
        top = [{"q": q.id, "kind": q.kind, "eig": round(val(q)["eig"], 6), "unlock": round(val(q)["unlock"], 6),
                "cost": round(val(q)["cost"], 6), "value": round(val(q)["value"], 6)} for q in ranked[:3]]
        entry = {
            "t": len(self.log), "live_view": self.k.view_of_obs.get(self.live), "area": area, "rule": rule,
            "open": len(open_q), "blocked": dict(sorted(Counter(q.blocked_reason.split(":")[0] for q in qs
                                                                 if q.blocked_reason).items())),
            "considered": len(values), "unreachable": sum(1 for x in values.values() if x is None),
            "deferred_by_tier": deferred, "tier": tier, "evicted": evicted, "top3": top,
            "chosen": {"q": chosen.id, "kind": chosen.kind, "claim": chosen.claim, "evidence": chosen.evidence_ids,
                       "eig": round(v["eig"], 6), "unlock": round(v["unlock"], 6), "unlocks": v["unlocks"][:5],
                       "cost": round(v["cost"], 6), "risk": chosen.risk, "tier": chosen.risk_tier,
                       "outcomes": chosen.outcomes,
                       "restoration": {"kind": v["restore"].kind if v["restore"] else "none",
                                       "actions": v["restore"].cost if v["restore"] else 0}},
            "rejected": "lower value" if self.mode != "uniform" else "uniform draw",
        }
        if chosen.kind == "bind_affordance":
            entry["p_new"] = round(v["p_new"], 6)
        self.log.append(entry)
        self.pending = {"q": chosen, "v": v, "caps_before": set(self.k.caps), "entry": entry,
                        "templates_before": set(self.k.templates),
                        "views_before": {self.k.view_of_obs.get(o) for o in
                                         self.k.obs_of_template.get(chosen.extra.get("template", ""), [])}}
        return ExperimentPlan(question_id=chosen.id, kind=chosen.kind, steps=v["steps"],
                              oracle=v["extra"].get("oracle"), oracle_action=v["extra"].get("oracle_action"))

    def _saturated(self, area: str, items: list[Question], val) -> bool:
        n = self.st.area_n(area)
        if n < SATURATION_MIN_N or (self.st.area_f1(area) + 1) / (n + 2) >= SATURATION_P_NEW or not self.st.yields:
            return False
        threshold = SATURATION_VALUE_FRACTION * statistics.median(self.st.yields)
        for q in items:
            v = val(q)
            if v and (v["value"] >= threshold or v["unlock"] >= threshold):
                return False
        return True

    # ------------------------------------------------------------------------ outcomes
    def update(self, plan: ExperimentPlan, result: ExperimentResult, view: AgentView) -> None:
        self.k.ingest(plan, result, self.live)
        if self.pending is not None:
            self.pending["result"] = result

    def _resolve(self) -> None:
        pend, self.pending = self.pending, None
        q, v, result, entry = pend["q"], pend["v"], pend.get("result"), pend["entry"]
        k, st = self.k, self.st
        if result is None:
            return
        outcome, bits = "inconclusive", 0.0
        if v["restore"] is not None and v["restore"].minimal and \
                result.abort_reason in {"control_not_found", "control_disabled"}:
            st.minimal_failed.add(q.id)
        if q.kind == "bind_affordance":
            aff = k.affs.get(q.subject_ids[0])
            kind = aff.family["kind"] if aff else "button"
            act = k.actions.get(result.action_ids[-1]) if result.action_ids else None
            if act is not None:
                st.kind_attempts[kind] += 1
                if act.status != "observed":
                    st.kind_fails[kind] += 1
                    outcome = "FAIL"
                    st.family_sigs[q.family]["FAIL"] += 1
                else:
                    cap = k.cap_of_action.get(act.action_id)
                    sig = cap or "NO_EFFECT"
                    outcome = "NEW" if cap and cap not in pend["caps_before"] else ("KNOWN" if cap else "NO_EFFECT")
                    st.area_sigs[q.area][sig] += 1
                    st.family_sigs[q.family][sig] += 1
                    src = k.obs.get(act.source_obs)
                    comp = act.affordance.component
                    if src and any(a.disabled and a.component == comp for a in src.record.affordances or []):
                        st.enable_trials += 1
                        if any(act.id in c.evidence_ids for c in k.claims.get("establishes", [])):
                            st.enable_events += 1
                dist = v["dist"]
                p = dist["FAIL"] if outcome == "FAIL" else dist["NEW"] if outcome == "NEW" else \
                    dist.get(k.cap_of_action.get(act.action_id) or "NO_EFFECT", dist.get("NO_EFFECT", 1e-6))
                bits = -math.log2(max(p, 1e-9))
            else:
                st.inconclusive[q.id] += 1
        else:
            verdict = self._verdict(q, v, result, pend)
            if verdict is None:
                st.inconclusive[q.id] += 1
            else:
                outcome = "pos" if verdict else "neg"
                prior = self._posterior(q) if q.kind != "reproduce" else v["p"]
                post = bayes(prior, verdict, v["s"], v["f"]) if v["f"] > 0 or not verdict else 1 - 1e-6
                st.claim_p[q.claim] = min(max(post, 1e-6), 1 - 1e-6)
                kind = _claim_kind(q)
                st.tested[kind] += 1
                st.confirmed[kind] += bool(verdict)
                if q.kind in {"test_dependency", "test_equivalence"}:
                    st.tested_claims.add(q.id)
                if q.kind == "split_test":
                    st.split_done[q.subject_ids[0]].add(q.extra["instance"])
                bits = kl_bernoulli(st.claim_p[q.claim], prior)
        # ε_env from independent replays of already-reproduced read-only capabilities
        for rid in result.replay_ids:
            rp = k.replays.get(rid)
            if rp is None or not rp.independent_context or rp.verification_kind != "standard":
                continue
            cap = k.cap_of_action.get(rp.action_id)
            if cap and cap in pend["caps_before"] and not k.cap_writes(cap) and \
                    STATUS_RANK.get(k.caps[cap].status, -1) >= STATUS_RANK[Status.REPRODUCED]:
                st.eps_trials += 1
                st.eps_mismatch += rp.id not in k.caps[cap].reproduction_ids
        st.yields.append(bits / max(1, result.actions))
        self.alloc.reward(q.area, bits, result.actions)
        entry.update({"actual_actions": result.actions, "abort": result.abort_reason, "outcome": outcome,
                      "realized_bits": round(bits, 6), "evidence": len(result.records),
                      "new_records": [r.id for r in result.records][-3:]})

    def _verdict(self, q: Question, v: dict, result: ExperimentResult, pend: dict) -> bool | None:
        k = self.k
        obs = [r for r in result.records if r.kind == "observation"]
        if q.kind == "find_entry_point":
            if not obs:
                return None
            return any(k.tpl_of_obs.get(o.obs_id) not in pend["templates_before"] for o in obs)
        if q.kind in {"reproduce", "test_equivalence"}:
            rid = next((r for r in reversed(result.replay_ids) if k.replays.get(r) and
                        k.replays[r].action_id == q.extra["action"]), None)
            if rid is None or not result.completed:
                return None
            cap = k.caps.get(q.subject_ids[0])
            return bool(cap and k.replays[rid].id in cap.reproduction_ids)
        if q.kind == "verify_effect":
            if not result.completed:
                return None
            rp = next((k.replays[r] for r in result.replay_ids if k.replays.get(r) and k.replays[r].verification_kind
                       == q.extra["oracle"]), None)
            if rp is None:
                return None
            ids = rp.verification.get("verification_observation_ids") or []
            os_ = [k.obs[i].record for i in ids if i in k.obs]
            if q.extra["oracle"] == "paired_search" and len(os_) == 4:
                b1, r1, b2, r2 = os_
                primary, contrast = _targets(r1) - _targets(b1), _targets(r2) - _targets(b2)
                return primary != contrast and bool(primary or contrast)
            if q.extra["oracle"] == "cross_view" and len(os_) == 2:
                new = instance_of(os_[0].url)
                return bool(new) and any(instance_of(t) == new for t in _targets(os_[1]))
            return None
        if q.kind == "sample_instance":
            last = obs[-1] if obs else None
            if last is None or k.tpl_of_obs.get(last.obs_id) != q.extra["template"]:
                return None
            return k.view_of_obs.get(last.obs_id) in pend["views_before"]
        if q.kind == "split_test":
            act = k.actions.get(result.action_ids[-1]) if result.action_ids else None
            if act is None or act.status != "observed":
                return None
            return k.cap_of_action.get(act.action_id) in set(q.extra["caps"])
        if q.kind == "test_dependency":
            if not result.completed or len(obs) < 2:
                return None
            x = q.extra["dependent"]
            before = [a.disabled for aid, a in k.occurrences(obs[-2].obs_id) if aid == x]
            after = [a.disabled for aid, a in k.occurrences(obs[-1].obs_id) if aid == x]
            if not before or not after:
                return None
            return before[0] is True and after[0] is False
        return None

    def decisions(self) -> list[dict[str, Any]]:
        return self.log


def make_planner(name: str):
    mode = {"acg_full": "full", "acg_no_unlock": "no_unlock", "acg_uniform": "uniform"}[name]

    def factory(isolation, costs, budget, seed=0):
        return Planner(isolation, costs, budget, seed, mode=mode)
    return factory
