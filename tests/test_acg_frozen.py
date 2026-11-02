"""Frozen offline falsification tests T1 and T3 (GENERALIZATION_AND_EVALUATION_PLAN.md §4.1).

Written in Phase 0 against the published contracts, before any resolver
existed. They skip until `agent1.model.materialize` exists. Do not edit the
expectations or these assertions to make an implementation pass.
Planner-specific checks (T3a decision-log hash, T3e) belong to Phase 1b.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from agent1.model.evidence import Record, read_log

materialize_module = pytest.importorskip("agent1.model.materialize")
materialize = materialize_module.materialize
Materializer = materialize_module.Materializer

CORPORA = Path(__file__).resolve().parents[1] / "evaluation" / "corpora"
T1 = json.loads((CORPORA / "t1" / "expected.json").read_text())
T3 = json.loads((CORPORA / "t3" / "expected.json").read_text())
T1_CASES = sorted(k for k in T1 if not k.startswith("_"))
RANK = {"hypothesized": 0, "observed": 1, "reproduced": 2, "verified": 3}
RULE_MIN = {"navigation": "reproduced", "instance_view": "reproduced", "client_view_change": "reproduced",
            "server_job_submission": "reproduced", "instance_creation": "verified", "instance_removal": "verified",
            "instance_modification": "verified", "collection_query": "verified"}
LABEL_KEYS = {"labels", "label_candidates"}


def _log(name: str) -> list[Record]:
    folder = name.split("_", 1)[0]
    return read_log(CORPORA / folder / f"{name}.jsonl")


def _caps(export):
    return [c for c in export.capabilities if RANK.get(str(c.status), 0) >= 1]


def _partition(export) -> list[list[str]]:
    return sorted(sorted(c.action_ids) for c in _caps(export))


def _cap_of(export, action: str):
    found = [c for c in _caps(export) if action in c.action_ids]
    assert len(found) <= 1
    return found[0] if found else None


def _classes(export) -> dict[str, tuple[str, str]]:
    return {a: (c.behavioral_class.name, str(c.behavioral_class.status))
            for c in _caps(export) if c.behavioral_class for a in c.action_ids}


def _strip_labels(value):
    if isinstance(value, dict):
        return {k: _strip_labels(v) for k, v in value.items() if k not in LABEL_KEYS}
    if isinstance(value, list):
        return [_strip_labels(v) for v in value]
    return value


# ---------------------------------------------------------------- T1
@pytest.mark.parametrize("case", T1_CASES)
def test_t1_partition(case: str) -> None:
    expected = T1[case]
    export = materialize(_log(case))
    assert _partition(export) == sorted(sorted(g) for g in expected["partition"])
    assert _classes(export) == {a: tuple(v) for a, v in expected["classes"].items()}
    for action in expected.get("no_effect_actions", []):
        assert _cap_of(export, action) is None
        assert any(action in a.action_ids and a.status == "executed_no_effect" for a in export.affordances)
    for action, count in expected.get("bindings_of", {}).items():
        assert len(_cap_of(export, action).bindings) == count
    if "unbound_affordances" in expected:
        assert sum(a.status == "unbound" for a in export.affordances) == expected["unbound_affordances"]
    for action in expected.get("unidentified", []):
        cap = _cap_of(export, action)
        assert cap.unidentified and cap.behavioral_class is None
    if "learned_predicates" in expected:
        got = sorted((p.template_route, p.kind) for p in export.learned_predicates)
        assert got == sorted((p["template_route"], p["kind"]) for p in expected["learned_predicates"])
    for group in expected.get("equivalent_interfaces", []):
        cap = _cap_of(export, group[0])
        assert set(group) <= set(cap.action_ids) and len(cap.bindings) >= 2
    if "entity_instances" in expected:
        assert len(export.entity_instances) == expected["entity_instances"]
    if "templates" in expected:
        assert sorted(t.route for t in export.templates) == sorted(expected["templates"])


@pytest.mark.parametrize("case", T1_CASES + ["t3_grounding"])
def test_full_rebuild_is_deterministic_and_order_independent(case: str) -> None:
    records = _log(case)
    shuffled = list(records)
    random.Random(7).shuffle(shuffled)
    first = materialize(records).model_dump(mode="json")
    assert first == materialize(records).model_dump(mode="json") == materialize(shuffled).model_dump(mode="json")


@pytest.mark.parametrize("case", T1_CASES + ["t3_grounding"])
def test_incremental_equals_full(case: str) -> None:
    records = _log(case)
    full = materialize(records).model_dump(mode="json")
    for cut in range(1, len(records)):
        m = Materializer()
        m.add(records[:cut])
        m.export()                       # materialize the prefix, then extend it
        m.add(records[cut:])
        assert m.export().model_dump(mode="json") == full, cut


# ---------------------------------------------------------------- T3
def test_t3_grounding_classes() -> None:
    export = materialize(_log("t3_grounding"))
    classes = _classes(export)
    for action, spec in T3["classes"].items():
        assert action in classes, action
        name, status = classes[action]
        assert name == spec["class"] and RANK[status] >= RANK[spec["min_status"]], action
    for action in T3["unclassified_actions"]:
        assert action not in classes


@pytest.mark.parametrize("ablation", T3["ablations"], ids=lambda a: f"{a['action']}-{a['remove'][0]}")
def test_t3b_evidence_ablation_removes_only_that_class(ablation) -> None:
    records = [r for r in _log("t3_grounding") if r.id not in set(ablation["remove"])]
    classes = _classes(materialize(records))
    assert ablation["action"] not in classes
    for action, spec in T3["classes"].items():
        if action != ablation["action"]:
            assert classes.get(action, (None,))[0] == spec["class"], action


def _rewrite(records: list[Record], mode: str, seed: int = 0) -> list[Record]:
    rng = random.Random(seed)
    zh = ["保存", "删除", "搜索", "打开", "继续", "设置", "帮助", "画布"]

    def text(_old: str) -> str:
        if mode == "random":
            return "".join(rng.choice("qwxzjk") for _ in range(rng.randint(3, 9)))
        return rng.choice(zh) + str(rng.randint(0, 99))
    out = []
    for r in records:
        update = {}
        if r.title:
            update["title"] = text(r.title)
        if r.affordances:
            update["affordances"] = [a.model_copy(update={"label": text(a.label)}) for a in r.affordances]
        if r.affordance:
            update["affordance"] = r.affordance.model_copy(update={"label": text(r.affordance.label)})
        out.append(r.model_copy(update=update))
    return out


@pytest.mark.parametrize("mode", ["random", "zh"])
@pytest.mark.parametrize("case", T1_CASES + ["t3_grounding"])
def test_t3a_text_invariance(case: str, mode: str) -> None:
    records = _log(case)
    original = _strip_labels(materialize(records).model_dump(mode="json"))
    rewritten = _strip_labels(materialize(_rewrite(records, mode)).model_dump(mode="json"))
    assert rewritten == original


def test_t3c_no_class_without_rule_and_evidence() -> None:
    logs = {name: _log(name) for name in T1_CASES + ["t3_grounding"]}
    names = sorted(logs)
    for seed in range(T3["random_subsets"]["seeds"]):
        rng = random.Random(seed)
        records = logs[names[seed % len(names)]]
        subset = [records[0]] + [r for r in records[1:] if rng.random() < 0.7]
        ids = {r.id for r in subset}
        for cap in materialize(subset).capabilities:
            cls = cap.behavioral_class
            if cls is None:
                continue
            assert cls.rule and cls.evidence_ids and set(cls.evidence_ids) <= ids, (seed, cap.id)
            assert RANK[str(cls.status)] >= RANK[RULE_MIN[cls.name]], (seed, cap.id)


@pytest.mark.parametrize("case", T1_CASES + ["t3_grounding"])
def test_t3d_every_label_is_traceable(case: str) -> None:
    records = _log(case)
    by_id = {r.id: r for r in records}
    export = materialize(records)
    labels = [l for a in export.affordances for l in a.labels] + [l for c in export.capabilities for l in c.labels] + \
             [l for e in export.entity_types for l in e.label_candidates]
    for label in labels:
        assert label.evidence_id in by_id
        assert json.dumps(label.text, ensure_ascii=False)[1:-1] in by_id[label.evidence_id].model_dump_json()
