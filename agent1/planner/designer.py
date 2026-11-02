"""L1 experiment designer: restoration plans and experiment step sequences (§5.3).

Restoration options, cheapest first:
- stay: the live view already offers the control;
- history back: one step, only after an input-free read-only step;
- direct URL: a document-entry view whose template has REPRODUCED read-only
  navigation into it (in the live context, or after a fresh context when no
  earlier step of its trail changed state);
- trail replay from a fresh context: each step re-executes a recorded action
  and is itself recorded as a replay, so it is checked on arrival;
- trail replay from an adapter snapshot, only at L3+ with snapshots, which is
  the only way a recorded write may be re-executed.

The planner never teleports to a view it has not reached through recorded,
replayable steps.
"""
from __future__ import annotations

from dataclasses import dataclass

from agent1.model.evidence import AffordanceEvidence

from .interfaces import Costs, Isolation, Step
from .knowledge import Knowledge, TrailStep


@dataclass
class Restore:
    kind: str
    steps: list[Step]
    cost: int
    target: str                    # obs id whose state the plan reproduces
    independent: bool
    minimal: bool = False


def _is_nav(t: TrailStep) -> bool:
    return t.op in {"goto", "back"} or (t.op == "click" and t.url is not None)


def minimal_trail(trail: list[TrailStep]) -> list[TrailStep]:
    """Page-load steps plus the in-page steps after the last page load.

    Used only for controls never observed disabled: in-page state changes on
    earlier pages are then not needed to reach the control. If the shortened
    replay ever fails to find the control, the planner falls back to the
    full trail for that question.
    """
    last = max((i for i, t in enumerate(trail) if _is_nav(t)), default=-1)
    return [t for i, t in enumerate(trail) if i > last or _is_nav(t)]


def _replay(ts: TrailStep) -> Step:
    if ts.op == "goto":
        return Step(op="goto", url=ts.url, purpose="restore")
    if ts.op == "back":
        return Step(op="back", purpose="restore")
    return Step(op="click", affordance=ts.aff, replay_of=ts.action, purpose="restore")


def _cost(steps: list[Step], costs: Costs) -> int:
    return sum(getattr(costs, s.op) for s in steps)


def _gotoable(k: Knowledge, oid: str | None) -> bool:
    """Direct-URL entry needs a document-entry view whose template has REPRODUCED read-only navigation."""
    if oid is None or oid not in k.obs or not k.obs[oid].doc_entry:
        return False
    return k.tpl_of_obs.get(oid) in k.reproduced_templates


def restore(k: Knowledge, live: str, targets: list[str], iso: Isolation, costs: Costs, *,
            independent: bool = False, minimal: bool = False) -> Restore | None:
    """Cheapest permitted way to reach the state of any target observation."""
    best: Restore | None = None
    live_info = k.obs[live]
    order = {"stay": 0, "back": 1, "epoch_goto": 2, "fresh": 3, "snapshot": 4}

    def offer(kind: str, steps: list[Step], target: str, indep: bool) -> None:
        nonlocal best
        if independent and not indep:
            return
        c = _cost(steps, costs)
        if best is None or (c, order[kind]) < (best.cost, order[best.kind]):
            best = Restore(kind=kind, steps=steps, cost=c, target=target, independent=indep, minimal=minimal)

    for s in targets:
        info = k.obs.get(s)
        if info is None:
            continue
        role = info.record.role
        same_context = live_info.epoch == info.epoch and live_info.record.role == role
        if s == live:
            offer("stay", [], s, False)
            continue
        if live_info.prev == s and same_context and live_info.input_free_read and \
                live_info.via is not None and not live_info.via.stateful:
            offer("back", [Step(op="back", purpose="restore")], s, False)
        trail = minimal_trail(list(info.trail)) if minimal else list(info.trail)
        # entry points: the start URL, any goto, and any page load whose template is directly addressable
        entries = [(-1, iso.start_url)] + [(j, t.url) for j, t in enumerate(trail)
                                           if t.url and (t.op == "goto" or _gotoable(k, t.obs))]
        for j, url in entries:
            suffix = trail[j + 1:]
            head = [Step(op="goto", url=url, purpose="restore")] if j >= 0 else []
            if same_context:
                # In the same browser context, effects of steps that sent requests persist
                # (session/server side); only client-side steps are replayed. The executor
                # still checks that the target control is present and enabled on arrival.
                offer("epoch_goto", (head or [Step(op="goto", url=url, purpose="restore")]) +
                      [_replay(t) for t in suffix if not t.sent], s, False)
            if any(t.writes for t in suffix):
                continue
            if not any(t.stateful for t in trail[:j + 1]):
                offer("fresh", [Step(op="fresh", role=role, purpose="restore")] + head + [_replay(t) for t in suffix],
                      s, True)
        if any(t.writes for t in trail) and iso.snapshot and iso.level >= 3:
            offer("snapshot", [Step(op="snapshot", role=role, purpose="restore")] + [_replay(t) for t in trail], s,
                  True)
    return best


def click(aff: AffordanceEvidence, **kw) -> Step:
    return Step(op="click", affordance=aff, **kw)
