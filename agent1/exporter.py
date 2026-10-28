from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .schema import EvidenceStatus, RunArtifact


def _slug(value: str) -> str:
    return "n_" + re.sub(r"[^A-Za-z0-9_]", "_", value)[:80]


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
                "title": representative.title if representative else "",
                "session_context": representative.session_context if representative else "",
                "observation_ids": member_ids,
                "raw_state_signatures": sorted({item.state_signature for item in members}),
                "return_path_length": len(artifact.return_paths.get(group, [])),
            }
        )
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
                "status": transition.status,
                "workflow_path_length": len(transition.workflow_path),
                "input_references": [item.model_dump(mode="json") for item in transition.input_references],
                "network": [item.model_dump(mode="json") for item in transition.network],
                "error": transition.error,
                "run_id": transition.run_id,
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
    attempted = {
        (transition.source_observation_id, transition.action.control_id)
        for transition in artifact.transitions
    }
    for item in artifact.advertisements:
        if (item.source_observation_id, item.control.id) in attempted:
            continue
        advertised.append(
            {
                "source_observation_id": item.source_observation_id,
                "source_group_signature": item.source_group_signature,
                "control": item.control.model_dump(mode="json"),
                "status": EvidenceStatus.ADVERTISED,
            }
        )
    return {
        "schema_version": "graph-a-1.0",
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
        },
        "edges": evidence_edges + feature_edges,
        "advertised_unexecuted": advertised,
        "replays": [item.model_dump(mode="json") for item in artifact.replays],
        "notes": artifact.notes,
    }


def mermaid(graph: dict[str, Any]) -> str:
    lines = ["flowchart LR"]
    states = graph["nodes"]["states"]
    for state in states:
        label = (state["title"] or state["route_pattern"] or "state").replace('"', "'")[:60]
        lines.append(f'  {_slug(state["id"])}["{label}"]')
    for action in graph["nodes"]["actions_evidence"]:
        label = (action["label"] or action["kind"]).replace('"', "'")[:60]
        status = str(action["status"])
        lines.append(f'  {_slug(action["id"])}{{"{label} [{status}]"}}')
    for edge in graph["edges"]:
        if edge["type"] not in {"offers_or_executes", "results_in"}:
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
        ]
    )
    for action in graph["nodes"]["actions_evidence"]:
        status = str(action["status"])
        if status in {"replay_validated", "observed", "failed"}:
            lines.append(f"  class {_slug(action['id'])} {status};")
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
        f"- Validated feature workflows: {len(validated)}",
        f"- Replay success: {metrics.replay_success_numerator}/{metrics.replay_success_denominator}",
        f"- Unsupported connections: {metrics.unsupported_connections}",
        f"- Incorrect state merges found by audit: {metrics.incorrect_state_merges}",
        f"- Redundant raw states: {metrics.redundant_states}",
        f"- Model calls / cost: {metrics.model_calls} / ${metrics.monetary_cost_usd:.6f}",
        "",
        "## Replay-validated workflows",
        "",
    ]
    if validated:
        lines.extend(f"- `{feature.id}` — {feature.description}" for feature in validated)
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
