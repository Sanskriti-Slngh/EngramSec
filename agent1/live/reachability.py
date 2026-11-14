"""Reachability model derived only from executed steps in the ledger.

An edge is (source state, action) -> destination state, where a state is
(route pattern, record identity, role). It records whether it is tied to a
record or a session, whether it changed state, its evidence, and how often it
succeeded or failed — separately for the original context and for independent
(fresh-context) replays. An edge is never promoted by planning: only executed
evidence changes it. `reusable` is false for state-changing edges, for edges
with a deterministic failure and no later success, and, across contexts, for
session-bound edges that were never reproduced independently.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from .ledger import ExecutionLedger, StepExecution

DETERMINISTIC_FAILURES = ("arrived_at_wrong_state", "control_not_found", "control_disabled", "restoration_mismatch")


def state_key(route: str | None, record: list[str] | None, role: str) -> str:
    return json.dumps([route or "", list(record or []), role])


class Edge(BaseModel):
    source: str
    destination: str | None
    action: dict[str, Any]
    record_bound: bool
    session_bound: bool
    changes_state: bool
    evidence: list[list[Any]] = Field(default_factory=list)
    attempts: int = 0
    successes_same_context: int = 0
    successes_independent: int = 0
    failures: int = 0
    failure_reasons: list[str] = Field(default_factory=list)
    last_outcome: str | None = None
    action_ids: list[str] = Field(default_factory=list)       # recorded actions this edge was executed as

    def reusable(self, independent: bool) -> bool:
        if self.changes_state:
            return False
        if self.last_outcome == "failed" and any(r.startswith(DETERMINISTIC_FAILURES) for r in self.failure_reasons[-1:]):
            return False
        if independent and self.session_bound and not self.successes_independent:
            return False
        return self.successes_same_context + self.successes_independent > 0


class ReachabilityModel:
    def __init__(self) -> None:
        self.edges: dict[str, Edge] = {}

    @staticmethod
    def _action(e: StepExecution) -> dict[str, Any]:
        i = e.intended
        return {"op": e.op, "kind": i.get("kind"), "locator": i.get("locator"), "component": i.get("component"),
                "target": i.get("target"), "url": i.get("url")}

    def add(self, e: StepExecution, independent: bool, session_dirty: bool, source_disabled: bool) -> None:
        if e.outcome == "not_attempted" or e.op in {"fresh", "snapshot"}:
            return
        source = state_key(e.intended.get("source_route"), e.intended.get("source_record"), e.session.role)
        action = self._action(e)
        key = json.dumps([source, action], sort_keys=True)
        edge = self.edges.get(key)
        if edge is None:
            edge = self.edges[key] = Edge(
                source=source, destination=None, action=action,
                record_bound=bool(e.intended.get("source_record")) or bool(e.actual_record),
                session_bound=session_dirty or source_disabled, changes_state=e.writes or e.state_changing)
        edge.attempts += 1
        edge.evidence.append([e.plan_id, e.step_index])
        for a in (e.replay_of, e.transition_id):
            if a and a not in edge.action_ids:
                edge.action_ids.append(a)
        edge.changes_state = edge.changes_state or e.writes or e.state_changing
        edge.session_bound = edge.session_bound or session_dirty or source_disabled
        if e.outcome == "succeeded":
            edge.destination = state_key(e.actual_route, e.actual_record, e.session.role)
            if independent:
                edge.successes_independent += 1
            else:
                edge.successes_same_context += 1
        elif e.outcome in {"failed", "stale"}:
            edge.failures += 1
            edge.failure_reasons.append(e.reason or e.outcome)
        edge.last_outcome = "succeeded" if e.outcome == "succeeded" else (
            "failed" if e.outcome in {"failed", "stale"} else edge.last_outcome)

    @classmethod
    def from_ledger(cls, ledger: ExecutionLedger) -> "ReachabilityModel":
        model = cls()
        independent, dirty, epoch = False, False, None
        plan = None
        for e in ledger.entries:
            if e.plan_id != plan:
                plan = e.plan_id
                independent = e.op == "fresh" and e.outcome == "succeeded"
            if e.session.epoch != epoch:
                epoch, dirty = e.session.epoch, False
            model.add(e, independent, dirty, bool(e.intended.get("source_has_disabled")))
            if e.outcome == "succeeded" and (e.writes or e.state_changing or e.intended.get("sent")):
                dirty = True                      # later steps in this context may depend on it
        return model

    def blocked_actions(self) -> set[str]:
        """Recorded action ids whose replay must not be planned again without new evidence."""
        out: set[str] = set()
        for edge in self.edges.values():
            if not edge.reusable(independent=False) and edge.attempts:
                out.update(edge.action_ids)
        return out

    def summary(self) -> dict[str, Any]:
        edges = list(self.edges.values())
        return {"edges": len(edges), "reusable": sum(e.reusable(False) for e in edges),
                "reusable_independently": sum(e.reusable(True) for e in edges),
                "state_changing": sum(e.changes_state for e in edges),
                "session_bound": sum(e.session_bound for e in edges),
                "with_failures": sum(e.failures > 0 for e in edges)}

    def dump(self) -> dict[str, Any]:
        return {k: v.model_dump(mode="json") for k, v in sorted(self.edges.items())}
