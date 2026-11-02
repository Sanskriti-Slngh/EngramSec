"""Execution-grounded tour execution: step ledger, verified restoration, complete feedback.

`GroundedExecutor` runs each plan step through the same legacy browser machinery
as the Phase 3 adapter, but:
- writes exactly one `StepExecution` per planned step (refused, unsupported and
  not-attempted steps included);
- observes and records the browser state after every executed step, so each step
  carries its own result observation and evidence;
- checks every restoration step against the state it was expected to reach
  (route, record) and, before the experiment, the full target state (route,
  record, session epoch, required control available, prerequisite controls
  still enabled); any mismatch is a structured restoration failure;
- refuses clicks on controls the legacy write guard knows to change state,
  including state-changing GETs, whether discovery or restoration.

`GroundedTourRunner` builds the scheduler's knowledge from the ledger only, and
feeds back refusals (with the condition they hold under), actual verification
cost, deterministic replay mismatches, failed restoration edges and structured
role identity.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any
from urllib.parse import urlsplit

from agent1.planner.interfaces import AgentView, Costs, ExperimentResult
from agent1.planner.knowledge import Knowledge, ObsInfo, TrailStep

from .executor import VERIFICATION, TourExecutor, _instance
from .ledger import ExecutionLedger, SessionRef, StepExecution, cookie_digest
from .reachability import ReachabilityModel
from .shadow import ActiveTourRunner

PERMANENT_REFUSALS = ("known_write", "known_state_change", "control_unsafe", "unsupported", "refused:unsafe")


def _route(obs: Any) -> str | None:
    return getattr(obs, "route_pattern", None)


class GroundedExecutor(TourExecutor):
    def __init__(self, explorer: Any, runner: Any) -> None:
        super().__init__(explorer, runner)
        self.ledger: ExecutionLedger = runner.ledger
        self.epoch = 0
        self.plans = 0
        self.restorations = {"attempted": 0, "verified": 0, "failed": 0}

    # ------------------------------------------------------------- identity
    def session_ref(self, live: Any) -> SessionRef:
        cfg = self.ex.config
        account = hashlib.sha256(str(cfg.storage_state_path).encode()).hexdigest()[:12] if cfg.storage_state_path else None
        names = sorted((live.session_markers or {}).get("cookie_names") or []) if live is not None else []
        return SessionRef(epoch=self.epoch, role=cfg.context_label, account_ref=account,
                          cookie_names_digest=cookie_digest(names))

    def _pseudo(self, url: str | None) -> str | None:
        sink = self.ex.evidence_sink
        return sink.pseudo_url(url) if sink is not None and url else url

    def _record(self, obs: Any) -> tuple:
        """Record identity as pseudonymized identifier values (never raw)."""
        sink = self.ex.evidence_sink
        return tuple(sink.pseudo_value(v) if sink is not None else v for v in _instance(obs.url))

    # ----------------------------------------------------------------- run
    def run(self, browser: Any, session: Any, plan: Any, live: Any, live_path: list, target_obs: str | None):
        from agent1.explorer import BrowserSession, UnsafeRestoration
        from agent1.schema import EvidenceStatus, FrontierItem, ReplayResult
        from agent1.state import allowed_origin
        ex = self.ex
        self.plans += 1
        plan_id = f"p{self.plans}"
        start_actions = ex.artifact.metrics.browser_actions
        before_t, before_r = len(ex.artifact.transitions), len(ex.artifact.replays)
        verification = plan.kind in VERIFICATION
        independent = bool(plan.steps) and plan.steps[0].op == "fresh"
        target = ex._observation_by_id(target_obs) if target_obs else None
        entries: list[StepExecution] = []
        stopped: str | None = None
        refused: list[str] = []
        has_restoration = any(s.purpose == "restore" for s in plan.steps)
        restoration_verified = False
        if has_restoration:
            self.restorations["attempted"] += 1
        for index, step in enumerate(plan.steps):
            experiment = index == len(plan.steps) - 1
            purpose = ("restoration" if step.purpose == "restore" and not experiment
                       else "verification" if verification else "discovery")
            intended = {"kind": getattr(step.affordance, "kind", None), "locator": getattr(step.affordance, "locator", None),
                        "component": getattr(step.affordance, "component", None),
                        "target": getattr(step.affordance, "target", None), "url": step.url,
                        "source_route": _route(live), "source_record": list(self._record(live)),
                        "source_has_disabled": bool((ex.evidence_sink.disabled.get(live.id) if ex.evidence_sink else []))}
            expect = ex._observation_by_id(step.expect_obs) if step.expect_obs and not experiment else None
            entry = StepExecution(plan_id=plan_id, step_index=index, op=step.op, plan_kind=plan.kind, purpose=purpose,
                                  intended=intended,
                                  source_obs=live.id, session=self.session_ref(live), replay_of=step.replay_of,
                                  expected_route=_route(expect) if expect else None,
                                  expected_record=list(self._record(expect)) if expect else None)
            entries.append(entry)
            if stopped:
                continue
            t0, a0 = time.perf_counter(), ex.artifact.metrics.browser_actions
            h0 = ex.http_budget.used if ex.http_budget else 0
            outcome, reason, result_obs = self._execute(browser, session, plan, step, entry, experiment, verification,
                                                        independent, live, live_path, target, refused)
            entry.browser_actions = ex.artifact.metrics.browser_actions - a0
            entry.http_used = (ex.http_budget.used if ex.http_budget else 0) - h0
            entry.elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
            entry.outcome, entry.reason = outcome, reason
            if outcome in {"refused", "unsupported"}:
                entry.stage = "attempted"
            elif result_obs is not None:
                entry.stage = "observed"
                entry.result_obs = result_obs[0].id
                entry.actual_route = _route(result_obs[0])
                entry.actual_record = list(self._record(result_obs[0]))
                live, live_path = result_obs
                # per-step arrival check against the state this step was expected to reach
                if outcome == "succeeded" and expect is not None and not experiment:
                    if entry.actual_route != entry.expected_route:
                        entry.outcome, entry.reason = "failed", "arrived_at_wrong_state:route"
                    elif entry.actual_record != entry.expected_record:
                        entry.outcome, entry.reason = "failed", "arrived_at_wrong_state:record"
            elif outcome != "not_attempted":
                entry.stage = "executed" if entry.browser_actions else "attempted"
            if entry.outcome != "succeeded":
                stopped = entry.reason or entry.outcome
                continue
            # before the experiment: verify the restored state as a whole
            if has_restoration and index == len(plan.steps) - 2 and target is not None:
                problem = self._verify_target(live, target, plan.steps[-1])
                if problem:
                    # The step executed, but did not restore the required state: that is a failed
                    # restoration of this route, recorded on the step that was supposed to achieve it.
                    stopped = "restoration_mismatch:" + problem
                    entry.outcome, entry.reason = "failed", stopped
                    entry.intended["restore_target"] = target.id
                    continue
                restoration_verified = True
        for e in entries:
            if e.outcome == "not_attempted" and stopped and e.stage == "planned":
                e.reason = e.reason or "not attempted: " + stopped
            self.ledger.append(e)
        if has_restoration:
            self.restorations["verified" if restoration_verified else "failed"] += 1
        self._count(stopped or "completed")
        recorded = {o.id for o in ex.artifact.observations} | {o.id for o in ex.artifact.replay_observations}
        if live.id not in recorded:
            ex._record_observation(live, list(live_path))
        records, action_ids, replay_ids = self.runner.sync_new(ex.artifact, before_t, before_r)
        result = ExperimentResult(records=records, actions=ex.artifact.metrics.browser_actions - start_actions,
                                  completed=stopped is None, abort_reason=stopped, refused=refused, live_obs=live.id,
                                  action_ids=action_ids, replay_ids=replay_ids)
        return result, live, live_path

    def _verify_target(self, live: Any, target: Any, experiment_step: Any) -> str | None:
        """Independent check that restoration reached the intended state, not just a URL."""
        if _route(live) != _route(target):
            return "route"
        if _instance(live.url) != _instance(target.url):
            return "record"
        if (live.session_context or "") != (target.session_context or ""):
            return "role"
        if experiment_step.op == "click":
            control, problem = self._resolve(live, experiment_step.affordance)
            if control is None:
                return "required_control_" + (problem or "missing")
        sink = self.ex.evidence_sink
        if sink is not None:
            disabled_any = {(c.css_path, c.kind, c.component) for v in sink.disabled.values() for c in v}
            needed = {(c.css_path, c.kind, c.component) for c in target.controls} & disabled_any
            have = {(c.css_path, c.kind, c.component) for c in live.controls}
            if needed - have:
                return "prerequisite_state_lost"
        return None

    # -------------------------------------------------------------- one step
    def _execute(self, browser, session, plan, step, entry, experiment, verification, independent, live, live_path,
                 target, refused):
        from agent1.explorer import BrowserSession, UnsafeRestoration
        from agent1.schema import EvidenceStatus, FrontierItem, ReplayResult
        from agent1.state import allowed_origin
        ex = self.ex
        if not self._budget_left():
            return "refused", "budget", None
        if step.op == "snapshot" or (step.op == "fresh" and (step.role or ex.config.context_label).split("+")[0]
                                     != ex.config.context_label):
            return "unsupported", "unsupported_operation:" + step.op, None
        if step.input is not None or step.oracle_capture is not None:
            return "unsupported", "unsupported_input_variant", None
        if step.op == "fresh":
            session.reset_context()
            self.epoch += 1
            ex._navigate_start(session, "frontier_restore")
            entry.requests = self._requests(session.last_navigation_network)
            obs = session.observe(ex._next_sequence())
            ex._record_observation(obs, [])
            entry.session = self.session_ref(obs)
            return "succeeded", None, (obs, [])
        if step.op == "goto":
            raw = self.runner.raw_url(step.url)
            if raw is None or not allowed_origin(ex.config.start_url, raw, ex.config.origin_aliases):
                return "refused", "goto_unresolved_or_out_of_scope", None
            ex.artifact.metrics.browser_actions += session.goto(raw)
            ex.artifact.metrics.restoration_actions += 1
            ex._record_navigation_evidence(session, "frontier_restore")
            entry.requests = self._requests(session.last_navigation_network)
            obs = session.observe(ex._next_sequence())
            ex._record_observation(obs, [])
            return "succeeded", None, (obs, [])
        if step.op == "back":
            if not session.go_back():
                return "failed", "history_unavailable", None
            ex.artifact.metrics.browser_actions += 1
            ex.artifact.metrics.restoration_actions += 1
            ex._record_navigation_evidence(session, "history_return")
            entry.requests = self._requests(session.last_navigation_network)
            obs = session.observe(ex._next_sequence())
            ex._record_observation(obs, [])
            return "succeeded", None, (obs, live_path[:-1])
        control, problem = self._resolve(live, step.affordance)
        if control is None:
            if problem == "control_unsafe":
                refused.append(problem)
                return "refused", problem, None
            return "failed", problem, None
        entry.resolved_control = {"css_path": control.css_path, "kind": control.kind, "component": control.component,
                                  "target": self._pseudo(control.target)}
        if experiment and target is not None and (_instance(target.url) != _instance(live.url)
                                                  or target.route_pattern != live.route_pattern):
            return "refused", "record_identity_mismatch", None
        descriptor = BrowserSession.descriptor(control)
        if ex.config.state_aware_exploration and ex._known_write(live, descriptor):
            refused.append("known_state_change")
            return "refused", "known_state_change", None      # includes observed state-changing GETs
        gate_reason = self.runner.gate_check(step, live)
        if gate_reason:
            refused.append(gate_reason)
            return "refused", gate_reason, None
        if experiment and not verification:
            item = FrontierItem(source_observation_id=live.id, expected_source_signature=live.state_signature,
                                expected_source_group=live.group_signature, path=list(live_path), action=descriptor)
            count = len(ex.artifact.transitions)
            updated = ex._attempt_frontier(browser, item, persistent_session=session, live_source=live,
                                           live_path=live_path)
            if updated is None:
                ex.artifact.metrics.live_state_stale += 1
                ex._navigate_start(session, "persistent_restore")
                obs = session.observe(ex._next_sequence())
                ex._record_observation(obs, [])
                return "stale", "live_state_stale", (obs, [])
            obs, observed = updated
            if len(ex.artifact.transitions) == count:
                refused.append("known_write_suppressed")
                return "refused", "known_write_suppressed", None
            t = ex.artifact.transitions[-1]
            entry.transition_id = t.id
            entry.requests = self._requests(t.network)
            entry.writes = bool(t.behavior.get("write_capable_request_observed"))
            entry.state_changing = bool(t.behavior.get("possible_state_change"))
            if t.status != EvidenceStatus.OBSERVED:
                return "failed", "action_failed", (obs, list(live_path))
            return "succeeded", None, (obs, list(live_path) + [descriptor])
        original = next((t for t in ex.artifact.transitions if t.id == step.replay_of), None)
        if original is None and experiment:
            return "failed", "replay_target_unknown", None
        desc = original.action if original is not None else descriptor
        network: list = []
        try:
            obs = ex._restore(session, [desc], network, initial=live)
        except UnsafeRestoration:
            refused.append("unsafe_restoration")
            return "refused", "known_state_change", None
        except RuntimeError:
            return "failed", "control_not_found", None
        flat = [e for s in network for e in s.network]
        entry.requests = self._requests(flat)
        entry.writes = any(e.method.upper() not in {"GET", "HEAD", "OPTIONS"} for e in flat)
        entry.intended["sent"] = any(e.resource_type != "document" for e in flat)
        if experiment:
            ex.artifact.replay_observations.append(obs)
            if independent:
                ok = obs.group_signature == original.result_group_signature
                replay = ReplayResult(
                    id="rp_grounded_" + str(len(ex.artifact.replays)), transition_id=original.id,
                    path_length=len(plan.steps) - 1,
                    status=EvidenceStatus.REPLAY_VALIDATED if ok else EvidenceStatus.FAILED,
                    expected_group_signature=original.result_group_signature or "",
                    actual_group_signature=obs.group_signature, actual_observation_id=obs.id, network=flat,
                    failure_reason=None if ok else "state_mismatch")
                ex.artifact.replays.append(replay)
                entry.replay_id = replay.id
                entry.verification_result = "reproduced" if ok else "mismatch"
            return "succeeded", None, (obs, list(live_path) + [desc])
        ex._record_observation(obs, list(live_path) + [desc])
        return "succeeded", None, (obs, list(live_path) + [desc])

    def _requests(self, events: list) -> list[dict]:
        return [{"method": e.method, "route": urlsplit(self._pseudo(e.url) or "").path,
                 "resource": e.resource_type, "failed": bool(e.failure)} for e in events or []]


class GroundedTourRunner(ActiveTourRunner):
    """Scheduler knowledge from the ledger only; complete executor feedback."""

    def __init__(self, config: Any, sink: Any) -> None:
        super().__init__(config, sink)
        self.ledger = ExecutionLedger()
        self.refusals: dict[str, set] = {}            # question id -> condition fingerprints refused under
        self.repeated_blocked = 0
        self.executor: GroundedExecutor | None = None
        self.sched.st.entered_roles = set()
        self._question_of: dict[str, str] = {}

    def _knowledge(self, records: list[Any], artifact: Any) -> Knowledge:
        """Trails from executed steps: each observation's trail is the steps actually executed to reach it."""
        k = Knowledge()
        obs = {r.obs_id: r for r in records if r.kind == "observation"}
        k.actions = {r.action_id: r for r in records if r.kind == "action"}
        k.replays = {r.replay_id: r for r in records if r.kind == "replay"}
        first = next((r for r in records if r.kind == "observation"), None)
        if first is not None:
            k.obs[first.obs_id] = ObsInfo(record=first, epoch=0, trail=(), doc_entry=True)
            k.order.append(first.obs_id)
        for e in self.ledger.entries:
            if e.outcome != "succeeded" or not e.result_obs or e.result_obs not in obs:
                continue
            prev = k.obs.get(e.source_obs or "")
            base = prev.trail if prev is not None else ()
            rec = obs[e.result_obs]
            if e.op == "fresh":
                info = ObsInfo(record=rec, epoch=e.session.epoch, trail=(), doc_entry=True, prev=e.source_obs)
            elif e.op == "goto":
                keep = base
                while keep and not keep[-1].stateful:
                    keep = keep[:-1]
                info = ObsInfo(record=rec, epoch=e.session.epoch, doc_entry=True, prev=e.source_obs,
                               trail=keep + (TrailStep(op="goto", url=rec.url, obs=e.result_obs),))
            elif e.op == "back":
                # Back undoes the step that produced the source. If that step was a state-free page
                # load and the browser verifiably arrived at its source page, the result's trail is
                # that page's trail (a recorded "back" would depend on history a new context lacks).
                producing = {x.result_obs: x for x in self.ledger.entries
                             if x.outcome == "succeeded" and x.result_obs and x.op in {"click", "goto"}}
                cur, clean, undone = e.source_obs, True, None
                for _ in range(50):                       # skip in-page steps back to the last page load
                    x = producing.get(cur)
                    if x is None:
                        break
                    if x.writes or x.state_changing:
                        clean = False
                    if any(r["resource"] == "document" for r in x.requests) or x.op == "goto":
                        undone = x
                        break
                    cur = x.source_obs
                clean = clean and undone is not None and all(r["method"] == "GET" for r in undone.requests)
                returned = k.obs.get(undone.source_obs) if undone is not None else None
                if returned is not None and clean and returned.record.url and \
                        (e.actual_route, e.actual_record) == (undone.intended.get("source_route"),
                                                              undone.intended.get("source_record")):
                    info = ObsInfo(record=rec, epoch=e.session.epoch, doc_entry=False, prev=e.source_obs,
                                   trail=returned.trail)
                else:
                    info = ObsInfo(record=rec, epoch=e.session.epoch, doc_entry=False, prev=e.source_obs,
                                   trail=base + (TrailStep(op="back", obs=e.result_obs),))
            else:
                action = e.transition_id or e.replay_of
                doc = any(r["resource"] == "document" for r in e.requests)
                stateful = not e.requests or any(r["resource"] != "document" or r["method"] != "GET" for r in e.requests)
                aff = k.actions[e.transition_id].affordance if e.transition_id in k.actions else (
                    k.actions[e.replay_of].affordance if e.replay_of in k.actions else None)
                step = TrailStep(op="click", aff=aff, action=action, stateful=stateful, writes=e.writes or e.state_changing,
                                 url=rec.url if doc else None, obs=e.result_obs,
                                 sent=any(r["resource"] != "document" for r in e.requests))
                info = ObsInfo(record=rec, epoch=e.session.epoch, doc_entry=doc, prev=e.source_obs,
                               trail=base + (step,), via=step, input_free_read=not (e.writes or e.state_changing))
            if e.result_obs not in k.obs:
                k.order.append(e.result_obs)
            k.obs[e.result_obs] = info
        for r in records:                                  # evidence without a ledger step (e.g. legacy-recorded)
            if r.kind == "observation" and r.obs_id not in k.obs:
                k.obs[r.obs_id] = ObsInfo(record=r, epoch=-1, trail=(), doc_entry=False)
                k.order.append(r.obs_id)
        k.epoch = self.executor.epoch if self.executor else 0
        k.blocked_actions = ReachabilityModel.from_ledger(self.ledger).blocked_actions()
        for e in self.ledger.entries:                     # failed restoration routes are not retried
            if e.outcome == "failed" and (e.reason or "").startswith(("restoration_mismatch", "arrived_at_wrong_state")):
                target = e.intended.get("restore_target")
                if e.op == "back" and target:
                    k.blocked_restorations.add(("back", target))
                if e.op == "fresh" and target:
                    k.blocked_restorations.add(("fresh", target))
                if e.op == "goto" and e.intended.get("url"):
                    k.blocked_restorations.add(("goto", e.intended["url"]))
        return k

    def condition(self, live_obs_id: str) -> tuple:
        """The conditions a refusal holds under: browser-context epoch and the live page's structure."""
        obs = self._artifact._observation_by_id(live_obs_id) if hasattr(self._artifact, "_observation_by_id") else None
        obs = obs or next((o for o in list(self._artifact.observations) + list(self._artifact.replay_observations)
                           if o.id == live_obs_id), None)
        return (self.executor.epoch if self.executor else 0, obs.group_signature if obs else None)

    def propose(self, artifact: Any, live_obs_id: str, used: int):
        self.sched.st.entered_roles = {e.session.role for e in self.ledger.entries if e.outcome == "succeeded"} \
            or {self.config.context_label}
        # actual cost of verification plans, including the restoration they needed
        self.sched.verif_actions = sum(e.browser_actions for e in self.ledger.entries if e.plan_kind in VERIFICATION)
        for e in self.ledger.entries:                      # deterministic mismatches are final; transients may retry
            if e.verification_result == "mismatch":
                q = self._question_of.get(e.plan_id)
                if q:
                    self.sched.no_reproduce.add(q)
        fp = self.condition(live_obs_id)
        self.sched.condition = fp
        self.sched.external_conditional = self.refusals
        plan, target = super().propose(artifact, live_obs_id, used)
        if plan is not None and fp in self.refusals.get(plan.question_id or "", set()):
            self.repeated_blocked += 1                 # must stay 0: the scheduler honors the refusal
        return plan, target

    def complete(self, result: Any) -> None:
        pend = self.sched.pending
        super().complete(result)                       # also records the executed outcome on the proposal
        if pend is None or self.executor is None:
            return
        q = pend["q"]
        self._question_of[f"p{self.executor.plans}"] = q.id
        if result.refused or (result.abort_reason or "").startswith(("refused", "known_", "control_unsafe",
                                                                      "unsupported", "record_identity", "budget")):
            reason = result.abort_reason or (result.refused[0] if result.refused else "refused")
            if any(reason.startswith(p) or p in reason for p in PERMANENT_REFUSALS):
                self.sched.external_blocked[q.id] = "executor_refused:" + reason
            else:
                self.refusals.setdefault(q.id, set()).add(self.condition(result.live_obs))
        if (result.abort_reason or "").startswith(("restoration_mismatch", "arrived_at_wrong_state",
                                                    "control_not_found")):
            self.sched.st.minimal_failed.add(q.id)
            # a failed restoration is evidence too: not retried under the same conditions
            self.refusals.setdefault(q.id, set()).add(self.condition(result.live_obs))

