"""Evidence-driven replay scheduling by request structure.

Exploration records, for every executed action, the requests it caused.
Replay re-executes recorded workflows in a fresh browser context. The legacy
order is shallowest-first, so a behavior that is only reachable several
actions deep (a control created by an earlier click, a replaced handler) is
reached only after every shallower workflow, and is usually cut off by the
action budget.

This scheduler gives replay two lanes that share the replay budget by action
cost:

* **structure lane**: greedy coverage of distinct, not yet verified request
  structures. Among workflows that demonstrate an unverified structure it
  picks the one with the most unverified structures per browser action. A
  structure that a validated replay reproduced is verified and no workflow is
  replayed again for it; a structure whose replays failed `max_attempts`
  times is given up and recorded as such.
* **shallow lane**: the existing shallowest-first order, unchanged, so
  ordinary navigation and prerequisite workflows are not starved. Under this
  policy it skips request-only workflows whose structures are all verified
  or given up (they would only repeat equivalent evidence or a known failure).

The next replay comes from the lane that has spent fewer browser actions
(structure lane on ties). Nothing here reads expected benchmark paths: inputs
are only Agent 1's own transitions and their recorded network evidence.

A request structure is privacy-preserving: initiator class, HTTP method,
route pattern (instance-like path segments and query values removed),
parameter names and body encoding class. Never values, bodies or cookies.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

from .state import route_pattern

SCRIPT_TYPES = {"xhr", "fetch"}


def request_structure_key(event: Any) -> str | None:
    """Normalized structure of one recorded request, or None when the request
    is not behavioral evidence (static GET subresources, plain navigations
    without parameters, requests with no response)."""
    method = event.method.upper()
    if event.status is None or event.failure:
        return None
    script = event.resource_type in SCRIPT_TYPES
    parameterized_document = event.resource_type == "document" and bool(event.parameter_names)
    if not (script or method not in {"GET", "HEAD"} or parameterized_document):
        return None
    initiator = "script" if script else (event.resource_type or "other")
    params = ",".join(event.parameter_names)
    return f"{initiator} {method} {route_pattern(event.url).split('?', 1)[0]} [{params}] {event.body_encoding or '-'}"


def request_structures(network: Iterable[Any]) -> set[str]:
    return {key for event in network if (key := request_structure_key(event))}


def structure_paths(network: Iterable[Any], structures: set[str]) -> dict[str, set[str]]:
    """Concrete request paths per structure (record identity), without query values."""
    from urllib.parse import urlsplit

    paths: dict[str, set[str]] = {}
    for event in network:
        key = request_structure_key(event)
        if key in structures:
            paths.setdefault(key, set()).add(urlsplit(event.url).path)
    return paths


def workflow_key(path: Iterable[Any]) -> tuple:
    return tuple((d.control_id, d.signature, d.interaction, getattr(d, "behavior_revision", None)) for d in path)


def state_changing_workflows(transitions: Iterable[Any]) -> set[tuple]:
    """Exact recorded workflows (as keys) whose final action issued a non-GET
    request during exploration. Keyed by the whole path, not the action
    signature: two "Submit" buttons on different pages are different steps."""
    return {workflow_key(t.workflow_path) for t in transitions
            if any(e.method.upper() not in {"GET", "HEAD"} for e in t.network)}


def workflow_changes_state(transition: Any, changing: set[tuple]) -> bool:
    """True when replaying the workflow would repeat a step that was observed
    changing application state (the step itself or any prerequisite)."""
    path = list(transition.workflow_path)
    if any(event.method.upper() not in {"GET", "HEAD"}
           for step in getattr(transition, "prerequisite_network", []) for event in step.network):
        return True
    return any(workflow_key(path[:k]) in changing for k in range(1, len(path) + 1))


@dataclass
class ReplayItem:
    transition: Any
    lane: str
    cost: int
    target_structures: list[str] = field(default_factory=list)


@dataclass
class _Candidate:
    transition: Any
    structures: set[str]
    cost: int
    eligible: bool


class ReplayScheduler:
    def __init__(self, structure_pool: list[tuple[Any, set[str], int, bool]],
                 shallow_order: list[tuple[Any, int]], *, max_attempts: int = 2):
        self.pool = [_Candidate(t, set(s), c, e) for t, s, c, e in structure_pool if s]
        self.shallow = list(shallow_order)
        self.max_attempts = max_attempts
        self.verified: set[str] = set()
        self.attempts: Counter[str] = Counter()
        self.failures: dict[str, list[str]] = {}
        self.given_up: set[str] = set()
        self.done: set[str] = set()
        self.spent = {"structure": 0, "shallow": 0}
        self.scheduled = {"structure": 0, "shallow": 0}
        self.skipped_equivalent = 0
        self.observed = set().union(*(c.structures for c in self.pool)) if self.pool else set()
        self.ineligible = {s for c in self.pool if not c.eligible for s in c.structures} - {
            s for c in self.pool if c.eligible for s in c.structures}

    def _open(self, structures: set[str]) -> set[str]:
        return structures - self.verified - self.given_up

    def _structure_item(self) -> ReplayItem | None:
        best: tuple[Any, ...] | None = None
        for candidate in self.pool:
            if candidate.transition.id in self.done or not candidate.eligible:
                continue
            new = self._open(candidate.structures)
            if not new:
                continue
            key = (-len(new) / candidate.cost, candidate.cost, candidate.transition.id)
            if best is None or key < best[0]:
                best = (key, candidate, new)
        if best is None:
            return None
        _, candidate, new = best
        return ReplayItem(candidate.transition, "structure", candidate.cost, sorted(new))

    def _shallow_item(self, structures_of) -> ReplayItem | None:
        while self.shallow:
            transition, cost = self.shallow[0]
            if transition.id in self.done:
                self.shallow.pop(0)
                continue
            structures, request_only = structures_of(transition)
            if request_only and structures and not self._open(structures):
                # Every structure it would show is verified or was given up.
                self.shallow.pop(0)
                self.done.add(transition.id)
                self.skipped_equivalent += 1
                continue
            return ReplayItem(transition, "shallow", cost, sorted(self._open(structures)))
        return None

    def next(self, structures_of) -> ReplayItem | None:
        """`structures_of(transition) -> (structures, request_only)`."""
        structure = self._structure_item()
        shallow = self._shallow_item(structures_of)
        if structure is None:
            return shallow
        if shallow is None:
            return structure
        return structure if self.spent["structure"] <= self.spent["shallow"] else shallow

    def skip(self, item: ReplayItem) -> None:
        """The item did not fit the remaining budget; never offer it again."""
        self.done.add(item.transition.id)

    def record(self, item: ReplayItem, validated: bool, reproduced: set[str], actions: int,
               reason: str | None = None) -> None:
        self.done.add(item.transition.id)
        self.spent[item.lane] += actions
        self.scheduled[item.lane] += 1
        if validated:
            self.verified |= reproduced
            return
        for structure in item.target_structures:
            self.attempts[structure] += 1
            self.failures.setdefault(structure, []).append(reason or "unknown")
            if self.attempts[structure] >= self.max_attempts:
                self.given_up.add(structure)

    def summary(self) -> dict[str, Any]:
        unattempted = self.observed - self.verified - set(self.attempts)
        return {
            "structures_observed": len(self.observed),
            "structures_verified": len(self.verified & self.observed),
            "structures_failed": len((set(self.attempts) - self.verified) & self.observed),
            "structures_given_up": len(self.given_up - self.verified),
            "structures_unattempted": len(unattempted),
            "structures_ineligible": len(self.ineligible),
            "lane_actions": dict(self.spent),
            "lane_replays": dict(self.scheduled),
            "equivalent_replays_skipped": self.skipped_equivalent,
        }
