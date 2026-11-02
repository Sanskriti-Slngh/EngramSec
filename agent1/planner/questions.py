"""Question generators over the ACG (EXPLORATION_PLANNER_DESIGN.md §4).

Generators iterate over templates, affordance families, capabilities and
claims, never over every record instance. A prerequisite is only ever named
by evidence: a control observed disabled, a request refused with 401/403, or
an observed `establishes` claim. Nothing is inferred from co-occurrence.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from agent1.model.evidence import AffordanceEvidence
from agent1.model.routes import identifier_segments, strip_positions
from agent1.model.schema import STATUS_RANK, Status

from .constants import QUESTION_CLASS, SAMPLE_INSTANCE_K, SATURATION_P_NEW
from .interfaces import Isolation
from .knowledge import Knowledge


@dataclass
class Question:
    id: str
    kind: str
    area: str
    subject_ids: list[str]
    claim: str                                   # claim (or categorical variable) the answer updates
    evidence_ids: list[str]                      # what motivated it
    outcomes: list[str]
    risk_tier: int = 0
    risk: str = "none_observed"
    blocked_reason: str | None = None
    family: tuple | None = None
    targets: list[tuple[str, AffordanceEvidence | None]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def qclass(self) -> str:
        return QUESTION_CLASS[self.kind]


def area_of(k: Knowledge, template_id: str) -> str:
    t = k.templates.get(template_id)
    if t is None:
        return "unknown"
    segs = [s for s in t.route.split("?")[0].split("/") if s]
    return segs[0] if segs else "root"


def instance_of(url: str | None) -> tuple[str, ...]:
    return tuple(v for _, _, v in identifier_segments(urlsplit(url or "").path))


def enabled_targets(k: Knowledge, aff_id: str, instance: tuple[str, ...] | None = None
                    ) -> list[tuple[str, AffordanceEvidence]]:
    aff = k.affs[aff_id]
    out = []
    for oid in k.obs_of_template.get(aff.template_id, []):
        if instance is not None and instance_of(k.obs[oid].record.url) != instance:
            continue
        for aid, a in k.occurrences(oid):
            if aid == aff_id and a.safe and not a.disabled:
                out.append((oid, a))
                break
    return out


def _failure(k: Knowledge, aff_id: str) -> str | None:
    errs = [k.actions[a].error for a in k.affs[aff_id].action_ids if a in k.actions and k.actions[a].error]
    return errs[-1] if errs else None


def generate(k: Knowledge, st: Any, iso: Isolation) -> list[Question]:
    """`st` is the planner's run-local state (counts and posteriors); see planner.py."""
    qs: list[Question] = []
    # A role's identity is its session context; evidence may append cookie names after "+".
    observed_roles = {(i.record.role or "").split("+")[0] for i in k.obs.values()}

    # bind_affordance (and blocked binds) -- one per affordance node; repeated
    # families of distinct nodes (e.g. rows without identifiers) open one member at a time
    families: dict[tuple, list[str]] = defaultdict(list)
    for aff in sorted(k.affs.values(), key=lambda a: a.id):
        fam = (aff.template_id, strip_positions(aff.family["locator"]), aff.family["interaction"], aff.family["kind"])
        families[fam].append(aff.id)
    for fam, members in families.items():
        open_member = False
        for aid in sorted(members, key=lambda a: (st.locator_order(k.affs[a]), a)):
            aff = k.affs[aid]
            area = area_of(k, aff.template_id)
            fail = _failure(k, aid)
            base = dict(kind="bind_affordance", area=area, subject_ids=[aid], claim=f"binding:{aid}",
                        evidence_ids=sorted(aff.evidence_ids)[:3], outcomes=["FAIL", "NEW", "KNOWN", "NO_EFFECT"],
                        family=fam)
            qid = f"bind:{aid}"
            if aff.status in {"bound", "executed_no_effect"}:
                continue
            if aff.status == "blocked":
                reason = aff.reason or "blocked"
                if reason == "disabled":
                    comp = aff.family["component"]
                    qs.append(Question(id=qid, blocked_reason=f"disabled:{aff.template_id}:{comp}", **base))
                elif not reason.startswith("destructive") and not reason.startswith("unsafe"):
                    qs.append(Question(id=qid, blocked_reason=reason, **base))
                else:
                    qs.append(Question(id=qid, blocked_reason="unsafe:" + reason, **base))
                continue
            if aff.status == "failed":
                if fail and fail.startswith("http_40"):
                    qs.append(Question(id=qid, blocked_reason="auth", **base))
                    continue
                if fail and fail.startswith("http_"):
                    qs.append(Question(id=qid, blocked_reason=f"validation:{aid}", **base))
                    continue
                if st.inconclusive.get(qid, 0) >= 2:
                    qs.append(Question(id=qid, blocked_reason="inconclusive", **base))
                    continue
            if len(members) > 1:
                if open_member or not st.family_allows(fam):
                    continue
                open_member = True
            writes = aff.family["kind"] == "form_submit" and aff.family["method"] not in {"", "GET", "HEAD"}
            qs.append(Question(id=qid, risk_tier=1 if writes else 0,
                               risk="server_write_possible" if writes else "none_observed", **base))

    # find_entry_point: adapter-declared roles never observed
    for role in iso.roles:
        if role not in observed_roles:
            qs.append(Question(id=f"entry:role:{role}", kind="find_entry_point", area="root", subject_ids=[role],
                               claim=f"entry:{role}", evidence_ids=[], outcomes=["pos", "neg", "inconclusive"],
                               extra={"role": role}))

    # sample_instance and split_test: instance templates
    for tid, t in k.templates.items():
        if "{id}" not in t.route:
            continue
        sampled = sorted({instance_of(k.obs[o].record.url) for o in k.obs_of_template.get(tid, [])} - {()})
        if not sampled:
            continue
        area = area_of(k, tid)
        if len(sampled) < SAMPLE_INSTANCE_K:
            links = st.instance_links(k, t, set(sampled))
            if links:
                qs.append(Question(id=f"sample:{tid}", kind="sample_instance", area=area, subject_ids=[tid],
                                   claim=f"uniform:{tid}", evidence_ids=[k.obs[links[0][0]].record.id],
                                   outcomes=["pos", "neg", "inconclusive"], targets=links,
                                   extra={"template": tid, "sampled": sampled}))
        for aff in sorted((a for a in k.affs.values() if a.template_id == tid and a.status == "bound"),
                          key=lambda a: a.id):
            done = {instance_of(k.obs[k.actions[x].source_obs].record.url) for x in aff.action_ids
                    if x in k.actions and k.actions[x].source_obs in k.obs}
            done |= st.split_done.get(aff.id, set())
            for inst in sampled:
                if inst in done:
                    continue
                targets = enabled_targets(k, aff.id, inst)
                if targets and not any(k.cap_writes(c) for c in aff.capability_ids):
                    qs.append(Question(id=f"split:{aff.id}", kind="split_test", area=area, subject_ids=[aff.id],
                                       claim=f"uniform:{aff.id}", evidence_ids=sorted(aff.evidence_ids)[:3],
                                       outcomes=["pos", "neg", "inconclusive"], targets=targets,
                                       extra={"instance": inst, "caps": list(aff.capability_ids)}))
                break

    # capabilities: reproduce, verify_effect, test_equivalence
    snapshot_ok = iso.snapshot and iso.level >= 3
    for cap in sorted(k.caps.values(), key=lambda c: c.id):
        acts = [a for a in cap.action_ids if a in k.actions]
        if not acts:
            continue
        first = k.actions[acts[0]]
        src = first.source_obs
        if src not in k.obs:
            continue
        area = area_of(k, k.tpl_of_obs.get(src, ""))
        writes = k.cap_writes(cap.id)
        rank = STATUS_RANK.get(cap.status, -1)
        base_ev = sorted(cap.evidence_ids)[:3]
        tier = 2 if writes else 0
        if rank == STATUS_RANK[Status.OBSERVED]:
            q = Question(id=f"reproduce:{cap.id}", kind="reproduce", area=area, subject_ids=[cap.id],
                         claim=f"reproducible:{cap.id}", evidence_ids=base_ev, outcomes=["pos", "neg", "inconclusive"],
                         risk_tier=tier, risk="server_write_confirmed" if writes else "none_observed",
                         targets=[(src, first.affordance)], extra={"action": first.action_id})
            if writes and not snapshot_ok:
                q.blocked_reason = "write_not_replayable"
            if st.inconclusive.get(q.id, 0) >= 2:
                q.blocked_reason = "inconclusive"
            qs.append(q)
        elif rank == STATUS_RANK[Status.REPRODUCED]:
            filled = any(qq.engine_filled and (qq.method or "GET").upper() == "GET"
                         for a in acts for qq in k.actions[a].requests or [])
            appeared = any(e.kind == "instance_appeared" for e in cap.effects)
            oracle = "paired_search" if filled and not writes else ("cross_view" if writes and appeared else None)
            if oracle:
                q = Question(id=f"verify:{cap.id}", kind="verify_effect", area=area, subject_ids=[cap.id],
                             claim=f"oracle:{oracle}:{cap.id}", evidence_ids=base_ev,
                             outcomes=["pos", "neg", "inconclusive"], risk_tier=tier,
                             targets=[(src, first.affordance)], extra={"action": first.action_id, "oracle": oracle})
                if oracle == "cross_view" and not snapshot_ok:
                    q.blocked_reason = "write_not_replayable"
                if st.inconclusive.get(q.id, 0) >= 2:
                    q.blocked_reason = "inconclusive"
                qs.append(q)
        if len(cap.bindings) >= 2 and not writes:
            least = min(cap.bindings, key=lambda b: (len(b.action_ids), b.affordance_id))
            act = k.actions.get(least.action_ids[0])
            if act and act.source_obs in k.obs and f"equiv:{cap.id}" not in st.tested_claims:
                qs.append(Question(id=f"equiv:{cap.id}", kind="test_equivalence", area=area,
                                   subject_ids=[cap.id, least.affordance_id], claim=f"equivalent:{cap.id}",
                                   evidence_ids=base_ev, outcomes=["pos", "neg", "inconclusive"],
                                   targets=[(act.source_obs, act.affordance)], extra={"action": act.action_id}))

    # test_dependency: an observed `establishes` claim (control enabled after a capability, same page)
    for c in k.claims.get("establishes", []):
        cap, x = c.subject, c.object.split(":", 1)[1]
        if cap not in k.caps or x not in k.affs or f"dep:{x}:{cap}" in st.tested_claims:
            continue
        acts = [a for a in k.caps[cap].action_ids if a in k.actions]
        if not acts:
            continue
        act = k.actions[acts[0]]
        disabled_obs = [o for o in k.obs_of_template.get(k.affs[x].template_id, [])
                        if any(aid == x and a.disabled for aid, a in k.occurrences(o))]
        targets = [(o, act.affordance) for o in disabled_obs
                   if any(a.safe and not a.disabled and (a.kind, a.locator, a.component) ==
                          (act.affordance.kind, act.affordance.locator, act.affordance.component)
                          for _, a in k.occurrences(o))]
        q = Question(id=f"dep:{x}:{cap}", kind="test_dependency", area=area_of(k, k.affs[x].template_id),
                     subject_ids=[x, cap], claim=f"requires:{x}:{cap}", evidence_ids=sorted(c.evidence_ids)[:3],
                     outcomes=["pos", "neg", "inconclusive"], targets=targets,
                     extra={"action": act.action_id, "dependent": x})
        if k.cap_writes(cap) and not snapshot_ok:
            q.blocked_reason = "write_not_replayable"
        elif not targets:
            q.blocked_reason = "no_disabled_view_reachable"
        qs.append(q)
    return qs
