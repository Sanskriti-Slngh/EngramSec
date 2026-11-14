"""Live ACG projection over evidence received from the real browser executor.

Uses the same per-item conversion as the offline importer
(`agent1.model.importer`), then adds the opt-in capture (disabled controls,
structure-only request evidence, WebSocket message classes). Identifier and
query values are replaced by format-preserving per-run pseudonyms before they
reach the model, so neither the live graph nor its persisted evidence log
holds a raw identifier.

`sync(artifact)` ingests whatever the explorer appended since the last call
(append-only); `export()` resolves the graph. By construction the export after
any sync equals a full rebuild from the persisted log of the same records
(`materialize(read_log(path))`); tests check it.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from agent1.model.evidence import (Capture, MessageEvidence, Record, RequestEvidence,
                                   write_log)
from agent1.model.importer import _affordance, action_item, assemble, observation_item, replay_item
from agent1.model.materialize import materialize
from agent1.model.schema import ACGExport


def _ts(value: str | None) -> float:
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


class LiveACG:
    def __init__(self, application: str, sink: Any = None, artifact_name: str = "live") -> None:
        self.application, self.sink, self.artifact_name = application, sink, artifact_name
        self.items: list[tuple[tuple, Record]] = []
        self.seen = {"observations": 0, "replay_observations": 0, "transitions": 0, "replays": 0}
        self.latencies_ms: list[float] = []
        self._cache: tuple[int, ACGExport] | None = None

    # ------------------------------------------------------------- conversion
    def _pseudo(self, url: str | None) -> str | None:
        return self.sink.pseudo_url(url) if self.sink is not None else url

    def _observation(self, obs: Any, index: int, context: str, collection: str):
        key, rec = observation_item(obs.model_dump(mode="json"), index, context, collection, self.artifact_name)
        if self.sink is None:
            return key, rec
        affs = [a.model_copy(update={"disabled": False, "target": self._pseudo(a.target)}) for a in rec.affordances or []]
        for c in self.sink.disabled.get(obs.id, []):
            a = _affordance(c.model_dump(mode="json"))
            affs.append(a.model_copy(update={"disabled": True, "target": self._pseudo(a.target)}))
        return key, rec.model_copy(update={"url": self._pseudo(rec.url), "affordances": affs})

    def _requests(self, events: list[Any], base: list[RequestEvidence] | None) -> list[RequestEvidence] | None:
        if base is None or self.sink is None:
            return base
        out = []
        for event, req in zip(events, base):
            extra = self.sink.http.get(id(event), {})
            out.append(req.model_copy(update={
                "url": self._pseudo(req.url), "request_shape": extra.get("request_shape"),
                "response_shape": extra.get("response_shape"), "content_class": extra.get("content_class"),
                "id_tokens": extra.get("id_tokens")}))
        return out

    def _frames(self, started: str | None, ended: str | None):
        if self.sink is None:
            return [], []
        lo, hi = _ts(started), _ts(ended)
        sent, received = [], []
        for f in self.sink.ws_frames:
            if lo <= _ts(f["at"]) <= hi:
                if f["direction"] == "sent":
                    sent.append(RequestEvidence(channel="websocket_send", url=f["url_path"],
                                                message_skeleton=f["skeleton"],
                                                message_discriminator=f.get("discriminator")))
                else:
                    received.append(MessageEvidence(url=f["url_path"], message_skeleton=f["skeleton"],
                                                    message_discriminator=f.get("discriminator")))
        return sent, received

    # ----------------------------------------------------------------- ingest
    def sync(self, artifact: Any) -> int:
        added = 0
        for collection, context in (("observations", "exploration"), ("replay_observations", "replay")):
            items = getattr(artifact, collection)
            for i in range(self.seen[collection], len(items)):
                self.items.append(self._observation(items[i], i, context, collection))
                added += 1
            self.seen[collection] = len(items)
        for i in range(self.seen["transitions"], len(artifact.transitions)):
            t = artifact.transitions[i]
            key, rec = action_item(t.model_dump(mode="json"), i, self.artifact_name)
            sent, received = self._frames(t.started_at, t.ended_at)
            reqs = self._requests(t.network, rec.requests)
            rec = rec.model_copy(update={"requests": (reqs or []) + sent, "received": received or None,
                                         "affordance": rec.affordance.model_copy(update={
                                             "target": self._pseudo(rec.affordance.target)}) if self.sink else rec.affordance})
            self.items.append((key, rec))
            added += 1
        self.seen["transitions"] = len(artifact.transitions)
        for i in range(self.seen["replays"], len(artifact.replays)):
            r = artifact.replays[i]
            key, rec = replay_item(r.model_dump(mode="json"), i, self.artifact_name)
            rec = rec.model_copy(update={"requests": self._requests(r.network, rec.requests)})
            self.items.append((key, rec))
            added += 1
        self.seen["replays"] = len(artifact.replays)
        return added

    def capture(self) -> Capture:
        on = self.sink is not None
        return Capture(replay_requests=True, websocket=on, response_shapes=on)

    def records(self) -> list[Record]:
        return assemble(self.items, self.capture(), self.artifact_name, self.application)

    def export(self) -> ACGExport:
        if self._cache and self._cache[0] == len(self.items):
            return self._cache[1]
        start = time.perf_counter()
        acg = materialize(self.records())
        self.latencies_ms.append((time.perf_counter() - start) * 1000)
        self._cache = (len(self.items), acg)
        return acg

    def write(self, path: Path) -> None:
        write_log(self.records(), path)
