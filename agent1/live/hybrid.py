"""Capability-aware legacy hybrid (opt-in `exploration_policy="hybrid_capabilities"`).

The legacy persistent frontier keeps its execution loop, local bursts, safety,
scope and budget controls. The live ACG only changes *which* frontier item the
loop takes next, through three evidence-gated mechanisms:

A. Redundancy control. A candidate is deferred (never deleted) when executed
   evidence shows its structural affordance family already behaves the same:
   the same exact target was executed once, or two distinct instances of the
   family produced the same ACG behavior (operations and effects), or the
   candidate repeats a family from another session role after that role's
   cross-role samples all reproduced the earlier behavior. A family whose
   samples disagree is split and never deferred. Labels, DOM structure and
   templates alone never defer anything.
B. Prerequisite continuation. A control that an executed action revealed on
   the same page, or that is enabled now but was disabled on the last visit to
   the same page, is investigated first while the live session still holds the
   state, past the legacy local-burst limit. This is a dependency hypothesis,
   not a causal claim.
C. Feasibility-gated verification. Legacy's separate replay phase runs only
   replays whose starting state can be rebuilt safely: no observed
   write-capable step, no session state a fresh context cannot rebuild, no
   prefix that already failed deterministically. Blocked replays cost nothing
   and are logged.

The evidence table is recomputed from the live ACG and the explorer's artifact
on every decision; nothing here is a parallel model of the application. Every
exploration and verification step is recorded in the execution ledger.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit

from agent1.model.routes import path_route

from .acg import LiveACG
from .ledger import ExecutionLedger, SessionRef, StepExecution, cookie_digest

REPRESENTATIVES = 2          # consistent samples from distinct instances before a family is deferred
ROLE_TRANSFER_SAMPLES = 2    # consistent cross-role samples before other cross-role repeats are deferred
LOCAL_BURST = 8              # the legacy local-burst limit (unchanged for ordinary items)
READ_METHODS = {"GET", "HEAD", "OPTIONS"}
NO_EFFECT = (("no_effect",),)


# ----------------------------------------------------------------------------- pure policy
@dataclass(frozen=True)
class Sample:
    """One observed exploration execution."""
    transition_id: str
    family: str
    exact: str
    role: str
    instance: str
    behavior: tuple


@dataclass
class Assessment:
    redundant: bool
    reason: str                     # novel | uncertain | family_split | same_target_repeat | family_settled | cross_role_repeat
    evidence: list[str] = field(default_factory=list)


class CapabilityPolicy:
    """Redundancy decisions from executed samples only (deterministic, no browser)."""

    def __init__(self, representatives: int = REPRESENTATIVES, transfer: int = ROLE_TRANSFER_SAMPLES) -> None:
        self.representatives, self.transfer = representatives, transfer
        self.samples: list[Sample] = []
        self.role_transfer: dict[str, dict[str, Any]] = {}

    def rebuild(self, samples: Iterable[Sample]) -> None:
        self.samples = list(samples)
        self.role_transfer = {}
        first_role_behavior: dict[tuple[str, str], set] = {}
        for s in self.samples:                       # in execution order
            others = {r: b for (f, r), b in first_role_behavior.items() if f == s.family and r != s.role}
            if others and not any((s.family, s.role) == k for k in first_role_behavior):
                rt = self.role_transfer.setdefault(s.role, {"match": 0, "mismatch": 0, "evidence": []})
                consistent = [b for b in others.values() if len(b) == 1]
                if consistent:
                    rt["match" if all(s.behavior in b for b in consistent) else "mismatch"] += 1
                    rt["evidence"].append(s.transition_id)
            first_role_behavior.setdefault((s.family, s.role), set()).add(s.behavior)

    def _in(self, family: str, role: str) -> list[Sample]:
        return [s for s in self.samples if s.family == family and s.role == role]

    def assess(self, family: str, exact: str, role: str) -> Assessment:
        fam = self._in(family, role)
        behaviors = {s.behavior for s in fam}
        if len(behaviors) > 1:
            return Assessment(False, "family_split", [s.transition_id for s in fam])
        same = [s for s in fam if s.exact == exact]
        if same:
            return Assessment(True, "same_target_repeat", [s.transition_id for s in same])
        if len({s.instance for s in fam}) >= self.representatives:
            return Assessment(True, "family_settled", [s.transition_id for s in fam])
        if fam:
            return Assessment(False, "uncertain", [s.transition_id for s in fam])
        rt = self.role_transfer.get(role, {"match": 0, "mismatch": 0, "evidence": []})
        settled_elsewhere = []
        for other in {s.role for s in self.samples if s.family == family} - {role}:
            o = self._in(family, other)
            if len({s.behavior for s in o}) == 1 and (any(s.exact == exact for s in o)
                                                      or len({s.instance for s in o}) >= self.representatives):
                settled_elsewhere += [s.transition_id for s in o]
        if settled_elsewhere:
            if rt["mismatch"] == 0 and rt["match"] >= self.transfer:
                return Assessment(True, "cross_role_repeat", settled_elsewhere + rt["evidence"])
            return Assessment(False, "uncertain", settled_elsewhere)
        return Assessment(False, "novel")


def continuation_signatures(src_page: str | None, src_controls: set[str], res_page: str,
                            res_controls: set[str], src_disabled: set[str], last_visit_disabled: set[str]) -> dict[str, str]:
    """Controls an executed action made available: signature -> 'revealed' | 'enabled'.

    Pages are concrete URL paths (two records of one template are different pages).
    `revealed`: on the same page as the source, present now and absent before.
    `enabled`: present and enabled now, observed disabled before on this page
    (on the source page, or on the last visit to the result page)."""
    out: dict[str, str] = {}
    for sig in res_controls & (last_visit_disabled | (src_disabled if src_page == res_page else set())):
        out[sig] = "enabled"
    if src_page == res_page:
        for sig in res_controls - src_controls:
            out.setdefault(sig, "revealed")
    return out


def verification_gate(path: list[str], write_signatures: set[str], unreachable_prefixes: set[tuple[str, ...]],
                      requires_session: bool) -> tuple[bool, str]:
    """Whether a replay of `path` (control signatures, last = the action) may run from a fresh context."""
    if path and path[-1] in write_signatures:
        return False, "write_capable_operation"
    if any(sig in write_signatures for sig in path[:-1]):
        return False, "state_changing_prerequisite"
    if any(tuple(path[:len(p)]) == p for p in unreachable_prefixes):
        return False, "prefix_unreachable"
    if requires_session:
        return False, "session_state_unavailable"
    return True, "feasible"


# ----------------------------------------------------------------------------- explorer adapter
def _role(obs: Any) -> str:
    from agent1.model.importer import _role as role_of
    return role_of(obs.session_context, obs.session_markers)


def _page(obs: Any) -> str:
    return urlsplit(obs.url).path


def _fields(d: Any) -> list:
    return sorted((f.input_type, f.name, f.required) for f in d.fields)


def family_of(source_route: str, d: Any) -> str:
    rev = d.behavior_revision or ""
    if d.target:
        return json.dumps(["t", d.kind, d.interaction, (d.method or "GET").upper(),
                           path_route(urlsplit(d.target).path), _fields(d), rev])
    # Handler-driven controls: no target to compare, so the family is scoped to the page and label.
    return json.dumps(["h", source_route, d.kind, d.interaction, d.component, d.role, d.label, _fields(d), rev])


def exact_of(source_route: str, source_group: str, d: Any) -> str:
    if d.target:
        return json.dumps(["t", d.kind, d.interaction, (d.method or "GET").upper(), d.target, _fields(d),
                           d.behavior_revision or ""])
    return family_of(source_route, d) + "|" + source_group


def instance_of(source: Any, d: Any) -> str:
    return d.target if d.target else f"{urlsplit(source.url).path}|{source.group_signature}"


class HybridController:
    def __init__(self, explorer: Any) -> None:
        self.ex = explorer
        self.live = LiveACG(application="live", sink=explorer.evidence_sink)
        self.policy = CapabilityPolicy()
        self.ledger = ExecutionLedger()
        self.decisions: list[dict[str, Any]] = []
        self.verification: list[dict[str, Any]] = []
        self.counters: Counter = Counter()
        self.open: dict[str, dict[str, Any]] = {}      # continuation signature -> hypothesis
        self.deferred: dict[tuple, str] = {}            # frontier item key -> first deferral reason
        self.executed_keys: set[tuple] = set()
        self.unreachable: set[tuple[str, ...]] = set()
        self.epoch = 0
        self.plan_seq = 0
        self.decide_ms: list[float] = []
        self._pending: dict[str, Any] | None = None

    # ------------------------------------------------------------ evidence
    def _obs(self, oid: str | None) -> Any:
        return self.ex._observation_by_id(oid) if oid else None

    def refresh(self) -> None:
        self.live.sync(self.ex.artifact)
        export = self.live.export()
        cap_of = {a: c for c in export.capabilities for a in c.action_ids}
        samples = []
        for t in self.ex.artifact.transitions:
            src = self._obs(t.source_observation_id)
            if src is None or not t.result_observation_id or t.error:
                continue
            cap = cap_of.get(t.id)
            behavior = ((tuple(sorted(cap.operation_ids)), tuple(sorted(e.kind for e in cap.effects)))
                        if cap else NO_EFFECT)
            samples.append(Sample(t.id, family_of(src.route_pattern, t.action),
                                  exact_of(src.route_pattern, src.group_signature, t.action), _role(src),
                                  instance_of(src, t.action), behavior))
        self.policy.rebuild(samples)

    @staticmethod
    def _key(item: Any) -> tuple:
        return item.source_observation_id, item.action.signature, item.action.behavior_revision or ""

    def assess(self, item: Any) -> Assessment:
        src = self._obs(item.source_observation_id)
        if src is None:
            return Assessment(False, "novel")
        return self.policy.assess(family_of(src.route_pattern, item.action),
                                  exact_of(src.route_pattern, src.group_signature, item.action), _role(src))

    # ------------------------------------------------------------ selection
    def select(self, frontier: list[Any], live: Any, is_local: Callable[[Any], bool], legacy_index: int | None,
               local_burst: int) -> tuple[int, bool]:
        start = time.perf_counter()
        local = [i for i, c in enumerate(frontier) if c.expected_source_group == live.group_signature and is_local(c)]
        legacy_choice = legacy_index if legacy_index is not None else 0
        row: dict[str, Any] = {"n": len(self.decisions), "actions": self.ex.artifact.metrics.browser_actions,
                               "live_obs": live.id, "legacy": self._describe(frontier[legacy_choice])}
        chosen, reason, deferred = None, "legacy", []
        for i in local:
            hyp = self.open.get(frontier[i].action.signature)
            if hyp and hyp["page"] == _page(live):
                chosen, reason = i, f"prerequisite_continuation:{hyp['kind']}"
                row["hypothesis"] = {"after": hyp["after"], "kind": hyp["kind"]}
                break
        if chosen is None:
            order = [legacy_choice] + ([i for i in local if i != legacy_choice] if local_burst < LOCAL_BURST else [])
            order += [i for i in range(len(frontier)) if i not in order]
            for i in order:
                a = self.assess(frontier[i])
                if not a.redundant:
                    chosen = i
                    reason = "legacy" if i == legacy_choice else "redundancy_deferral"
                    break
                deferred.append({**self._describe(frontier[i]), "reason": a.reason, "evidence": a.evidence[:6]})
                self.deferred.setdefault(self._key(frontier[i]), a.reason)
            if chosen is None:
                chosen, reason = legacy_choice, "all_redundant_legacy_fallback"
        self.counters[reason.split(":")[0]] += 1
        row.update(chosen=self._describe(frontier[chosen]), reason=reason, deferred=deferred[:12],
                   deferred_count=len(deferred))
        self.decisions.append(row)
        self.decide_ms.append((time.perf_counter() - start) * 1000)
        return chosen, chosen in local

    @staticmethod
    def _describe(item: Any) -> dict[str, Any]:
        return {"label": item.action.label[:60], "kind": item.action.kind, "signature": item.action.signature[:16],
                "source_obs": item.source_observation_id}

    # ------------------------------------------------------------ exploration ledger
    def before_attempt(self, item: Any) -> None:
        m = self.ex.artifact.metrics
        self._pending = {"item": item, "transitions": len(self.ex.artifact.transitions), "actions": m.browser_actions,
                         "suppressed": m.repeat_write_actions_suppressed, "t0": time.perf_counter()}

    def after_attempt(self, updated: Any) -> None:
        p, self._pending = self._pending, None
        if p is None:
            return
        item, m = p["item"], self.ex.artifact.metrics
        self.executed_keys.add(self._key(item))
        src = self._obs(item.source_observation_id)
        actions = m.browser_actions - p["actions"]
        new = self.ex.artifact.transitions[p["transitions"]:]
        entry = StepExecution(
            plan_id=f"x{self.plan_seq}", step_index=0, op=item.action.interaction, purpose="discovery",
            intended={"signature": item.action.signature, "kind": item.action.kind,
                      "family": family_of(src.route_pattern, item.action) if src else None},
            source_obs=item.source_observation_id, session=self._session(src),
            expected_route=src.route_pattern if src else None, browser_actions=actions,
            elapsed_ms=round((time.perf_counter() - p["t0"]) * 1000, 1))
        self.plan_seq += 1
        if new:
            t = new[-1]
            res = self._obs(t.result_observation_id)
            entry.stage, entry.transition_id = "executed", t.id
            entry.requests = self._requests(t.network)
            entry.writes = any(r["method"] not in READ_METHODS for r in entry.requests)
            entry.state_changing = entry.writes or bool(t.behavior.get("possible_state_change"))
            entry.resolved_control = {"signature": t.action.signature, "label": t.action.label[:60]}
            if res is not None and not t.error:
                entry.stage, entry.outcome, entry.result_obs = "observed", "succeeded", res.id
                entry.actual_route = res.route_pattern
                self._learn_continuation(src, res, t)
            else:
                entry.outcome, entry.reason = "failed", (t.error or "no_result_observation")[:120]
        elif m.repeat_write_actions_suppressed > p["suppressed"] and actions == 0:
            entry.outcome, entry.reason = "refused", "known_write"
        elif updated is None:
            entry.stage, entry.outcome, entry.reason = "attempted", "stale", "live_state_stale"
        else:
            entry.stage, entry.outcome, entry.reason = "attempted", "failed", "no_transition_recorded"
        if entry.outcome in {"refused"}:
            entry.stage = "planned"
        self.ledger.append(entry)
        self.open.pop(item.action.signature, None)
        self.refresh()

    def _session(self, obs: Any) -> SessionRef:
        if obs is None:
            return SessionRef(epoch=self.epoch, role="unknown")
        names = (obs.session_markers or {}).get("cookie_names") or []
        return SessionRef(epoch=self.epoch, role=_role(obs), cookie_names_digest=cookie_digest(names))

    def _requests(self, network: list[Any]) -> list[dict[str, Any]]:
        sink = self.ex.evidence_sink
        out = []
        for n in network or []:
            url = sink.pseudo_url(n.url) if sink is not None else n.url
            out.append({"method": (n.method or "").upper(), "route": path_route(urlsplit(url or "").path)})
        return out

    # ------------------------------------------------------------ continuation (B)
    def _learn_continuation(self, src: Any, res: Any, t: Any) -> None:
        disabled = self.ex.evidence_sink.disabled if self.ex.evidence_sink is not None else {}
        sigs = lambda o: {c.signature for c in o.controls if c.safe}
        last = next((o for o in reversed(self.ex.artifact.observations)
                     if o.id not in {res.id, src.id if src else ""} and _page(o) == _page(res)
                     and _role(o) == _role(res)), None)
        found = continuation_signatures(
            _page(src) if src else None, sigs(src) if src else set(), _page(res), sigs(res),
            {c.signature for c in disabled.get(src.id, [])} if src else set(),
            {c.signature for c in disabled.get(last.id, [])} if last else set())
        for sig, kind in found.items():
            if sig not in self.open:
                self.open[sig] = {"kind": kind, "after": t.id, "page": _page(res)}
                self.counters[f"hypothesis_{kind}"] += 1

    # ------------------------------------------------------------ verification (C)
    def gate(self, transition: Any) -> tuple[bool, str]:
        transitions = self.ex.artifact.transitions
        writes = {t.action.signature for t in transitions
                  if any((n.method or "GET").upper() not in READ_METHODS for n in t.network)
                  or t.behavior.get("possible_state_change")}
        role_changing = {t.action.signature for t in transitions
                         if (s := self._obs(t.source_observation_id)) and (r := self._obs(t.result_observation_id))
                         and _role(s) != _role(r)}
        start = self.ex.artifact.observations[0] if self.ex.artifact.observations else None
        src = self._obs(transition.source_observation_id)
        path = [d.signature for d in transition.workflow_path]
        needs_session = bool(start and src and _role(src) != _role(start)
                             and not any(sig in role_changing for sig in path[:-1]))
        ok, reason = verification_gate(path, writes, self.unreachable, needs_session)
        if not ok:
            self.ledger.append(StepExecution(
                plan_id=f"v{self.plan_seq}", step_index=0, op="replay", purpose="verification", plan_kind="reproduce",
                intended={"transition": transition.id, "path_length": len(path)}, session=self._session(src),
                source_obs=transition.source_observation_id, outcome="refused", reason=reason, replay_of=transition.id))
            self.plan_seq += 1
            self.verification.append({"transition": transition.id, "label": transition.action.label[:60],
                                      "decision": "blocked", "reason": reason})
            self.counters[f"verification_blocked:{reason}"] += 1
        return ok, reason

    def after_replay(self, transition: Any, replay: Any) -> None:
        self.epoch += 1                         # every replay runs in a fresh browser context
        src = self._obs(transition.source_observation_id)
        validated = str(getattr(replay.status, "value", replay.status)) == "replay_validated"
        deterministic = (replay.failure_reason or "") in {"control_missing", "control_not_found"} or \
            (replay.failure_reason or "").startswith("control_missing")
        if not validated and deterministic and replay.failed_step:
            self.unreachable.add(tuple(d.signature for d in transition.workflow_path[:replay.failed_step]))
        self.ledger.append(StepExecution(
            plan_id=f"v{self.plan_seq}", step_index=0, op="replay", purpose="verification", plan_kind="reproduce",
            intended={"transition": transition.id, "path_length": len(transition.workflow_path)},
            session=SessionRef(epoch=self.epoch, role=_role(src) if src else "unknown"),
            source_obs=transition.source_observation_id, stage="executed", outcome="succeeded" if validated else "failed",
            reason=None if validated else (replay.failure_reason or "not_reproduced"), replay_id=replay.id,
            replay_of=transition.id, browser_actions=replay.browser_actions,
            verification_result="reproduced" if validated else ("mismatch" if not deterministic else None)))
        if validated:
            # The ledger's success contract needs an observed result; a replay's own
            # observation id is recorded on the replay evidence itself.
            entry = self.ledger.entries[-1]
            entry.stage, entry.result_obs = "observed", getattr(replay, "actual_observation_id", None) or replay.id
        self.plan_seq += 1
        self.verification.append({"transition": transition.id, "label": transition.action.label[:60],
                                  "decision": "replayed", "validated": validated, "reason": replay.failure_reason})
        self.counters["verification_replayed"] += 1

    # ------------------------------------------------------------ summary
    def finish(self, output_dir: Path) -> dict[str, Any]:
        remaining = {self._key(i) for i in self.ex.frontier}
        prevented = sum(1 for k in self.deferred if k in remaining and k not in self.executed_keys)
        later = sum(1 for k in self.deferred if k in self.executed_keys)
        self.ledger.save(output_dir / "execution_ledger.jsonl")
        (output_dir / "hybrid_decisions.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in self.decisions + [{"verification": v} for v in self.verification]))
        outcomes = Counter(e.outcome for e in self.ledger.entries)
        return {"decisions": len(self.decisions), "counters": dict(self.counters),
                "deferred_items": len(self.deferred), "redundant_actions_prevented": prevented,
                "deferred_then_executed": later,
                "deferral_reasons": dict(Counter(self.deferred.values())),
                "continuation_hypotheses_open_at_end": len(self.open),
                "verification_blocked": sum(1 for v in self.verification if v["decision"] == "blocked"),
                "verification_replayed": sum(1 for v in self.verification if v["decision"] == "replayed"),
                "verification_actions": sum(e.browser_actions for e in self.ledger.entries if e.purpose == "verification"),
                "ledger_steps": len(self.ledger.entries), "ledger_integrity": self.ledger.integrity(),
                "step_outcomes": dict(outcomes),
                "decide_ms_mean": round(sum(self.decide_ms) / len(self.decide_ms), 2) if self.decide_ms else None,
                "acg_update_ms_mean": round(sum(self.live.latencies_ms) / len(self.live.latencies_ms), 2)
                if self.live.latencies_ms else None}
