"""Deterministic, read-only import of archived Agent 1 evidence.

Supported inputs: `run.json`, `checkpoint.json` (its `artifact`), and the
reduced evidence in a Graph A export. Archives are never modified. Missing
fields are reported in the capture manifest and the import report rather than
filled in.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evidence import (AffordanceEvidence, Capture, FieldShape, MessageEvidence, Record, RequestEvidence,
                       Source)

ROLE_SEPARATOR = "+"


def _role(session_context: str | None, markers: dict[str, list[str]] | None) -> str:
    cookies = sorted((markers or {}).get("cookie_names") or [])
    return (session_context or "unknown") + (ROLE_SEPARATOR + ",".join(cookies) if cookies else "")


def _storage(markers: dict[str, list[str]] | None) -> list[str] | None:
    if markers is None:
        return None
    return sorted({f"local:{k}" for k in markers.get("local_storage_keys") or []}
                  | {f"session:{k}" for k in markers.get("session_storage_keys") or []})


def _fields(items: list[dict[str, Any]]) -> list[FieldShape]:
    return [FieldShape(name=f.get("name", ""), input_type=f.get("input_type", ""), required=bool(f.get("required")))
            for f in items or []]


def _affordance(control: dict[str, Any]) -> AffordanceEvidence:
    return AffordanceEvidence(
        kind=control.get("kind", ""), role_attr=control.get("role", "") or "",
        interaction=control.get("interaction", "click") or "click",
        component=control.get("component", "document") or "document",
        locator=control.get("css_path", "") or "", target=control.get("target"), method=control.get("method"),
        fields=_fields(control.get("fields") or []), provenance=control.get("provenance", "snapshot") or "snapshot",
        behavior_revision=control.get("behavior_revision"), frame=int(control.get("frame_index") or 0),
        safe=bool(control.get("safe", True)), skip_reason=control.get("skip_reason"),
        label=control.get("label", "") or "")


def _requests(network: list[dict[str, Any]] | None, filled: list[str]) -> list[RequestEvidence]:
    return [RequestEvidence(channel="http", method=(e.get("method") or "").upper(), url=e.get("url", ""),
                            status=e.get("status"), resource_type=e.get("resource_type"),
                            param_names=sorted(e.get("parameter_names") or []), body_encoding=e.get("body_encoding"),
                            engine_filled=sorted(filled), failure=e.get("failure"))
            for e in network or []]


def _status(transition: dict[str, Any]) -> str:
    raw = str(transition.get("status", ""))
    if raw in {"failed", "not_tested", "blocked"}:
        return raw
    return "observed" if transition.get("result_observation_id") and not transition.get("error") else "failed"


def import_run_artifact(artifact: dict[str, Any], artifact_name: str, application: str) -> list[Record]:
    """Import a RunArtifact (run.json or checkpoint['artifact'])."""
    replay_network = any("network" in r for r in artifact.get("replays") or [])
    capture = Capture(replay_requests=replay_network)
    items: list[tuple[str, int, str, Record]] = []

    def observation(obs: dict[str, Any], index: int, context: str, collection: str) -> None:
        markers = obs.get("session_markers")
        record = Record(
            id=f"ev:{collection}:{obs['id']}", seq=0, kind="observation",
            source=Source(artifact=artifact_name, pointer=f"/{collection}/{index}"),
            obs_id=obs["id"], context=context, url=obs.get("url"), role=_role(obs.get("session_context"), markers),
            storage_keys=_storage(markers), affordances=[_affordance(c) for c in obs.get("controls") or []],
            title=obs.get("title", "") or "")
        items.append((obs.get("recorded_at", ""), int(obs.get("sequence", 0)), record.id, record))

    for i, obs in enumerate(artifact.get("observations") or []):
        observation(obs, i, "exploration", "observations")
    for i, obs in enumerate(artifact.get("replay_observations") or []):
        observation(obs, i, "replay", "replay_observations")
    for i, t in enumerate(artifact.get("transitions") or []):
        filled = [ref.get("field_name", "") for ref in t.get("input_references") or []]
        record = Record(
            id=f"ev:transitions:{t['id']}", seq=0, kind="action",
            source=Source(artifact=artifact_name, pointer=f"/transitions/{i}"),
            action_id=t["id"], source_obs=t.get("source_observation_id"), result_obs=t.get("result_observation_id"),
            affordance=_affordance(t.get("action") or {}), status=_status(t),
            requests=_requests(t.get("network"), filled), error=t.get("error"),
            workflow_length=max(1, len(t.get("workflow_path") or [])))
        items.append((t.get("ended_at") or t.get("started_at") or "", 10**9, record.id, record))
    for i, r in enumerate(artifact.get("replays") or []):
        record = Record(
            id=f"ev:replays:{r['id']}", seq=0, kind="replay",
            source=Source(artifact=artifact_name, pointer=f"/replays/{i}"),
            replay_id=r["id"], action_id=r.get("transition_id"), result_obs=r.get("actual_observation_id"),
            status=str(r.get("status", "")), verification_kind=r.get("verification_kind") or "standard",
            requests=_requests(r["network"], []) if "network" in r else None,
            verification={k: v for k, v in {
                "functional_status": r.get("functional_status"), "failure_reason": r.get("failure_reason"),
                "primary_only_targets": len((r.get("verification_evidence") or {}).get("primary_only_targets") or []),
                "contrast_only_targets": len((r.get("verification_evidence") or {}).get("contrast_only_targets") or []),
                "verification_observation_ids": r.get("verification_observation_ids") or [],
            }.items() if v is not None})
        items.append((r.get("ended_at") or r.get("started_at") or "", 2 * 10**9, record.id, record))
    items.sort(key=lambda item: (item[0], item[1], item[2]))
    manifest = Record(id="ev:manifest", seq=0, kind="capture_manifest",
                      source=Source(artifact=artifact_name, pointer="/"), capture=capture, application=application)
    records = [manifest] + [item[3] for item in items]
    return [record.model_copy(update={"seq": index}) for index, record in enumerate(records)]


def import_graph_a(graph: dict[str, Any], artifact_name: str, application: str) -> list[Record]:
    """Import the reduced evidence of a Graph A export.

    Graph A carries per-transition network and workflow descriptors, but not
    per-observation controls, so `dom_affordances` is not captured. Observation
    URLs come from record-instance nodes when available, otherwise from the
    state's representative URL (flagged `group_representative`)."""
    nodes = graph.get("nodes") or {}
    url_of: dict[str, tuple[str, str]] = {}
    role_of: dict[str, str] = {}
    for state in nodes.get("states") or []:
        for oid in state.get("observation_ids") or []:
            url_of.setdefault(oid, (state.get("url", ""), "group_representative"))
            role_of[oid] = _role(state.get("session_context"), state.get("session_markers"))
    for inst in nodes.get("record_instances") or []:
        for oid in inst.get("observation_ids") or []:
            url_of[oid] = (inst.get("url", ""), "exact")
    source_state: dict[str, str] = {}
    for edge in graph.get("edges") or []:
        if edge.get("type") == "offers_or_executes":
            source_state[edge["target"]] = edge["source"]
    state_obs = {f"state_{s['group_signature']}": (s.get("observation_ids") or [None])[0] for s in nodes.get("states") or []}
    records: list[Record] = [Record(id="ev:manifest", seq=0, kind="capture_manifest",
                                    source=Source(artifact=artifact_name, pointer="/"),
                                    capture=Capture(dom_affordances=False, storage_key_names=False,
                                                    replay_requests=True),
                                    application=application)]
    for oid in sorted(url_of):
        url, confidence = url_of[oid]
        records.append(Record(id=f"ev:observations:{oid}", seq=0, kind="observation",
                              source=Source(artifact=artifact_name, pointer=f"/nodes/states#{oid}"),
                              obs_id=oid, url=url, url_confidence=confidence, role=role_of.get(oid, "unknown")))
    for i, action in enumerate(nodes.get("actions_evidence") or []):
        path = action.get("workflow_path") or [{}]
        filled = [ref.get("field_name", "") for ref in action.get("input_references") or []]
        records.append(Record(
            id=f"ev:actions_evidence:{action['id']}", seq=0, kind="action",
            source=Source(artifact=artifact_name, pointer=f"/nodes/actions_evidence/{i}"),
            action_id=action["id"].removeprefix("action_"), source_obs=state_obs.get(source_state.get(action["id"], "")),
            result_obs=action.get("result_observation_id"), affordance=_affordance(path[-1]),
            status=_status({"status": action.get("status"), "result_observation_id": action.get("result_observation_id"),
                            "error": action.get("error")}),
            requests=_requests(action.get("network"), filled), error=action.get("error"),
            workflow_length=max(1, len(path))))
    for i, obs in enumerate(graph.get("replay_observations") or []):
        markers = obs.get("session_markers")
        records.append(Record(id=f"ev:replay_observations:{obs['id']}", seq=0, kind="observation",
                              source=Source(artifact=artifact_name, pointer=f"/replay_observations/{i}"),
                              obs_id=obs["id"], context="replay", url=obs.get("url"),
                              role=_role(obs.get("session_context"), markers), storage_keys=_storage(markers),
                              affordances=[_affordance(c) for c in obs.get("controls") or []],
                              title=obs.get("title", "") or ""))
    for i, r in enumerate(graph.get("replays") or []):
        records.append(Record(id=f"ev:replays:{r['id']}", seq=0, kind="replay",
                              source=Source(artifact=artifact_name, pointer=f"/replays/{i}"),
                              replay_id=r["id"], action_id=r.get("transition_id"),
                              result_obs=r.get("actual_observation_id"), status=str(r.get("status", "")),
                              verification_kind=r.get("verification_kind") or "standard",
                              requests=_requests(r.get("network"), []),
                              verification={"failure_reason": r.get("failure_reason")}))
    # Graph A carries no timestamps for observations; keep the export order.
    return [record.model_copy(update={"seq": index}) for index, record in enumerate(records)]


def import_path(path: Path, application: str, repository_root: Path | None = None) -> list[Record]:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = str(path.relative_to(repository_root)) if repository_root and path.is_relative_to(repository_root) else path.name
    if "nodes" in data and "edges" in data:
        return import_graph_a(data, name, application)
    return import_run_artifact(data.get("artifact", data), name, application)


__all__ = ["import_graph_a", "import_path", "import_run_artifact", "MessageEvidence"]
