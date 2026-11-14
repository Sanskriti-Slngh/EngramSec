"""Normalized, append-only evidence log: the only input of the ACG.

Contract `acg-evidence/1`. One JSON object per line. Records are immutable once
written; corrections are new records. Every record names where it came from
(`source`), so every ACG claim can cite it. Display text (labels, titles) is
kept verbatim as annotation material and must never be used for identity.

Fields that a historical Agent 1 run did not capture are *absent*, and the
`capture` manifest says so. Synthetic test logs set `synthetic: true`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

SCHEMA = "acg-evidence/1"


class Source(BaseModel):
    artifact: str            # repository-relative path or corpus file name
    pointer: str             # JSON pointer-like location inside the artifact


class Capture(BaseModel):
    """What the producing run actually recorded. False means 'not captured',
    never 'observed to be absent'."""
    dom_affordances: bool = True
    http_requests: bool = True
    http_query_values: bool = True
    storage_key_names: bool = True
    websocket: bool = False
    response_shapes: bool = False
    visual_regions: bool = False
    instance_fields: bool = False
    replay_requests: bool = False


class FieldShape(BaseModel):
    name: str
    input_type: str
    required: bool = False


class AffordanceEvidence(BaseModel):
    kind: str                                  # link | button | form_submit | gesture ...
    role_attr: str = ""
    interaction: str = "click"
    component: str = "document"
    locator: str = ""                          # structural path (css), not text
    target: str | None = None                  # link/form target URL, if any
    method: str | None = None
    fields: list[FieldShape] = Field(default_factory=list)
    provenance: str = "snapshot"
    behavior_revision: str | None = None
    frame: int = 0
    safe: bool = True
    skip_reason: str | None = None
    disabled: bool | None = None               # None = not captured; True = observed disabled/aria-disabled
    label: str = ""                            # display text: annotation only


class RequestEvidence(BaseModel):
    channel: Literal["http", "websocket_send"] = "http"
    method: str | None = None
    url: str = ""
    status: int | None = None
    resource_type: str | None = None
    param_names: list[str] = Field(default_factory=list)
    body_encoding: str | None = None
    engine_filled: list[str] = Field(default_factory=list)   # names of fields the agent filled
    failure: str | None = None
    message_skeleton: str | None = None        # websocket: key-path skeleton digest
    message_discriminator: str | None = None   # websocket: pseudonymous token
    # Phase 2 live capture (None = not captured): structure-only digests and per-run keyed tokens.
    request_shape: str | None = None
    response_shape: str | None = None
    content_class: str | None = None
    id_tokens: list[str] | None = None


class MessageEvidence(BaseModel):
    url: str
    message_skeleton: str
    message_discriminator: str | None = None


class Record(BaseModel):
    id: str
    seq: int
    kind: Literal["capture_manifest", "observation", "action", "replay"]
    source: Source
    # capture_manifest
    capture: Capture | None = None
    synthetic: bool = False
    application: str | None = None
    # observation
    obs_id: str | None = None
    context: Literal["exploration", "replay"] = "exploration"
    url: str | None = None
    url_confidence: Literal["exact", "group_representative"] = "exact"
    role: str | None = None
    storage_keys: list[str] | None = None      # None = not captured
    affordances: list[AffordanceEvidence] | None = None   # None = not captured
    regions: dict[str, str] | None = None      # visual region digests (synthetic only so far)
    instance_fields: dict[str, str] | None = None
    title: str = ""                            # display text: annotation only
    # action
    action_id: str | None = None
    source_obs: str | None = None
    result_obs: str | None = None
    affordance: AffordanceEvidence | None = None
    status: str | None = None                  # observed | failed | not_tested | blocked
    requests: list[RequestEvidence] | None = None
    received: list[MessageEvidence] | None = None
    error: str | None = None
    workflow_length: int = 1
    # replay
    replay_id: str | None = None
    independent_context: bool = True
    verification_kind: str | None = None       # standard | paired_search | cross_view | differential
    verification: dict[str, Any] = Field(default_factory=dict)


def record_digest(record: Record) -> str:
    payload = json.dumps(record.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def log_digest(records: list[Record]) -> str:
    h = hashlib.sha256()
    for record in records:
        h.update(record_digest(record).encode())
    return h.hexdigest()[:16]


def write_log(records: list[Record], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.model_dump(mode="json", exclude_none=True),
                                    sort_keys=True, ensure_ascii=False) + "\n")


def read_log(path: Path) -> list[Record]:
    records = [Record.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.lstrip().startswith("//")]
    return sorted(records, key=lambda r: (r.seq, r.id))
