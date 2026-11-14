"""Shadow-mode Capability Tour Scheduler (Phase 2, opt-in `shadow_tours`).

The legacy frontier remains the only component that executes actions. At each
legacy decision point the runner:
1. syncs the live ACG with the explorer's own evidence;
2. rebuilds the scheduler's knowledge of navigation trails from the legacy
   transitions (both policies see the same observable evidence);
3. asks `tour_v2` for a proposal and records it with its feasibility from the
   live state, restoration cost, prerequisite progress and risk tier;
4. never resolves the proposal: its outcome is unknown and is not inferred.
After the legacy action, the proposal is compared with what legacy did
(agreement is reported, never scored as success).
"""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from agent1.model.schema import STATUS_RANK, Status
from agent1.planner.gate import writes as writes_request
from agent1.planner.interfaces import AgentView, Costs, Isolation
from agent1.planner.knowledge import Knowledge, ObsInfo, TrailStep, stateful
from agent1.planner.tours import TourScheduler

from .acg import LiveACG

SUPPORTED_OPS = {"click", "goto", "back", "fresh"}       # what the legacy executor can do; no snapshots


class ShadowRunner:
    def __init__(self, config: Any, sink: Any) -> None:
        self.config = config
        self.live = LiveACG(application="live", sink=sink)
        self.iso = Isolation(level=0, exploratory_writes=bool(config.allow_post_forms), snapshot=False,
                             roles=[config.context_label], default_role=config.context_label, start_url="/")
        self.sched = TourScheduler(self.iso, Costs(), config.max_browser_actions, seed=0, mode="v2")
        self.sched.started = True                 # knowledge is rebuilt from legacy evidence below
        self.proposals: list[dict[str, Any]] = []
        self.pending: dict[str, Any] | None = None
        self.decide_ms: list[float] = []
        self.counters: Counter = Counter()

    # ------------------------------------------------------------ knowledge
    def _knowledge(self, records: list[Any], artifact: Any) -> Knowledge:
        """Trails of every observation, reconstructed from legacy transitions and their workflow paths."""
        k = Knowledge()
        obs = {r.obs_id: r for r in records if r.kind == "observation"}
        actions = {r.action_id: r for r in records if r.kind == "action"}
        k.actions = dict(actions)
        k.replays = {r.replay_id: r for r in records if r.kind == "replay"}
        by_locator: dict[tuple, str] = {}
        epoch = 0
        fresh_mode = getattr(self.config, "exploration_mode", "fresh") == "fresh"

        def step(action_id: str | None, aff: Any) -> TrailStep:
            rec = actions.get(action_id or "")
            url_doc = bool(rec and any(q.resource_type == "document" for q in rec.requests or []))
            return TrailStep(op="click", aff=aff, action=action_id, stateful=stateful(rec),
                             writes=bool(rec and writes_request(rec)),
                             url=None if not url_doc or rec is None or rec.result_obs not in obs
                             else obs[rec.result_obs].url,
                             obs=rec.result_obs if url_doc and rec else None,
                             sent=bool(rec and any(q.resource_type != "document" for q in rec.requests or [])))
        prev = None
        for r in records:
            if r.kind == "observation" and r.obs_id not in k.obs:
                k.obs[r.obs_id] = ObsInfo(record=r, epoch=epoch, trail=(), doc_entry=True, prev=prev)
                k.order.append(r.obs_id)
                prev = r.obs_id
            elif r.kind == "action" and r.status == "observed":
                t = next((x for x in artifact.transitions if x.id == r.action_id), None)
                path = []
                for d in (t.workflow_path if t else []):
                    path.append(step(by_locator.get((d.css_path, d.kind, d.component)), self._aff(d)))
                if t is not None and t.restoration_attempted and fresh_mode:
                    epoch += 1
                src = k.obs.get(r.source_obs or "")
                if src is not None and not src.trail and path:
                    src.trail, src.epoch, src.doc_entry = tuple(path), epoch, False
                res = k.obs.get(r.result_obs or "")
                if res is not None and src is not None:
                    s = step(r.action_id, r.affordance)
                    res.trail, res.epoch, res.prev, res.via = src.trail + (s,), src.epoch, src.record.obs_id, s
                    res.doc_entry = s.url is not None
                    res.input_free_read = not s.writes and not (r.affordance.fields if r.affordance else [])
                if r.affordance is not None:
                    by_locator.setdefault((r.affordance.locator, r.affordance.kind, r.affordance.component),
                                          r.action_id)
        k.epoch = epoch
        return k

    def _aff(self, descriptor: Any) -> Any:
        from agent1.model.importer import _affordance
        a = _affordance(descriptor.model_dump(mode="json"))
        return a.model_copy(update={"target": self.live._pseudo(a.target)})

    # -------------------------------------------------------------- decide
    def decide(self, artifact: Any, live_obs_id: str, used: int) -> None:
        start = time.perf_counter()
        self.live.sync(artifact)
        acg = self.live.export()
        records = self.live.records()
        self.sched.k = self._knowledge(records, artifact)
        self.sched._last_obs_seen = 0
        if live_obs_id not in self.sched.k.obs:
            # Legacy reset to a page it did not record as an observation: no evidence for the live state.
            self.counters["live_state_not_recorded"] += 1
            self.pending = {"t": len(self.proposals), "live_obs": live_obs_id, "used": used, "proposal": None,
                            "feasibility": "live_state_not_recorded"}
            self.proposals.append(self.pending)
            return
        view = AgentView.model_construct(records=records, acg=acg, live_obs=live_obs_id,
                                         remaining=max(0, self.config.max_browser_actions - used), used=used,
                                         isolation=self.iso, costs=Costs())
        try:
            plan = self.sched.next(view)
        except Exception as exc:                       # recorded, never allowed to affect the explorer
            self.counters["scheduler_errors"] += 1
            self.proposals.append({"t": len(self.proposals), "error": repr(exc)[:200]})
            return
        self.sched.pending = None                      # an unexecuted proposal has no outcome
        entry = self.sched.log[-1] if self.sched.log else {}
        record = {"t": len(self.proposals), "live_obs": live_obs_id, "used": used,
                  "acg_capabilities": len(acg.capabilities), "acg_templates": len(acg.templates),
                  "capture_gaps": sorted(g.kind for g in acg.gaps)}
        if plan is None:
            record.update({"proposal": None, "feasibility": "no_feasible_question",
                           "open": entry.get("open"), "mode": entry.get("mode")})
        else:
            record.update(self._describe(plan, entry, live_obs_id, artifact))
        record["decide_ms"] = round((time.perf_counter() - start) * 1000, 2)
        self.decide_ms.append(record["decide_ms"])
        self.proposals.append(record)
        self.pending = record

    def _describe(self, plan: Any, entry: dict, live_obs_id: str, artifact: Any) -> dict[str, Any]:
        chosen = entry.get("chosen", {})
        ops = [s.op for s in plan.steps]
        experiment = next((s for s in reversed(plan.steps) if s.op == "click" and not s.replay_of), None) or \
            next((s for s in reversed(plan.steps) if s.op == "click"), None)
        known_actions = {t.id for t in artifact.transitions}
        replays_known = all(s.replay_of in known_actions for s in plan.steps if s.replay_of)
        restoration = chosen.get("restoration", {})
        if any(op not in SUPPORTED_OPS for op in ops):
            feasibility = "unsupported_by_executor"
        elif restoration.get("kind") == "stay":
            live = next((o for o in reversed(artifact.observations) if o.id == live_obs_id), None)
            present = experiment is not None and live is not None and any(
                c.css_path == experiment.affordance.locator and c.kind == experiment.affordance.kind
                for c in live.controls)
            feasibility = "executable_now" if present else "control_missing_in_live_state"
        elif replays_known:
            feasibility = "executable_with_restoration"
        else:
            feasibility = "restoration_unresolved"
        reason = entry.get("reason", "")
        return {"proposal": {"question": chosen.get("q"), "kind": chosen.get("kind"), "reason": reason,
                             "evidence": chosen.get("evidence"), "risk_tier": chosen.get("tier"),
                             "risk": chosen.get("risk"), "restoration": restoration,
                             "plan_ops": ops, "plan_actions": chosen.get("plan_actions"),
                             "target": {"kind": experiment.affordance.kind, "locator": experiment.affordance.locator}
                             if experiment else None},
                "feasibility": feasibility,
                "prerequisite_progress": reason.endswith("prerequisite_progress"),
                "context_preserving": reason.startswith("continue") or restoration.get("kind") in {"stay", "back"},
                "open_discovery": entry.get("open_discovery"), "open_verification": entry.get("open_verification"),
                "infeasible_discovery": (entry.get("considered") or {}).get("infeasible_discovery"),
                "blocked_verification": dict((entry.get("considered") or {}).get("blocked_verification") or {})}

    # -------------------------------------------------------------- compare
    def after_action(self, artifact: Any, transitions_before: int) -> None:
        """Compare the pending proposal with what legacy actually executed (no outcome inference)."""
        if self.pending is None:
            return
        done = artifact.transitions[transitions_before:]
        pend, self.pending = self.pending, None
        if not done:
            pend["legacy"] = {"executed": False}
            return
        t = done[-1]
        target = (pend.get("proposal") or {}).get("target")
        same = bool(target) and target["locator"] == t.action.css_path and target["kind"] == t.action.kind
        pend["legacy"] = {"executed": True, "status": str(t.status), "restoration": t.restoration_attempted,
                          "same_control": same}
        if pend.get("prerequisite_progress") and not same:
            self.counters["prerequisite_progress_not_taken_by_legacy"] += 1
        if pend.get("context_preserving") and t.restoration_attempted and not same:
            self.counters["context_preservation_opportunity"] += 1

    # ---------------------------------------------------------------- finish
    def finish(self, artifact: Any, output_dir: Path) -> dict[str, Any]:
        self.live.sync(artifact)
        acg = self.live.export()
        output_dir.mkdir(parents=True, exist_ok=True)
        self.live.write(output_dir / "acg_evidence.jsonl")
        (output_dir / "live_acg.json").write_text(acg.model_dump_json(indent=1))
        with (output_dir / "shadow_decisions.jsonl").open("w") as fh:
            for p in self.proposals:
                fh.write(json.dumps(p, sort_keys=True, default=str) + "\n")
        props = [p for p in self.proposals if "error" not in p]
        feas = Counter(p["feasibility"] for p in props)
        made = [p for p in props if p.get("proposal")]
        summary = {
            "decisions": len(self.proposals), "scheduler_errors": self.counters["scheduler_errors"],
            "feasibility": dict(feas),
            "proposal_kinds": dict(Counter(p["proposal"]["kind"] for p in made)),
            "agreement_same_control": sum(bool((p.get("legacy") or {}).get("same_control")) for p in made),
            "compared": sum(bool((p.get("legacy") or {}).get("executed")) for p in made),
            "prerequisite_progress_proposals": sum(p.get("prerequisite_progress", False) for p in made),
            "context_preserving_proposals": sum(p.get("context_preserving", False) for p in made),
            "mean_proposed_plan_actions": round(sum(p["proposal"]["plan_actions"] or 0 for p in made) / len(made), 2)
            if made else None,
            "mean_proposed_restoration_actions": round(sum((p["proposal"]["restoration"] or {}).get("actions", 0)
                                                           for p in made) / len(made), 2) if made else None,
            "risk_tiers": dict(Counter(p["proposal"]["risk_tier"] for p in made)),
            "counters": dict(self.counters),
            "global_navigation_suppressed": len(self.sched.global_suppressed),
            "acg": acg.summary, "capture_gaps": sorted(g.kind for g in acg.gaps),
            "acg_update_ms": {"mean": round(sum(self.live.latencies_ms) / len(self.live.latencies_ms), 2)
                              if self.live.latencies_ms else None,
                              "max": round(max(self.live.latencies_ms), 2) if self.live.latencies_ms else None},
            "decide_ms": {"mean": round(sum(self.decide_ms) / len(self.decide_ms), 2) if self.decide_ms else None,
                          "max": round(max(self.decide_ms), 2) if self.decide_ms else None},
            "sink": self.live.sink.summary() if self.live.sink is not None else None,
        }
        (output_dir / "shadow_summary.json").write_text(json.dumps(summary, indent=1, default=str))
        return summary


class ActiveTourRunner(ShadowRunner):
    """Same decision path as shadow mode, but the scheduler keeps its pending question so the
    executed result can be resolved, and the plan is returned for execution."""

    def __init__(self, config: Any, sink: Any) -> None:
        super().__init__(config, sink)
        self.sched = TourScheduler(self.iso, Costs(), config.max_browser_actions, seed=config.tour_seed, mode="v2")
        self.sched.started = True
        self._seen_records: set[str] = set()

    def propose(self, artifact: Any, live_obs_id: str, used: int):
        self.live.sync(artifact)
        acg = self.live.export()
        records = self.live.records()
        self._seen_records = {r.id for r in records}
        self.sched.k = self._knowledge(records, artifact)
        self.sched._last_obs_seen = 0
        if live_obs_id not in self.sched.k.obs:
            self.counters["live_state_not_recorded"] += 1
            return None, None
        view = AgentView.model_construct(records=records, acg=acg, live_obs=live_obs_id,
                                         remaining=max(0, self.config.max_browser_actions - used), used=used,
                                         isolation=self.iso, costs=Costs())
        start = time.perf_counter()
        plan = self.sched.next(view)
        self.decide_ms.append(round((time.perf_counter() - start) * 1000, 2))
        entry = self.sched.log[-1] if self.sched.log else {}
        record = {"t": len(self.proposals), "live_obs": live_obs_id, "used": used}
        record.update({"proposal": None, "feasibility": "no_feasible_question"} if plan is None
                      else self._describe(plan, entry, live_obs_id, artifact))
        self.proposals.append(record)
        target = (self.sched.pending or {}).get("target_obs")
        return plan, target

    def complete(self, result: Any) -> None:
        if self.sched.pending is not None:
            self.sched.pending["result"] = result
            if self.sched.pending["q"].kind in {"reproduce", "verify_effect", "test_dependency", "test_equivalence"}:
                self.sched.verif_actions += result.actions      # same accounting as TourScheduler.update
            if result.refused and result.actions == 0:
                self.sched.external_blocked[self.sched.pending["q"].id] = "executor_refused:" + result.refused[0]
        if self.proposals:
            self.proposals[-1]["executed"] = {"actions": result.actions, "completed": result.completed,
                                              "abort": result.abort_reason, "refused": result.refused}

    def raw_url(self, pseudo: str | None) -> str | None:
        if not pseudo:
            return None
        if pseudo == self.iso.start_url:
            return self.config.start_url                 # the scheduler's name for the configured start page
        art = self._artifact
        for o in list(art.observations) + list(art.replay_observations):
            if self.live._pseudo(o.url) == pseudo:
                return o.url
            for c in o.controls:
                if c.target and self.live._pseudo(c.target) == pseudo:
                    return c.target
        return None

    def gate_check(self, step: Any, live: Any) -> str | None:
        return self.sched.gate.check(step, self.live._pseudo(live.url), False)

    def sync_new(self, artifact: Any, before_t: int, before_r: int):
        self.live.sync(artifact)
        records = [r for r in self.live.records() if r.id not in self._seen_records]
        return records, [t.id for t in artifact.transitions[before_t:]], [r.id for r in artifact.replays[before_r:]]
