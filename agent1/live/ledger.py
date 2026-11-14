"""Step-level execution ledger: one typed record per planned step.

The source of truth for what the browser actually did. A plan containing a step
proves nothing; only an entry with `stage >= executed` does, and only its own
`result_obs` is evidence of the state it reached. Refused, failed, stale and
unsupported steps are recorded with zero or more browser actions; steps after a
stop are recorded as `not_attempted`. No raw credentials, cookie values or
payload values are stored: targets and URLs are pseudonymized, cookies appear
only as a digest of their names.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

Stage = Literal["planned", "attempted", "executed", "observed"]
Outcome = Literal["succeeded", "refused", "failed", "stale", "unsupported", "not_attempted"]
STAGES = ("planned", "attempted", "executed", "observed")


class SessionRef(BaseModel):
    """Structured session identity (never cookie values)."""
    epoch: int                         # browser-context epoch; a reset starts a new one
    role: str                          # declared role label of this context
    account_ref: str | None = None     # digest of the operator-provided account/session source
    cookie_names_digest: str | None = None


class StepExecution(BaseModel):
    plan_id: str
    step_index: int
    op: str
    plan_kind: str = "explore"         # the question kind the plan answers
    purpose: Literal["restoration", "discovery", "verification"]
    intended: dict[str, Any]
    resolved_control: dict[str, Any] | None = None
    source_obs: str | None = None
    result_obs: str | None = None
    session: SessionRef
    expected_route: str | None = None
    expected_record: list[str] | None = None
    actual_route: str | None = None
    actual_record: list[str] | None = None
    stage: Stage = "planned"
    outcome: Outcome = "not_attempted"
    reason: str | None = None
    transition_id: str | None = None
    replay_id: str | None = None
    replay_of: str | None = None
    requests: list[dict[str, Any]] = Field(default_factory=list)   # method + pseudonymized route only
    writes: bool = False
    state_changing: bool = False
    browser_actions: int = 0
    http_used: int = 0
    elapsed_ms: float = 0.0
    verification_result: Literal["reproduced", "mismatch", "transient"] | None = None

    @property
    def key(self) -> tuple[str, int]:
        return self.plan_id, self.step_index


class ExecutionLedger:
    def __init__(self) -> None:
        self.entries: list[StepExecution] = []

    def append(self, entry: StepExecution) -> None:
        self.entries.append(entry)

    def plan(self, plan_id: str) -> list[StepExecution]:
        return [e for e in self.entries if e.plan_id == plan_id]

    def save(self, path: Path) -> None:
        path.write_text("".join(json.dumps(e.model_dump(mode="json"), sort_keys=True) + "\n" for e in self.entries))

    @classmethod
    def load(cls, path: Path) -> "ExecutionLedger":
        ledger = cls()
        for line in path.read_text().splitlines():
            if line.strip():
                ledger.append(StepExecution.model_validate_json(line))
        return ledger

    def integrity(self) -> list[str]:
        """Contract violations (empty when the ledger is consistent)."""
        problems, keys, evidence = [], set(), {}
        for e in self.entries:
            if e.key in keys:
                problems.append(f"duplicate result for step {e.key}")
            keys.add(e.key)
            if e.outcome == "succeeded" and e.stage != "observed":
                problems.append(f"success without an observed result {e.key}")
            if e.stage == "observed" and not e.result_obs:
                problems.append(f"observed stage without a result observation {e.key}")
            if e.outcome in {"refused", "unsupported", "not_attempted"} and e.browser_actions:
                problems.append(f"browser actions charged to a step that never executed {e.key}")
            if e.outcome in {"refused", "unsupported", "not_attempted"} and (e.transition_id or e.replay_id):
                problems.append(f"evidence attached to a step that never executed {e.key}")
            for ev in (e.transition_id, e.replay_id):
                if ev:
                    if ev in evidence:
                        problems.append(f"evidence {ev} assigned to {evidence[ev]} and {e.key}")
                    evidence[ev] = e.key
        by_plan: dict[str, list[StepExecution]] = {}
        for e in self.entries:
            by_plan.setdefault(e.plan_id, []).append(e)
        for plan_id, steps in by_plan.items():
            idx = sorted(s.step_index for s in steps)
            if idx != list(range(len(idx))):
                problems.append(f"plan {plan_id} has missing step results {idx}")
            stopped = False
            for s in sorted(steps, key=lambda s: s.step_index):
                if stopped and s.outcome != "not_attempted":
                    problems.append(f"step after a stop was executed {s.key}")
                if s.outcome != "succeeded":
                    stopped = True
        return problems


def cookie_digest(names: list[str]) -> str | None:
    return hashlib.sha256(",".join(sorted(names)).encode()).hexdigest()[:12] if names else None
