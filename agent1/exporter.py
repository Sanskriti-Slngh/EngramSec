from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from .schema import EvidenceStatus, RunArtifact
from .state import digest


def _slug(value: str) -> str:
    return "n_" + re.sub(r"[^A-Za-z0-9_]", "_", value)[:80]


SURFACE_OUTCOMES = ("successful_resource", "sent_non_2xx", "sent_no_response", "observed_not_sent")


def build_request_surfaces(artifact: RunArtifact) -> list[dict[str, Any]]:
    """Request surfaces keyed by method, path and parameter names (no values).

    Outcomes are deliberately distinct: a request the browser sent that was
    answered 405 is a *sent* surface, not a fetched resource and not a workflow.
    A workflow is verified only by an independent replay of a UI transition.
    """
    surfaces: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}

    def entry(method: str, url: str, names: list[str] | tuple[str, ...]) -> dict[str, Any]:
        parts = urlsplit(url)
        path_url = f"{parts.scheme}://{parts.netloc}{parts.path or '/'}"
        key = (method.upper(), path_url, tuple(sorted(set(names))))
        return surfaces.setdefault(key, {
            "method": key[0], "url": path_url, "parameter_names": list(key[2]),
            "sent_by": set(), "statuses": set(), "observed_as": set(), "in_replay_validated_workflow": False,
        })

    def sent(event: Any, channel: str) -> None:
        names = event.parameter_names or [k for k, _ in parse_qsl(urlsplit(event.url).query, keep_blank_values=True)]
        item = entry(event.method, event.url, names)
        item["sent_by"].add(channel)
        item["statuses"].add(event.status)

    for nav in artifact.navigation_evidence:
        for event in nav.network:
            sent(event, f"browser_{nav.reason}")
    for transition in artifact.transitions:
        for event in transition.network:
            sent(event, "browser_action")
        for step in transition.prerequisite_network:
            for event in step.network:
                sent(event, "browser_restoration")
    validated = {item.transition_id for item in artifact.replays if item.status == EvidenceStatus.REPLAY_VALIDATED}
    for replay in artifact.replays:
        for event in replay.network:
            sent(event, "replay")
            if replay.transition_id in validated:
                entry(event.method, event.url, event.parameter_names)["in_replay_validated_workflow"] = True
    for item in artifact.resource_evidence:
        if not item.url:
            continue
        names = [k for k, _ in parse_qsl(urlsplit(item.url).query, keep_blank_values=True)]
        if item.status in {"fetched", "failed"}:
            record = entry("GET", item.url, names)
            record["sent_by"].add(f"spider_{item.channel or 'typed_resource'}")
            record["statuses"].add(item.http_status)
        else:
            method = item.method or ("GET" if item.kind in {"navigation", "asset"} else "UNKNOWN")
            entry(method, item.url, names)["observed_as"].add(f"{item.kind}:{item.queue_decision}")
    result = []
    for item in surfaces.values():
        statuses = {status for status in item["statuses"] if status is not None}
        if any(200 <= status < 300 for status in statuses):
            outcome = "successful_resource"
        elif statuses:
            outcome = "sent_non_2xx"
        elif item["sent_by"]:
            outcome = "sent_no_response"
        else:
            outcome = "observed_not_sent"
        result.append(item | {
            "outcome": outcome,
            "sent_by": sorted(item["sent_by"]),
            "statuses": sorted(statuses),
            "observed_as": sorted(item["observed_as"]),
        })
    return sorted(result, key=lambda x: (x["url"], x["method"], x["parameter_names"]))


def build_behavior_evidence(artifact: RunArtifact) -> dict[str, Any]:
    """Listener-observed candidates, handler revisions and the requests and
    states that executing them produced, with replay status. Visible DOM
    (group signature), handler behavior (behavior signature) and session
    context are kept as separate fields; none is inferred from another."""
    from .explorer import action_request_structures

    replays: dict[str, list[Any]] = {}
    for replay in artifact.replays:
        replays.setdefault(replay.transition_id, []).append(replay)
    observations = {item.id: item for item in artifact.observations}
    executed_by_control: dict[str, list[str]] = {}
    for transition in artifact.transitions:
        if transition.status != EvidenceStatus.FAILED:
            executed_by_control.setdefault(transition.action.control_id, []).append(transition.id)
    listener_observations, candidates, revisions = [], [], []
    for observation in artifact.observations:
        evidence = observation.listener_evidence
        if evidence is None:
            continue
        listener_observations.append({
            "observation_id": observation.id, "group_signature": observation.group_signature,
            "behavior_signature": observation.behavior_signature or observation.group_signature,
            "session_context": observation.session_context, "caused_by_action": evidence.caused_by_action,
            "listener_nodes": evidence.listener_nodes, "described_nodes": evidence.described_nodes,
            "reused_nodes": evidence.reused_nodes, "changes": evidence.changes, "truncated": evidence.truncated,
            "candidates": len(evidence.candidates), "revisions": len(evidence.revisions),
            "active_revisions": len(evidence.active_revisions), "skipped": evidence.skipped,
            "delegation_hosts": evidence.delegation_hosts, "elapsed_ms": evidence.elapsed_ms,
            "cdp_calls": evidence.cdp_calls, "error": evidence.error, "supported": evidence.supported,
        })
        for item in evidence.candidates:
            candidates.append({"observation_id": observation.id, **{k: item.get(k) for k in (
                "label", "tag", "css_path", "provenance", "interactions", "handler_locations", "listener_count",
                "family", "behavior_revision", "control_ids", "safe", "skip_reason")},
                "caused_by_action": evidence.caused_by_action,
                "executed_transition_ids": sorted({t for c in item.get("control_ids") or [] for t in executed_by_control.get(c, [])})})
        for item in evidence.revisions:
            revisions.append({"observation_id": observation.id, **{k: item.get(k) for k in (
                "label", "css_path", "revision", "caused_by_action", "before", "after", "snapshot_control")}})
    executions = []
    for transition in artifact.transitions:
        action = transition.action
        if action.provenance != "observed_listener" and not action.behavior_revision:
            continue
        result = observations.get(transition.result_observation_id or "")
        attempts = replays.get(transition.id, [])
        executions.append({
            "transition_id": transition.id, "status": str(transition.status),
            "label": action.label, "provenance": action.provenance, "behavior_revision": action.behavior_revision,
            "source_group_signature": transition.source_group_signature,
            "result_group_signature": transition.result_group_signature,
            "result_behavior_signature": (result.behavior_signature or result.group_signature) if result else None,
            "visible_dom_changed": transition.source_group_signature != transition.result_group_signature,
            "request_structures": sorted(f"{m} {r} {list(p)}" for m, r, p in action_request_structures(transition.network)),
            "replays_attempted": len(attempts),
            "replay_validated": any(str(r.status) == "replay_validated" for r in attempts),
        })
    return {
        "listener_observations": listener_observations,
        "listener_candidates": candidates,
        "handler_revisions": revisions,
        "behavior_executions": executions,
        "summary": {
            "listener_observations": len(listener_observations),
            "candidates_recorded": len(candidates),
            "candidates_by_change": {k: sum(1 for c in candidates if c["provenance"] == k)
                                     for k in sorted({c["provenance"] or "unknown" for c in candidates})},
            "candidate_records_executed": sum(1 for c in candidates if c["executed_transition_ids"]),
            "handler_revisions_recorded": len(revisions),
            "executed_listener_or_revision_actions": len(executions),
            "replay_validated_listener_or_revision_actions": sum(e["replay_validated"] for e in executions),
        },
    }


def build_graph_a(artifact: RunArtifact) -> dict[str, Any]:
    observations = {item.id: item for item in artifact.observations}
    state_nodes = []
    for group, member_ids in sorted(artifact.state_groups.items()):
        members = [observations[item] for item in member_ids if item in observations]
        representative = members[0] if members else None
        state_nodes.append(
            {
                "id": f"state_{group}",
                "type": "state",
                "group_signature": group,
                "route_pattern": representative.route_pattern if representative else "",
                "url": representative.url if representative else "",
                "title": representative.title if representative else "",
                "session_context": representative.session_context if representative else "",
                "session_markers": representative.session_markers if representative else {},
                "observation_ids": member_ids,
                "raw_state_signatures": sorted({item.state_signature for item in members}),
                "return_path_length": len(artifact.return_paths.get(group, [])),
                "readiness_statuses": sorted({item.readiness.status for item in members}),
            }
        )
    resource_responses: dict[str, dict[str, Any]] = {}
    resource_references: dict[str, dict[str, Any]] = {}
    resource_evidence_nodes: dict[str, dict[str, Any]] = {}
    resource_edges: list[dict[str, Any]] = []
    for index, item in enumerate(artifact.resource_evidence):
        evidence = item.model_dump(mode="json")
        evidence_id = evidence.get("evidence_id") or "resource_evidence_" + digest(evidence, 20)
        evidence["evidence_id"] = evidence_id
        response_url = str(item.source_url)
        external_candidate = item.source_type == "zap_seed" and item.status not in {"fetched", "failed"}
        response_key = response_url + ("\0external_seed" if external_candidate else "")
        response_id = "response_" + hashlib.sha256(response_key.encode()).hexdigest()[:20]
        reference_key = (
            f"unresolved\0{evidence_id}"
            if item.url is None
            else f"{item.kind}\0{item.url}"
        )
        reference_id = "resource_" + hashlib.sha256(reference_key.encode()).hexdigest()[:20]
        resource_responses.setdefault(
            response_id,
            {
                "id": response_id,
                "type": "external_seed_source" if external_candidate else "resource_source_response",
                "url": response_url,
            },
        )
        reference = resource_references.setdefault(
            reference_id,
            {
                "id": reference_id,
                "type": "resource_reference",
                "url": item.url,
                "kind": item.kind,
                "statuses": [],
                "evidence_ids": [],
            },
        )
        if item.status not in reference["statuses"]:
            reference["statuses"].append(item.status)
        reference["evidence_ids"].append(evidence_id)
        resource_evidence_nodes.setdefault(
            evidence_id,
            {"id": evidence_id, "type": "resource_evidence", **evidence},
        )
        resource_edges.append(
            {
                "source": response_id,
                "target": reference_id,
                "type": ("external_seed_candidate" if external_candidate else "agent_seed_fetch") if item.source_type == "zap_seed" else "references",
                "status": item.status,
                "evidence_id": evidence_id,
            }
        )
    external_runs: dict[str, dict[str, Any]] = {}
    external_nodes: list[dict[str, Any]] = []
    external_edges: list[dict[str, Any]] = []
    for item in artifact.external_discoveries:
        run_id = "external_run_" + digest([item.engine, item.run_id, item.source_origin, item.export_digest], 20)
        external_runs.setdefault(run_id, {
            "id": run_id, "type": "external_discovery_run", "engine": item.engine,
            "run_id": item.run_id, "source_origin": item.source_origin,
            "export_digest": item.export_digest, "session_context": "unknown",
        })
        external_nodes.append({"type": "external_discovery_evidence", **item.model_dump(mode="json")})
        external_edges.append({
            "source": run_id, "target": item.id, "type": "external_report",
            "status": item.status, "evidence_id": item.id,
        })
        for reference in resource_references.values():
            if reference.get("url") == item.mapped_url:
                external_edges.append({
                    "source": item.id, "target": reference["id"],
                    "type": "external_candidate_for_resource", "status": item.status,
                    "evidence_id": item.id,
                })
    action_nodes = []
    evidence_edges = []
    for transition in artifact.transitions:
        action_id = f"action_{transition.id}"
        action_nodes.append(
            {
                "id": action_id,
                "type": "action_evidence",
                "control_id": transition.action.control_id,
                "kind": transition.action.kind,
                "label": transition.action.label,
                "interaction": transition.action.interaction,
                "component": transition.action.component,
                "frame_index": transition.action.frame_index,
                "frame_url": transition.action.frame_url,
                "status": transition.status,
                "workflow_path_length": len(transition.workflow_path),
                "workflow_path": [
                    descriptor.model_dump(mode="json")
                    for descriptor in transition.workflow_path
                ],
                "restoration_attempted": transition.restoration_attempted,
                "prerequisite_network": [
                    item.model_dump(mode="json")
                    for item in transition.prerequisite_network
                ],
                "input_references": [item.model_dump(mode="json") for item in transition.input_references],
                "network": [item.model_dump(mode="json") for item in transition.network],
                "error": transition.error,
                "run_id": transition.run_id,
                "result_observation_id": transition.result_observation_id,
                "outcome_signals": (
                    [item.model_dump(mode="json") for item in observations[transition.result_observation_id].outcome_signals]
                    if transition.result_observation_id in observations
                    else []
                ),
            }
        )
        evidence_edges.append(
            {
                "source": f"state_{transition.source_group_signature}",
                "target": action_id,
                "type": "offers_or_executes",
                "status": transition.status,
                "evidence_transition_id": transition.id,
            }
        )
        if transition.result_group_signature:
            evidence_edges.append(
                {
                    "source": action_id,
                    "target": f"state_{transition.result_group_signature}",
                    "type": "results_in",
                    "status": transition.status,
                    "evidence_transition_id": transition.id,
                }
            )
    feature_nodes = []
    feature_edges = []
    for feature in artifact.features:
        feature_nodes.append(
            {
                "id": feature.id,
                "type": "feature",
                "description": feature.description,
                "status": feature.status,
                "evidence_transition_ids": feature.evidence_transition_ids,
                "replay_ids": feature.replay_ids,
                "validated_transition_ids": feature.validated_transition_ids,
                "failed_transition_ids": feature.failed_transition_ids,
                "untested_transition_ids": feature.untested_transition_ids,
            }
        )
        for source_group in feature.source_group_signatures or [feature.source_group_signature]:
            feature_edges.append(
                {
                    "source": feature.id,
                    "target": f"state_{source_group}",
                    "type": "starts_at",
                    "status": feature.status,
                }
            )
        for target_group in feature.target_group_signatures or [feature.target_group_signature]:
            feature_edges.append(
                {
                    "source": feature.id,
                    "target": f"state_{target_group}",
                    "type": "ends_at",
                    "status": feature.status,
                }
            )
    advertised = []
    advertised_nodes = []
    attempted = {
        (transition.source_observation_id, transition.action.control_id)
        for transition in artifact.transitions
    }
    for item in artifact.advertisements:
        if (item.source_observation_id, item.control.id) in attempted:
            continue
        advertised_id = f"advertised_{item.source_observation_id}_{item.control.id}"
        advertised.append(
            {
                "id": advertised_id,
                "source_observation_id": item.source_observation_id,
                "source_group_signature": item.source_group_signature,
                "control": item.control.model_dump(mode="json"),
                "status": EvidenceStatus.ADVERTISED,
                "test_status": EvidenceStatus.NOT_TESTED,
            }
        )
        advertised_nodes.append(
            {
                "id": advertised_id,
                "type": "advertised_action",
                "label": item.control.label,
                "kind": item.control.kind,
                "status": EvidenceStatus.ADVERTISED,
                "test_status": EvidenceStatus.NOT_TESTED,
            }
        )
        evidence_edges.append(
            {
                "source": f"state_{item.source_group_signature}",
                "target": advertised_id,
                "type": "offers_untested",
                "status": EvidenceStatus.NOT_TESTED,
                "source_observation_id": item.source_observation_id,
            }
        )
    workflow_nodes = []
    workflow_edges = []
    for workflow in artifact.functional_workflows:
        workflow_nodes.append(workflow.model_dump(mode="json") | {"type": "functional_workflow"})
        workflow_edges.append(
            {
                "source": workflow.id,
                "target": f"action_{workflow.transition_id}",
                "type": "validated_from_path_instance",
                "status": workflow.status,
                "evidence_transition_id": workflow.transition_id,
                "replay_id": workflow.replay_id,
            }
        )
    request_surfaces = build_request_surfaces(artifact)
    behavior = build_behavior_evidence(artifact)
    return {
        "schema_version": "graph-a-1.1",
        "run": {
            "run_id": artifact.run_id,
            "code_revision": artifact.code_revision,
            "started_at": artifact.started_at,
            "ended_at": artifact.ended_at,
            "config": artifact.config,
        },
        "metrics": artifact.metrics.model_dump(mode="json"),
        "nodes": {
            "features": feature_nodes,
            "states": state_nodes,
            "actions_evidence": action_nodes,
            "functional_workflows": workflow_nodes,
            "advertised_actions": advertised_nodes,
            "resource_source_responses": list(resource_responses.values()),
            "resource_references": list(resource_references.values()),
            "resource_evidence": list(resource_evidence_nodes.values()),
            "external_discovery_runs": list(external_runs.values()),
            "external_discoveries": external_nodes,
        },
        "edges": evidence_edges + feature_edges + workflow_edges + resource_edges + external_edges,
        "advertised_unexecuted": advertised,
        "replays": [item.model_dump(mode="json") for item in artifact.replays],
        "replay_observations": [
            item.model_dump(mode="json") for item in artifact.replay_observations
        ],
        "navigation_evidence": [
            item.model_dump(mode="json") for item in artifact.navigation_evidence
        ],
        "resource_evidence": [
            item.model_dump(mode="json") for item in artifact.resource_evidence
        ],
        "external_discoveries": [item.model_dump(mode="json") for item in artifact.external_discoveries],
        "connection_evidence": [
            item.model_dump(mode="json") for item in artifact.connection_evidence
        ],
        "request_surfaces": request_surfaces,
        "behavior_evidence": behavior,
        "request_surface_summary": {
            outcome: sum(item["outcome"] == outcome for item in request_surfaces) for outcome in SURFACE_OUTCOMES
        } | {"total": len(request_surfaces)},
        "notes": artifact.notes,
    }


def mermaid(graph: dict[str, Any]) -> str:
    lines = ["flowchart LR"]
    for run in graph["nodes"].get("external_discovery_runs", []):
        lines.append(f'  {_slug(run["id"])}(("ZAP external run"))')
    for item in graph["nodes"].get("external_discoveries", [])[:100]:
        label = f'{urlsplit(item["mapped_url"]).path} [{item["status"]}]'.replace('"', "'")[:100]
        lines.append(f'  {_slug(item["id"])}["{label}"]')
        run_id = "external_run_" + digest([item["engine"], item["run_id"], item["source_origin"], item["export_digest"]], 20)
        lines.append(f'  {_slug(run_id)} -->|external report| {_slug(item["id"])}')
    states = graph["nodes"]["states"]
    for state in states:
        label = (state["title"] or state["route_pattern"] or "state").replace('"', "'")[:60]
        lines.append(f'  {_slug(state["id"])}["{label}"]')
    for action in graph["nodes"]["actions_evidence"]:
        label = (action["label"] or action["kind"]).replace('"', "'")[:60]
        status = str(action["status"])
        lines.append(f'  {_slug(action["id"])}{{"{label} [{status}]"}}')
    for workflow in graph["nodes"].get("functional_workflows", []):
        label = f"{workflow['action_label']} [{workflow['status']}]".replace('"', "'")[:80]
        lines.append(f'  {_slug(workflow["id"])}(("{label}"))')
    resource_nodes: dict[tuple[str, str], tuple[str, set[str]]] = {}
    resource_responses: dict[str, str] = {}
    resource_labels: dict[str, str] = {}
    resource_links: set[tuple[str, str, str]] = set()
    for evidence in graph.get("resource_evidence", []):
        resource_url = str(evidence.get("url", ""))
        source_url = str(evidence.get("source_url", ""))
        kind = str(evidence.get("kind", "resource"))
        if not resource_url or not source_url:
            continue
        key = (resource_url, kind)
        status = str(evidence.get("status", "discovered"))
        target_id = resource_nodes.setdefault(
            key,
            (
                "resource_" + hashlib.sha256(f"{kind}\0{resource_url}".encode()).hexdigest()[:20],
                set(),
            ),
        )[0]
        resource_nodes[key][1].add(status)
        external_candidate = evidence.get("source_type") == "zap_seed" and status not in {"fetched", "failed"}
        response_key = source_url + ("\0external_seed" if external_candidate else "")
        response_id = resource_responses.setdefault(
            response_key,
            "response_" + hashlib.sha256(response_key.encode()).hexdigest()[:20],
        )
        response_parts = urlsplit(source_url)
        response_label = f"{'External seed' if external_candidate else 'Response'} {response_parts.netloc}{response_parts.path or '/'}"[:90]
        resource_url_parts = urlsplit(resource_url)
        query_names = sorted({name for name, _ in parse_qsl(resource_url_parts.query, keep_blank_values=True)})
        query_suffix = f" ?{','.join(query_names)}" if query_names else ""
        resource_label = f"{kind}: {resource_url_parts.netloc}{resource_url_parts.path}{query_suffix}"[:100]
        relation = str(evidence.get("source", evidence.get("relation", "reference")))[:30]
        resource_links.add((response_id, target_id, f"{relation} [{status}]"))
        resource_labels[response_id] = response_label
        resource_labels[target_id] = resource_label
    if resource_nodes:
        for response_id in sorted(set(resource_responses.values())):
            response_label = resource_labels.get(response_id, "HTTP response")
            lines.append(f'  {_slug(response_id)}(("{response_label}"))')
        for (resource_url, kind), (resource_id, statuses) in sorted(resource_nodes.items()):
            lines.append(f'  {_slug(resource_id)}["{resource_labels.get(resource_id, kind)} [{", ".join(sorted(statuses))}]"]')
        for source_id, target_id, relation in sorted(resource_links):
            lines.append(f"  {_slug(source_id)} -->|{relation}| {_slug(target_id)}")
    executed_labels = {
        (item.get("label") or item.get("kind") or "").strip()
        for item in graph["nodes"].get("actions_evidence", [])
    }
    shown_advertised = []
    shown_labels: set[str] = set()
    for item in graph["nodes"].get("advertised_actions", []):
        label = (item.get("label") or item.get("kind") or "").strip()
        if label in executed_labels or label in shown_labels:
            continue
        shown_advertised.append(item)
        shown_labels.add(label)
        if len(shown_advertised) >= 100:
            break
    shown_advertised_ids = {item["id"] for item in shown_advertised}
    for advertised in shown_advertised:
        label = (advertised["label"] or advertised["kind"]).replace('"', "'")[:60]
        lines.append(f'  {_slug(advertised["id"])}["{label} [not tested]"]')
    for edge in graph["edges"]:
        if edge["type"] not in {"offers_or_executes", "results_in", "validated_from_path_instance", "offers_untested"}:
            continue
        if edge["type"] == "offers_untested" and edge["target"] not in shown_advertised_ids:
            continue
        source = _slug(edge["source"])
        target = _slug(edge["target"])
        status = str(edge["status"])
        lines.append(f"  {source} -->|{status}| {target}")
    lines.extend(
        [
            "  classDef replay_validated fill:#d7f5df,stroke:#237a3b,color:#102a18;",
            "  classDef observed fill:#fff3cd,stroke:#9a7600,color:#332600;",
            "  classDef failed fill:#f8d7da,stroke:#a61b29,color:#3d080d;",
            "  classDef functional_verified fill:#c8f7c5,stroke:#176b2c,color:#102a18;",
            "  classDef validation_failure fill:#ffe0b2,stroke:#b35c00,color:#3d2100;",
            "  classDef not_tested fill:#e2e3e5,stroke:#6c757d,color:#202124;",
            "  classDef navigation_only fill:#d6eaff,stroke:#245b91,color:#10253b;",
            "  classDef unresolved fill:#fff3cd,stroke:#9a7600,color:#332600;",
            "  classDef resource_fetched fill:#d7f5df,stroke:#237a3b,color:#102a18;",
            "  classDef resource_discovered fill:#fff3cd,stroke:#9a7600,color:#332600;",
            "  classDef resource_failed fill:#f8d7da,stroke:#a61b29,color:#3d080d;",
        ]
    )
    for action in graph["nodes"]["actions_evidence"]:
        status = str(action["status"])
        if status in {"replay_validated", "observed", "failed"}:
            lines.append(f"  class {_slug(action['id'])} {status};")
    for workflow in graph["nodes"].get("functional_workflows", []):
        status = str(workflow["status"])
        if status in {"functional_verified", "validation_failure", "not_tested", "navigation_only", "unresolved", "failed"}:
            lines.append(f"  class {_slug(workflow['id'])} {status};")
    for advertised in shown_advertised:
        lines.append(f"  class {_slug(advertised['id'])} not_tested;")
    for _, (resource_id, statuses) in resource_nodes.items():
        if len(statuses) == 1:
            status = next(iter(statuses))
            if status in {"fetched", "discovered", "failed"}:
                lines.append(f"  class {_slug(resource_id)} resource_{status};")
    return "\n".join(lines) + "\n"


def report_markdown(artifact: RunArtifact) -> str:
    metrics = artifact.metrics
    validated = [feature for feature in artifact.features if feature.status == EvidenceStatus.REPLAY_VALIDATED]
    observed = [feature for feature in artifact.features if feature.status == EvidenceStatus.OBSERVED]
    failed = [transition for transition in artifact.transitions if transition.status == EvidenceStatus.FAILED]
    lines = [
        f"# Agent 1 run {artifact.run_id}",
        "",
        f"- Code revision: `{artifact.code_revision}`",
        f"- Policy: `{artifact.config.get('policy')}`",
        f"- Target: `{artifact.config.get('start_url')}`",
        f"- Elapsed: {metrics.elapsed_seconds:.3f} seconds",
        f"- Browser actions (including setup/replay): {metrics.browser_actions}",
        f"- Replay-validated navigation categories: {metrics.navigation_categories_replay_validated}",
        f"- Verified functional workflows: {metrics.functional_workflows_verified}",
        f"- Reproduced validation failures: {metrics.functional_validation_failures}",
        f"- Functional outcomes unresolved/untested/failed: {metrics.functional_unresolved}",
        f"- Replay navigation success: {metrics.replay_navigation_successes}/{metrics.replay_attempts}",
        f"- Replay failures / untested paths: {metrics.replay_failures}/{metrics.replay_untested_paths}",
        f"- Graph connections with complete evidence: {metrics.graph_connections_complete}/{metrics.graph_connections_total}",
        f"- Graph connections missing evidence: {metrics.graph_connections_missing_evidence}",
        f"- Incorrect state merges found by audit: {metrics.incorrect_state_merges}",
        f"- Redundant raw states: {metrics.redundant_states}",
        f"- Model calls / cost: {metrics.model_calls} / ${metrics.monetary_cost_usd:.6f}",
        "",
        "## Fully replay-validated navigation categories",
        "",
    ]
    if validated:
        lines.extend(f"- `{feature.id}` — {feature.description}" for feature in validated)
    else:
        lines.append("- None.")
    lines.extend(["", "## Functional path-instance outcomes", ""])
    if artifact.functional_workflows:
        lines.extend(
            f"- `{item.id}` — {item.action_label}: `{item.status}` (path length {item.path_length})"
            for item in artifact.functional_workflows
        )
    else:
        lines.append("- None.")
    lines.extend(["", "## Observed but not replay-validated", ""])
    if observed:
        lines.extend(f"- `{feature.id}` — {feature.description}" for feature in observed)
    else:
        lines.append("- None.")
    lines.extend(["", "## Failed or blocked transitions", ""])
    if failed:
        lines.extend(
            f"- `{item.id}` — {item.action.label}: {item.error}" for item in failed
        )
    else:
        lines.append("- None.")
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {note}" for note in artifact.notes)
    return "\n".join(lines) + "\n"


def write_outputs(artifact: RunArtifact, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    graph = build_graph_a(artifact)
    (output_dir / "graph_a.json").write_text(
        json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "graph_a.mmd").write_text(mermaid(graph), encoding="utf-8")
    (output_dir / "metrics.json").write_text(
        json.dumps(artifact.metrics.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(report_markdown(artifact), encoding="utf-8")
    with (output_dir / "trace.jsonl").open("w", encoding="utf-8") as handle:
        for transition in artifact.transitions:
            handle.write(json.dumps(transition.model_dump(mode="json"), sort_keys=True) + "\n")
    (output_dir / "run.json").write_text(
        json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
