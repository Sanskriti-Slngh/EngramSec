"""Thin executor adapter: runs tour_v2 ExperimentPlans through the legacy browser session.

Every step goes through existing explorer machinery and its safety path:
- experiment clicks: `Explorer._attempt_frontier` from the live state (control
  resolution with `find_current`, known-write suppression, form filling, scope
  checks, transition recording);
- restoration clicks and verification replays: `Explorer._restore` (refuses
  return paths through observed writes; not recorded as transitions, as in
  legacy);
- navigation: `goto_start` / an in-scope `goto` / `go_back`; fresh contexts with
  `reset_context`.
Before each click the intended control is resolved against the current
observation (structure and pseudonymized target), checked against disabled
evidence, the evidence-only risk gate and, for the experiment, the intended
record identity. Unsupported operations (snapshots, other roles, input
variants) are refused, never approximated.
"""
from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlsplit

from agent1.planner.interfaces import ExperimentResult, Step

VERIFICATION = {"reproduce", "verify_effect", "test_dependency", "test_equivalence"}


def _instance(url: str | None) -> tuple:
    from agent1.model.routes import identifier_segments
    return tuple(v for _, _, v in identifier_segments(urlsplit(url or "").path))


class TourExecutor:
    def __init__(self, explorer: Any, runner: Any) -> None:
        self.ex, self.runner = explorer, runner
        self.counters: dict[str, int] = {}

    def _count(self, key: str) -> None:
        self.counters[key] = self.counters.get(key, 0) + 1

    # ------------------------------------------------------------ resolution
    def _resolve(self, observation: Any, aff: Any) -> tuple[Any | None, str | None]:
        sink = self.ex.evidence_sink
        pseudo = (lambda u: sink.pseudo_url(u)) if sink is not None else (lambda u: u)
        same = lambda c: (c.css_path == aff.locator and c.kind == aff.kind and c.component == aff.component
                          and pseudo(c.target) == aff.target)
        for control in observation.controls:
            if same(control):
                return (control, None) if control.safe else (None, "control_unsafe")
        if sink is not None and any(same(c) for c in sink.disabled.get(observation.id, [])):
            return None, "control_disabled"
        return None, "control_not_found"

    def _budget_left(self) -> bool:
        ex = self.ex
        return (ex.artifact.metrics.browser_actions < ex.config.max_browser_actions
                and ex._elapsed() < ex.config.max_seconds
                and not ex._discovery_http_exhausted())

    def _observe(self, session: Any) -> Any:
        # Intermediate restoration pages are not recorded (as in legacy); the plan's final live
        # page is recorded once at the end so the scheduler always has evidence for its live state.
        return session.observe(self.ex._next_sequence())

    # ----------------------------------------------------------------- run
    def run(self, browser: Any, session: Any, plan: Any, live: Any, live_path: list, target_obs: str | None):
        """Execute one plan. Returns (ExperimentResult, live observation, live path)."""
        from agent1.schema import EvidenceStatus, FrontierItem, ReplayResult
        from agent1.explorer import BrowserSession, UnsafeRestoration
        from agent1.state import allowed_origin
        ex = self.ex
        start_actions = ex.artifact.metrics.browser_actions
        before_t, before_r = len(ex.artifact.transitions), len(ex.artifact.replays)
        independent = bool(plan.steps) and plan.steps[0].op == "fresh"
        verification = plan.kind in VERIFICATION
        abort, refused = None, []
        purpose: dict[str, int] = {}
        for index, step in enumerate(plan.steps):
            if not self._budget_left():
                abort = "budget"
                break
            at = ex.artifact.metrics.browser_actions
            # Evidence roles carry session-cookie names after "+"; only the session context is an identity.
            if step.op == "snapshot" or (step.op == "fresh" and (step.role or ex.config.context_label).split("+")[0]
                                         != ex.config.context_label):
                abort = "unsupported_operation:" + step.op
                break
            if step.input is not None or step.oracle_capture is not None:
                abort = "unsupported_input_variant"          # paired-search probes are not executable here
                break
            if step.op == "fresh":
                session.reset_context()
                ex._navigate_start(session, "frontier_restore")
                live, live_path = self._observe(session), []
            elif step.op == "goto":
                raw = self.runner.raw_url(step.url)
                if raw is None or not allowed_origin(ex.config.start_url, raw, ex.config.origin_aliases):
                    abort = "goto_unresolved_or_out_of_scope"
                    break
                ex.artifact.metrics.browser_actions += session.goto(raw)
                ex.artifact.metrics.restoration_actions += 1
                ex._record_navigation_evidence(session, "frontier_restore")
                live = self._observe(session)
                live_path = list(ex.artifact.return_paths.get(live.group_signature, []))
            elif step.op == "back":
                if not session.go_back():
                    abort = "history_unavailable"
                    break
                ex.artifact.metrics.browser_actions += 1
                ex.artifact.metrics.restoration_actions += 1
                ex._record_navigation_evidence(session, "history_return")
                live = self._observe(session)
                live_path = live_path[:-1]
            else:
                control, problem = self._resolve(live, step.affordance)
                if control is None:
                    abort = problem
                    break
                experiment = index == len(plan.steps) - 1
                if experiment and target_obs is not None:
                    target = ex._observation_by_id(target_obs)
                    if target is not None and (_instance(target.url) != _instance(live.url)
                                               or target.route_pattern != live.route_pattern):
                        abort = "record_identity_mismatch"
                        break
                gate_reason = self.runner.gate_check(step, live)
                if gate_reason:
                    refused.append(gate_reason)
                    abort = "refused:" + gate_reason
                    break
                if experiment and not verification:
                    item = FrontierItem(source_observation_id=live.id, expected_source_signature=live.state_signature,
                                        expected_source_group=live.group_signature, path=list(live_path),
                                        action=BrowserSession.descriptor(control))
                    count_before = len(ex.artifact.transitions)
                    updated = ex._attempt_frontier(browser, item, persistent_session=session, live_source=live,
                                                   live_path=live_path)
                    if updated is None:
                        ex.artifact.metrics.live_state_stale += 1
                        ex._navigate_start(session, "persistent_restore")
                        live, live_path = self._observe(session), []
                        abort = "live_state_stale"
                        break
                    live, observed = updated
                    live_path = list(ex.artifact.return_paths.get(live.group_signature, observed))
                    if len(ex.artifact.transitions) == count_before:
                        abort = "suppressed_by_legacy_safety"     # e.g. a known write is never repeated
                        refused.append("known_write_suppressed")
                        break
                    if ex.artifact.transitions[-1].status != EvidenceStatus.OBSERVED:
                        abort = "action_failed"
                        break
                else:
                    original = next((t for t in ex.artifact.transitions if t.id == step.replay_of), None)
                    if original is None and experiment:
                        abort = "replay_target_unknown"      # a verification target must be a recorded action
                        break
                    # A restoration step without a recorded original replays the resolved live control
                    # through the same guarded path.
                    descriptor = original.action if original is not None else BrowserSession.descriptor(control)
                    network: list = []
                    try:
                        observation = ex._restore(session, [descriptor], network, initial=live)
                    except UnsafeRestoration:
                        refused.append("unsafe_restoration")
                        abort = "refused:unsafe_restoration"
                        break
                    except RuntimeError:
                        abort = "control_not_found"
                        break
                    if experiment:
                        ex.artifact.replay_observations.append(observation)
                        if independent:
                            ok = observation.group_signature == original.result_group_signature
                            ex.artifact.replays.append(ReplayResult(
                                id="rp_tour_" + str(len(ex.artifact.replays)), transition_id=original.id,
                                path_length=len(plan.steps) - 1,
                                status=EvidenceStatus.REPLAY_VALIDATED if ok else EvidenceStatus.FAILED,
                                expected_group_signature=original.result_group_signature or "",
                                actual_group_signature=observation.group_signature,
                                actual_observation_id=observation.id,
                                network=[e for s in network for e in s.network],
                                browser_actions=ex.artifact.metrics.browser_actions - start_actions,
                                failure_reason=None if ok else "state_mismatch"))
                        else:
                            self._count("replay_not_independent_not_recorded")
                    else:
                        live_path = list(live_path) + [descriptor]
                    live = observation
            purpose[step.purpose] = purpose.get(step.purpose, 0) + ex.artifact.metrics.browser_actions - at
        self._count(abort or "completed")
        recorded = {o.id for o in ex.artifact.observations} | {o.id for o in ex.artifact.replay_observations}
        if live.id not in recorded:
            ex._record_observation(live, list(live_path))
        records, action_ids, replay_ids = self.runner.sync_new(ex.artifact, before_t, before_r)
        result = ExperimentResult(records=records, actions=ex.artifact.metrics.browser_actions - start_actions,
                                  completed=abort is None, abort_reason=abort, refused=refused, live_obs=live.id,
                                  action_ids=action_ids, replay_ids=replay_ids, purpose_actions=purpose)
        return result, live, live_path
