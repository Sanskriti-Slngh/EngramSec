"""Per-step risk gate shared by every selector (PROPOSED_APPLICATION_MODEL.md §6.2).

It reads only the evidence log and the adapter's isolation declaration:
- controls the extractor marked unsafe, and disabled controls, are never clicked;
- a control that has been observed sending a write-capable request is never
  re-executed, unless the plan began from an adapter snapshot that passed its
  start-state verification and the isolation level is at least L3;
- an untested form that may write runs only if the operator allowed
  exploratory writes (the first-observation rule).
"""
from __future__ import annotations

from urllib.parse import urlsplit

from agent1.model.evidence import AffordanceEvidence, Record
from agent1.model.routes import path_route, strip_positions

from .interfaces import Isolation, Step

READ_METHODS = {"GET", "HEAD", "OPTIONS"}


def control_key(source_url: str | None, aff: AffordanceEvidence) -> tuple:
    """Structural identity of a control on a page template (no display text)."""
    target = path_route(urlsplit(aff.target).path) if aff.target else ""
    locator = strip_positions(aff.locator) if "{id}" in target else aff.locator
    return (path_route(urlsplit(source_url or "").path), aff.kind, aff.interaction, aff.component, locator, target,
            (aff.method or "").upper(), tuple(f.name for f in aff.fields))


def writes(record: Record) -> bool:
    return any(q.channel == "websocket_send" or (q.method or "GET").upper() not in READ_METHODS
               for q in record.requests or [])


class RiskGate:
    def __init__(self, isolation: Isolation) -> None:
        self.isolation = isolation
        self.known_writes: set[tuple] = set()
        self._obs_url: dict[str, str] = {}
        self._seen = 0
        self.refusals: list[str] = []

    def observe(self, records: list[Record]) -> None:
        for r in records[self._seen:]:
            if r.kind == "observation" and r.obs_id:
                self._obs_url[r.obs_id] = r.url or ""
            elif r.kind == "action" and r.affordance is not None and writes(r):
                self.known_writes.add(control_key(self._obs_url.get(r.source_obs or ""), r.affordance))
        self._seen = len(records)

    def is_known_write(self, source_url: str | None, aff: AffordanceEvidence) -> bool:
        return control_key(source_url, aff) in self.known_writes

    def check(self, step: Step, source_url: str | None, snapshot_verified: bool) -> str | None:
        if step.op == "snapshot" and not self.isolation.snapshot:
            return "snapshot_unavailable"
        if step.op != "click" or step.affordance is None:
            return None
        aff = step.affordance
        if not aff.safe:
            return "unsafe:" + (aff.skip_reason or "flagged")
        if aff.disabled:
            return "disabled"
        if self.is_known_write(source_url, aff):
            if self.isolation.level >= 3 and self.isolation.snapshot and snapshot_verified:
                return None
            return "known_write_not_replayable"
        if aff.kind == "form_submit" and (aff.method or "GET").upper() not in READ_METHODS \
                and not self.isolation.exploratory_writes:
            return "exploratory_write_not_permitted"
        return None
