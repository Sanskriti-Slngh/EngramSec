"""Phase 0: frozen evaluation foundation (no resolvers involved)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agent1.model.evidence import log_digest, read_log
from agent1.model.importer import import_path
from evaluation.datasets import DATASETS, archive_paths
from evaluation.ground_truth import load_ground_truth
from evaluation.purity_check import scan
from evaluation.score_acg import _partition_quality, route_matches, true_instance

ROOT = Path(__file__).resolve().parents[1]
CORPORA = ROOT / "evaluation" / "corpora"


@pytest.mark.parametrize("path", sorted((ROOT / "evaluation" / "annotations").glob("*.json")), ids=lambda p: p.stem)
def test_ground_truth_validates(path: Path) -> None:
    gt = load_ground_truth(path)
    assert gt.templates and gt.annotation.independent is False


def test_t1_expectations_cover_every_executed_action() -> None:
    expected = json.loads((CORPORA / "t1" / "expected.json").read_text())
    logs = sorted((CORPORA / "t1").glob("*.jsonl"))
    assert len(logs) == 8 and {p.stem for p in logs} == {k for k in expected if not k.startswith("_")}
    for path in logs:
        records = read_log(path)
        assert records[0].kind == "capture_manifest" and records[0].synthetic
        executed = {r.action_id for r in records if r.kind == "action" and r.status == "observed"}
        case = expected[path.stem]
        grouped = [a for group in case["partition"] for a in group] + case.get("no_effect_actions", [])
        assert sorted(grouped) == sorted(executed), path.stem


def test_t3_expectations_reference_existing_evidence() -> None:
    expected = json.loads((CORPORA / "t3" / "expected.json").read_text())
    records = read_log(CORPORA / "t3" / "t3_grounding.jsonl")
    ids = {r.id for r in records}
    actions = {r.action_id for r in records if r.kind == "action"}
    assert set(expected["classes"]) | set(expected["unclassified_actions"]) <= actions
    for ablation in expected["ablations"]:
        assert set(ablation["remove"]) <= ids and ablation["action"] in actions


def test_importer_is_deterministic_and_read_only() -> None:
    path = ROOT / "agent1" / "experiments" / "stateful_fixture_example" / "graph_a.json"
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    first, second = import_path(path, "stateful_lab", ROOT), import_path(path, "stateful_lab", ROOT)
    assert log_digest(first) == log_digest(second)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    manifest = first[0]
    assert manifest.kind == "capture_manifest" and manifest.capture.dom_affordances is False
    assert all(r.affordances is None for r in first if r.kind == "observation" and r.context == "exploration")


@pytest.mark.parametrize("name", sorted(DATASETS))
def test_local_archives_import(name: str) -> None:
    present = [p for p in archive_paths(name) if p.exists()]
    if not present:
        pytest.skip("archive not available locally")
    records = import_path(present[0], name, ROOT)
    assert [r.seq for r in records] == list(range(len(records)))
    assert log_digest(records) == log_digest(import_path(present[0], name, ROOT))


def test_dataset_registry_refuses_held_out_archives() -> None:
    assert not any(f in str(p).lower() for name in DATASETS for p in archive_paths(name)
                   for f in ("comfyui", "prestashop", "siyucms", "heldout", "webexploitbench"))


def test_model_package_has_no_application_specific_knowledge() -> None:
    assert scan([ROOT / "agent1" / "model"]) == []


def test_scorer_partition_quality_and_identity() -> None:
    mapping = {"a": "x", "b": "x", "c": "y", "d": "z"}
    q = _partition_quality({"g1": ["a", "b"], "g2": ["c", "d"]}, mapping, [["y", "z"]])
    assert q["correct_merges"] == 1 and q["incorrect_merges"] == [] and q["indistinguishable_merges"] == [["y", "z"]]
    q = _partition_quality({"g1": ["a"], "g2": ["b", "c"]}, mapping, [])
    assert q["incorrect_merges"] == [["x", "y"]] and q["splits"] == {"x": ["g1", "g2"]}
    assert route_matches("/records/{id}", "/records/12") and route_matches("/topics/{slug}", "/topics/music")
    assert not route_matches("/records/{id}", "/records/12/edit")
    gt = load_ground_truth(ROOT / "evaluation" / "annotations" / "whiteboard.json")
    assert true_instance(gt, "/canvas/abc") == ("canvas", "abc") and true_instance(gt, "/") is None
