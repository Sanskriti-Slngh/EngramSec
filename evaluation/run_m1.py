"""Milestone 1: build the ACG offline from archived development evidence and score it.

Raw evidence logs and ACG exports stay local (git-ignored). The committed
scorecard holds aggregates only: no URLs, tokens, identifiers or labels from
the archives.
Run: .venv/bin/python -m evaluation.run_m1
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from agent1.model.evidence import Record, write_log
from agent1.model.importer import import_path
from agent1.model.materialize import Materializer, materialize
from .datasets import DATASETS, ROOT, archive_paths
from .ground_truth import load_ground_truth
from .score_acg import (map_actions, observation_paths, role_aware_precision, score_action_based, score_capabilities,
                        score_identity, score_legacy_features, score_provenance)

LOCAL = ROOT / "agent1" / "experiments" / "acg_m1_20261101"
SCORECARD = ROOT / "evaluation" / "results" / "acg_m1_scorecard.json"


def _raw(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("artifact", data)


def _legacy(raw: dict[str, Any]) -> dict[str, Any]:
    if "nodes" in raw:
        n = raw["nodes"]
        return {"features": n.get("features", []), "groups": len(n.get("states", [])),
                "record_instances": len(n.get("record_instances", [])), "page_templates": len(n.get("page_templates", [])),
                "transition_groups": {}}
    return {"features": raw.get("features", []), "groups": len(raw.get("state_groups", {})),
            "record_instances": None, "page_templates": None,
            "transition_groups": {t["id"]: (t.get("source_group_signature"), (t.get("action") or {}).get("signature"))
                                  for t in raw.get("transitions", [])}}


def _divergence(export, records: list[Record], legacy_groups: dict[str, tuple[str, str]]) -> dict[str, Any]:
    """Groups in which one affordance led to different capabilities (same outcome measure for both models)."""
    cap_of = {a: c.id for c in export.capabilities for a in c.action_ids}
    obs_view = {o: v.id for v in export.view_states for o in v.observation_ids}
    aff_of = {a: aff.id for aff in export.affordances for a in aff.action_ids}
    acg: dict[tuple[str, str], set[str]] = defaultdict(set)
    old: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in records:
        if r.kind != "action" or r.status != "observed":
            continue
        outcome = cap_of.get(r.action_id, "no_effect")
        acg[(obs_view.get(r.source_obs or "", "?"), aff_of.get(r.action_id, "?"))].add(outcome)
        if r.action_id in legacy_groups:
            old[legacy_groups[r.action_id]].add(outcome)
    return {"acg_view_state_divergences": sum(len(v) > 1 for v in acg.values()),
            "legacy_group_divergences": sum(len(v) > 1 for v in old.values()) if legacy_groups else None}


def _counterexamples(export, records: list[Record], mapping: dict[str, str | None] | None) -> dict[str, Any]:
    caps = export.capabilities
    by_ops = defaultdict(list)
    by_effects = defaultdict(list)
    for c in caps:
        if c.operation_ids:
            by_ops[tuple(c.operation_ids)].append(c)
        if c.effects:
            by_effects[(c.role, tuple(sorted((e.kind, e.target) for e in c.effects)))].append(c)

    def truth(cs) -> list[list[str]]:
        if mapping is None:
            return []
        return [sorted({str(mapping.get(a)) for a in c.action_ids}) for c in cs]
    same_ops = [cs for cs in by_ops.values() if len(cs) > 1]
    same_effects = [cs for cs in by_effects.values() if len({tuple(c.operation_ids) for c in cs}) > 1]
    actions = {r.action_id: r for r in records if r.kind == "action"}
    deep = [a for a in actions.values() if a.status == "observed" and a.workflow_length >= 3]
    cap_of = {a: c for c in caps for a in c.action_ids}
    roles_by_route = defaultdict(set)
    for t in export.templates:
        roles_by_route[t.route].add(t.role)
    return {
        "same_operations_different_effects": {"groups": len(same_ops), "ground_truth": [truth(cs) for cs in same_ops]},
        "different_operations_same_effects": {"groups": len(same_effects),
                                              "ground_truth": [truth(cs) for cs in same_effects]},
        "no_backend_request": {"capabilities": sum(1 for c in caps if not c.operation_ids),
                               "actions_without_capability": export.summary["actions_without_capability"]},
        "multi_step_prerequisites": {"actions": len(deep),
                                     "with_capability": sum(1 for a in deep if a.action_id in cap_of),
                                     "reproduced": sum(1 for a in deep if a.action_id in cap_of
                                                       and str(cap_of[a.action_id].status) != "observed")},
        "record_dependent_behavior": {"learned_record_predicates": sum(p.kind == "record_instance"
                                                                      for p in export.learned_predicates),
                                      "underdetermined": export.summary["underdetermined_behaviors"]},
        "same_route_multiple_roles": {"routes": sum(len(r) > 1 for r in roles_by_route.values())},
    }


def _sanitize_identity(identity: dict[str, Any]) -> dict[str, Any]:
    return {"entity_instances": identity["entity_instances"], "true_instances_observed": identity["true_instances_observed"],
            "incorrect_entity_merges": len(identity["incorrect_entity_merges"]),
            "correct_entity_merges": identity["correct_entity_merges"],
            "entity_splits": len(identity["entity_splits"]), "templates": identity["templates"],
            "template_splits_vs_ground_truth": len(identity["template_splits_vs_ground_truth"]),
            "templates_without_ground_truth_route": len(identity["templates_without_ground_truth_route"])}


def run_archive(name: str, path: Path) -> dict[str, Any]:
    spec = DATASETS[name]
    records = import_path(path, name, ROOT)
    export = materialize(records)
    again = materialize(records)
    incremental = Materializer()
    cut = len(records) // 2
    incremental.add(records[:cut])
    incremental.export()
    incremental.add(records[cut:])
    out = LOCAL / name / str(path.parent.relative_to(ROOT / "agent1" / "experiments")).replace("/", "__")
    write_log(records, out / "acg_evidence.jsonl")
    (out / "acg.json").write_text(export.model_dump_json(indent=1), encoding="utf-8")
    raw = _raw(path)
    legacy = _legacy(raw)
    gt = load_ground_truth(ROOT / "evaluation" / "annotations" / f"{spec['annotation']}.json") if spec["annotation"] else None
    dump = export.model_dump(mode="json")
    result: dict[str, Any] = {
        "archive": str(path.relative_to(ROOT)), "summary": export.summary,
        "gaps": {g.kind: g.count for g in export.gaps},
        "deterministic_full_rebuild": dump == again.model_dump(mode="json"),
        "incremental_equals_full": dump == incremental.export().model_dump(mode="json"),
        "provenance": score_provenance(dump, records),
        "legacy": {"features": len(legacy["features"]), "state_groups": legacy["groups"],
                   "record_instances": legacy["record_instances"], "page_templates": legacy["page_templates"]},
        "behavioral_divergence": _divergence(export, records, legacy["transition_groups"]),
    }
    mapping = None
    if gt is not None:
        result["identity"] = _sanitize_identity(score_identity(gt, dump, observation_paths(records)))
        if gt.capabilities_annotated:
            mapping = map_actions(gt, records)
            caps = score_capabilities(gt, dump, records)
            result["capabilities"] = {k: caps[k] for k in ("m1a_recall", "m1a_precision", "m1b_precision", "m1b_recall",
                                                           "unmatched_gt", "matches")}
            result["capabilities"]["merges"] = {
                "incorrect": caps["capability_merges"]["incorrect_merges"],
                "indistinguishable": caps["capability_merges"]["indistinguishable_merges"],
                "correct": caps["capability_merges"]["correct_merges"],
                "splits": caps["capability_merges"]["splits"]}
            result["capabilities"]["unmapped_actions"] = len(caps["action_mapping_unmapped"])
            result["capabilities"]["role_aware_precision_secondary"] = role_aware_precision(gt, dump, caps)
            result["capabilities"]["unmatched_acg_count"] = len(caps["unmatched_acg"])
            acg_actions = score_action_based(gt, dump, records)
            legacy_features = score_legacy_features(gt, legacy["features"], records)
            result["fair_comparison_action_based"] = {
                "acg": {k: acg_actions[k] for k in ("capabilities", "gt_capabilities_reached", "denominator")}
                | {"incorrect_merges": len(acg_actions["partition"]["incorrect_merges"]),
                   "splits": len(acg_actions["partition"]["splits"]),
                   "correct_merges": acg_actions["partition"]["correct_merges"]},
                "graph_a_features": {k: legacy_features[k] for k in ("features", "gt_capabilities_reached", "denominator")}
                | {"incorrect_merges": len(legacy_features["partition"]["incorrect_merges"]),
                   "splits": len(legacy_features["partition"]["splits"]),
                   "correct_merges": legacy_features["partition"]["correct_merges"]},
            }
    result["counterexamples"] = _counterexamples(export, records, mapping)
    (out / "score.json").write_text(json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    card: dict[str, Any] = {"milestone": "ACG M1 (Phase 1, offline)", "datasets": {}}
    for name in DATASETS:
        runs = [run_archive(name, p) for p in archive_paths(name) if p.exists()]
        card["datasets"][name] = {"role": DATASETS[name]["role"], "runs": runs}
        for r in runs:
            s = r["summary"]
            line = (f"{name:13} tpl={s['page_templates']:3} vs={s['view_states']:3} E={s['entity_types']:2} "
                    f"inst={s['entity_instances']:3} caps={s['capabilities']:3} unid={s['unidentified_operations']:3} "
                    f"eq={s['equivalent_interface_groupings']:2} status={s['capabilities_by_status']} "
                    f"det={r['deterministic_full_rebuild']} inc={r['incremental_equals_full']}")
            if "capabilities" in r:
                c = r["capabilities"]
                line += (f" M1a R={c['m1a_recall']['matched']}/{c['m1a_recall']['denominator']}"
                         f" P={c['m1a_precision']['matched']}/{c['m1a_precision']['denominator']}"
                         f" M1b={c['m1b_precision']['correct']}/{c['m1b_precision']['asserted']}"
                         f" badmerge={len(c['merges']['incorrect'])}")
            print(line)
    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    # Whiteboard and Crawl Maze runs come from local services; keep only aggregates.
    for name in ("whiteboard", "crawl_maze"):
        for r in card["datasets"][name]["runs"]:
            r.pop("archive", None)
    SCORECARD.write_text(json.dumps(card, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
