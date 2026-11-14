"""Capability-level scoring of an ACG export against frozen ground truth.

Evaluator side: it may read display labels from the evidence log to map
actions to ground-truth entry points; the ACG itself never does.
Unavailable measurements are reported as None, never as zero.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from agent1.model.evidence import Record
from .ground_truth import Capability as GTCapability, GroundTruth, Operation as GTOperation

RANK = {"hypothesized": 0, "observed": 1, "reproduced": 2, "verified": 3}


def _route_regex(route: str) -> re.Pattern[str]:
    parts = re.split(r"(\{id\}|\{slug\})", route)
    body = "".join("[^/?#]+" if p in {"{id}", "{slug}"} else re.escape(p) for p in parts)
    return re.compile("^" + body + "$")


def route_matches(gt_route: str, path: str) -> bool:
    """`path` is a concrete path or an ACG route with {id} placeholders."""
    return bool(_route_regex(gt_route).match(path.split("?", 1)[0]))


def _op_matches(gt: GTOperation, op: dict[str, Any]) -> bool:
    if gt.channel != op.get("channel", "http") or (gt.method or "").upper() != (op.get("method") or "").upper():
        return False
    if not route_matches(gt.route, op["route"]):
        return False
    return all(key in (op.get("dispatch") or {}) for key in gt.dispatch)


def _request_matches(gt: GTOperation, request: dict[str, Any]) -> bool:
    return ((request.get("method") or "").upper() == gt.method.upper()
            and route_matches(gt.route, urlsplit(request.get("url", "")).path))


def _entry_matches(cap: GTCapability, action: Record, source_path: str | None) -> bool:
    aff = action.affordance
    if aff is None:
        return False
    for ep in cap.entry_points:
        if ep.kind and ep.kind != aff.kind:
            continue
        if ep.label is not None and ep.label.strip() != aff.label.strip():
            continue
        if ep.target_route and not (aff.target and route_matches(ep.target_route, urlsplit(aff.target).path)):
            continue
        if ep.source_route and not (source_path and route_matches(ep.source_route, source_path)):
            continue
        return True
    return False


def map_actions(gt: GroundTruth, records: list[Record]) -> dict[str, str | None]:
    """Ground-truth capability of each executed action (None = unmapped)."""
    observations = {r.obs_id: r for r in records if r.kind == "observation"}
    mapping: dict[str, str | None] = {}
    non = {n.id for n in gt.non_capabilities}
    for action in records:
        if action.kind != "action" or action.status != "observed":
            continue
        source = observations.get(action.source_obs or "")
        source_path = urlsplit(source.url).path if source and source.url else None
        candidates = [c for c in gt.capabilities if _entry_matches(c, action, source_path)]
        if len(candidates) > 1:
            requests = [r.model_dump() for r in action.requests or []]
            narrowed = [c for c in candidates if any(_request_matches(o, q) for o in c.operations for q in requests)]
            candidates = narrowed or candidates
        if not candidates:
            nonmatch = [n.id for n in gt.non_capabilities
                        if any(ep.label and action.affordance and ep.label == action.affordance.label for ep in n.entry_points)]
            mapping[action.action_id] = f"non:{nonmatch[0]}" if nonmatch else None
        else:
            mapping[action.action_id] = sorted(c.id for c in candidates)[0] if len(candidates) == 1 else "ambiguous:" + ",".join(sorted(c.id for c in candidates))
    assert not (set(mapping.values()) & non)
    return mapping


def _partition_quality(groups: dict[str, list[str]], mapping: dict[str, str | None],
                       indistinguishable: list[list[str]]) -> dict[str, Any]:
    """groups: model group id -> action ids. Merges/splits against the GT action mapping."""
    indist = [set(g) for g in indistinguishable]
    incorrect_merges, indistinguishable_merges, correct_merges = [], [], 0
    gt_to_groups: dict[str, set[str]] = defaultdict(set)
    for gid, actions in groups.items():
        truths = {mapping.get(a) for a in actions if mapping.get(a) and not str(mapping.get(a)).startswith(("ambiguous", "non:"))}
        for t in truths:
            gt_to_groups[t].add(gid)
        if len(truths) > 1:
            if any(truths <= g for g in indist):
                indistinguishable_merges.append(sorted(truths))
            else:
                incorrect_merges.append(sorted(truths))
        elif len(truths) == 1 and len(actions) > 1:
            correct_merges += 1
    splits = {t: sorted(g) for t, g in gt_to_groups.items() if len(g) > 1}
    return {"incorrect_merges": incorrect_merges, "indistinguishable_merges": indistinguishable_merges,
            "correct_merges": correct_merges, "splits": splits, "groups": len(groups),
            "gt_capabilities_reached": sorted(gt_to_groups)}


def score_capabilities(gt: GroundTruth, export: dict[str, Any], records: list[Record]) -> dict[str, Any]:
    if not gt.capabilities_annotated:
        return {"capability_scoring": None, "reason": "capabilities not annotated for this application"}
    ops = {o["id"]: o for o in export["operations"]}
    caps = [c for c in export["capabilities"] if RANK.get(c["status"], 0) >= RANK["observed"]]
    labels_of = {c["id"]: {l["text"] for l in c.get("labels", [])} for c in caps}
    in_scope = [c for c in gt.capabilities if c.in_scope]
    pairs = []
    for g in in_scope:
        for c in caps:
            cops = [ops[i] for i in c["operation_ids"]]
            if g.operations:
                score = sum(any(_op_matches(o, co) for co in cops) for o in g.operations)
            else:
                effect_ok = any(e["kind"] == g.no_operation_effect for e in c["effects"])
                label_ok = any(ep.label in labels_of[c["id"]] for ep in g.entry_points if ep.label)
                score = 1 if (not cops and effect_ok and label_ok) else 0
            if score:
                pairs.append((-score, g.id, c["id"]))
    matched_gt, matched_acg, matches = set(), set(), {}
    for _, gid, cid in sorted(pairs):
        if gid not in matched_gt and cid not in matched_acg:
            matched_gt.add(gid); matched_acg.add(cid); matches[gid] = cid
    mapping = map_actions(gt, records)
    acg_groups = {c["id"]: c["action_ids"] for c in caps}
    quality = _partition_quality(acg_groups, mapping, gt.indistinguishable)
    by_id = {c.id: c for c in gt.capabilities}
    acg_by_id = {c["id"]: c for c in caps}
    asserted = [(gid, acg_by_id[cid]["behavioral_class"]) for gid, cid in matches.items() if acg_by_id[cid].get("behavioral_class")]
    unmatched_asserted = [c for c in caps if c.get("behavioral_class") and c["id"] not in matched_acg]
    correct = sum(1 for gid, cls in asserted if cls["name"] == by_id[gid].behavioral_class)
    observable = [gid for gid in matches if by_id[gid].class_observable_to_role]
    observable_all = [c.id for c in in_scope if c.class_observable_to_role]
    return {
        "m1a_recall": {"value": len(matched_gt) / len(in_scope) if in_scope else None,
                        "matched": len(matched_gt), "denominator": len(in_scope)},
        "m1a_precision": {"value": len(matched_acg) / len(caps) if caps else None,
                           "matched": len(matched_acg), "denominator": len(caps)},
        "matches": dict(sorted(matches.items())),
        "unmatched_gt": sorted(c.id for c in in_scope if c.id not in matched_gt),
        "unmatched_acg": sorted(c["id"] for c in caps if c["id"] not in matched_acg),
        "m1b_precision": {"value": correct / (len(asserted) + len(unmatched_asserted)) if (asserted or unmatched_asserted) else None,
                           "correct": correct, "asserted": len(asserted) + len(unmatched_asserted)},
        "m1b_recall": {"value": (sum(1 for gid in observable if any(g == gid and cls["name"] == by_id[gid].behavioral_class for g, cls in asserted)) / len(observable)) if observable else None,
                        "correct": sum(1 for gid, cls in asserted if cls["name"] == by_id[gid].behavioral_class and by_id[gid].class_observable_to_role),
                        "denominator_matched_observable": len(observable),
                        "observable_in_ground_truth": len(observable_all)},
        "capability_merges": quality,
        "action_mapping_unmapped": sorted(a for a, t in mapping.items() if t is None),
    }


def score_legacy_features(gt: GroundTruth, features: list[dict[str, Any]], records: list[Record]) -> dict[str, Any]:
    """Graph A feature baseline under the same action-based merge/split measure."""
    mapping = map_actions(gt, records)
    groups = {f["id"]: [t.removeprefix("action_") for t in f.get("evidence_transition_ids", [])] for f in features}
    quality = _partition_quality(groups, mapping, gt.indistinguishable)
    in_scope = {c.id for c in gt.capabilities if c.in_scope}
    reached = set(quality["gt_capabilities_reached"]) & in_scope
    return {"features": len(features), "gt_capabilities_reached": len(reached), "denominator": len(in_scope),
            "action_based_recall": len(reached) / len(in_scope) if in_scope else None, "partition": quality}


def score_action_based(gt: GroundTruth, export: dict[str, Any], records: list[Record]) -> dict[str, Any]:
    """The same action-based measure for the ACG (fair comparison with features)."""
    mapping = map_actions(gt, records)
    caps = [c for c in export["capabilities"] if RANK.get(c["status"], 0) >= 1]
    quality = _partition_quality({c["id"]: c["action_ids"] for c in caps}, mapping, gt.indistinguishable)
    in_scope = {c.id for c in gt.capabilities if c.in_scope}
    reached = set(quality["gt_capabilities_reached"]) & in_scope
    return {"capabilities": len(caps), "gt_capabilities_reached": len(reached), "denominator": len(in_scope),
            "action_based_recall": len(reached) / len(in_scope) if in_scope else None, "partition": quality}


def true_instance(gt: GroundTruth, path: str) -> tuple[str, str] | None:
    for entity in gt.entity_types:
        for pattern in entity.identity:
            parts = pattern.strip("/").split("/")
            segs = path.split("?", 1)[0].strip("/").split("/")
            if len(parts) != len(segs):
                continue
            value = None
            for p, s in zip(parts, segs):
                if p in {"{id}", "{slug}"}:
                    value = s
                elif p != s:
                    break
            else:
                if value is not None:
                    return entity.id, value
    return None


def score_identity(gt: GroundTruth, export: dict[str, Any], observation_paths: dict[str, str]) -> dict[str, Any]:
    instances = export["entity_instances"]
    incorrect, correct, owners = [], 0, defaultdict(set)
    for inst in instances:
        truths = {true_instance(gt, p) for p in inst["observed_paths"]} - {None}
        for t in truths:
            owners[t].add(inst["id"])
        if len(truths) > 1:
            incorrect.append(sorted(map(str, truths)))
        elif len(truths) == 1 and len(inst["evidence_ids"]) > 1:
            correct += 1
    true_all = {true_instance(gt, p) for p in observation_paths.values()} - {None}
    splits = {f"{k[0]}:{k[1]}": sorted(v) for k, v in owners.items() if len(v) > 1}
    templates = export["templates"]
    gt_templates = defaultdict(set)
    unmatched_templates = []
    for t in templates:
        hits = [g for g in gt.templates if route_matches(g, t["route"])]
        for g in hits:
            gt_templates[(g, t["role"])].add(t["id"])
        if not hits:
            unmatched_templates.append(t["route"])
    template_splits = {f"{g}@{role}": sorted(ids) for (g, role), ids in gt_templates.items() if len(ids) > 1}
    return {"entity_instances": len(instances), "true_instances_observed": len(true_all),
            "incorrect_entity_merges": incorrect, "correct_entity_merges": correct, "entity_splits": splits,
            "templates": len(templates), "template_splits_vs_ground_truth": template_splits,
            "templates_without_ground_truth_route": sorted(unmatched_templates)}


def score_provenance(export: dict[str, Any], records: list[Record]) -> dict[str, Any]:
    ids = {r.id for r in records}
    claims = export["claims"]
    complete = [c for c in claims if c["evidence_ids"] and all(e in ids for e in c["evidence_ids"]) and c["sources"]
                and (c["status"] not in {"blocked", "refuted"} or c.get("reason"))]
    caps = export["capabilities"]
    grounded = [c for c in caps if c["evidence_ids"] and all(e in ids for e in c["evidence_ids"])]
    return {"claims": len(claims), "claims_with_complete_provenance": len(complete),
            "fraction": len(complete) / len(claims) if claims else None,
            "capabilities_with_grounded_evidence": len(grounded), "capabilities": len(caps)}


def observation_paths(records: list[Record]) -> dict[str, str]:
    return {r.obs_id: urlsplit(r.url).path for r in records if r.kind == "observation" and r.url}


def query_values(url: str) -> dict[str, str]:
    return dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))


def role_aware_precision(gt: GroundTruth, export: dict[str, Any], frozen: dict[str, Any]) -> dict[str, Any]:
    """Secondary diagnostic, not the frozen M1a: an unmatched ACG capability whose
    operations match an already-matched ground-truth capability but whose role
    differs is a role-scoped duplicate (design: capabilities are per role)."""
    ops = {o["id"]: o for o in export["operations"]}
    caps = {c["id"]: c for c in export["capabilities"]}
    by_id = {c.id: c for c in gt.capabilities}
    duplicates = 0
    for cid in frozen["unmatched_acg"]:
        c = caps[cid]
        for gid, mid in frozen["matches"].items():
            g = by_id[gid]
            if c["role"] != caps[mid]["role"] and g.operations and any(
                    _op_matches(o, ops[x]) for o in g.operations for x in c["operation_ids"]):
                duplicates += 1
                break
    total = frozen["m1a_precision"]["denominator"]
    matched = frozen["m1a_precision"]["matched"] + duplicates
    return {"role_scoped_duplicates": duplicates, "matched": matched, "denominator": total,
            "value": matched / total if total else None}
