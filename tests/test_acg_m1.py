"""Phase 1 gate checks on archived development evidence (offline; no browser)."""
from __future__ import annotations

import ast
import json
from collections import defaultdict
from pathlib import Path

import pytest

from agent1.model.importer import import_path
from agent1.model.materialize import Materializer, materialize
from evaluation.datasets import archive_paths
from evaluation.ground_truth import load_ground_truth
from evaluation.score_acg import observation_paths, score_capabilities, score_identity, score_provenance

ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS = ROOT / "evaluation" / "annotations"


def _present(name: str) -> list[Path]:
    paths = [p for p in archive_paths(name) if p.exists()]
    if not paths:
        pytest.skip(f"{name} archives are local-only and not present")
    return paths


def test_stateful_lab_records_stay_distinct_and_capabilities_are_measured() -> None:
    path = archive_paths("stateful_lab")[0]          # committed Graph A
    records = import_path(path, "stateful_lab", ROOT)
    export = materialize(records)
    dump = export.model_dump(mode="json")
    gt = load_ground_truth(ANNOTATIONS / "stateful_lab.json")
    identity = score_identity(gt, dump, observation_paths(records))
    assert identity["incorrect_entity_merges"] == [] and identity["entity_splits"] == {}
    seeded = {p for inst in export.entity_instances for p in inst.observed_paths if p in {"/records/1", "/records/2"}}
    owners = {inst.id for inst in export.entity_instances for p in inst.observed_paths if p in seeded}
    assert seeded == {"/records/1", "/records/2"} and len(owners) == 2
    assert sorted(t.route for t in export.templates) == ["/", "/records/{id}"]
    caps = score_capabilities(gt, dump, records)
    assert caps["m1a_recall"]["value"] is not None and caps["capability_merges"]["incorrect_merges"] == []
    assert score_provenance(dump, records)["fraction"] == 1.0
    # A single observed transition is never promoted by the Graph A export.
    assert all(str(c.status) == "observed" for c in export.capabilities)


def test_stateful_lab_incremental_equals_full_at_every_cut() -> None:
    records = import_path(archive_paths("stateful_lab")[0], "stateful_lab", ROOT)
    full = materialize(records).model_dump(mode="json")
    for cut in range(1, len(records), 7):
        m = Materializer()
        m.add(records[:cut])
        m.export()
        m.add(records[cut:])
        assert m.export().model_dump(mode="json") == full


def test_whiteboard_record_identities_remain_separate() -> None:
    gt = load_ground_truth(ANNOTATIONS / "whiteboard.json")
    for path in _present("whiteboard"):
        records = import_path(path, "whiteboard", ROOT)
        export = materialize(records)
        identity = score_identity(gt, export.model_dump(mode="json"), observation_paths(records))
        assert identity["incorrect_entity_merges"] == [] and identity["entity_splits"] == {}
        assert identity["entity_instances"] == identity["true_instances_observed"] > 0
        detail = [t for t in export.templates if t.route.startswith("/canvases/")]
        assert len(detail) == 1, "canvases share one page template"


def test_replay_lab_has_no_incorrect_capability_merge() -> None:
    gt = load_ground_truth(ANNOTATIONS / "replay_lab.json")
    for path in _present("replay_lab"):
        records = import_path(path, "replay_lab", ROOT)
        caps = score_capabilities(gt, materialize(records).model_dump(mode="json"), records)
        assert caps["capability_merges"]["incorrect_merges"] == []


def test_crawl_maze_view_states_show_no_behavioral_divergence() -> None:
    for path in _present("crawl_maze"):
        records = import_path(path, "crawl_maze", ROOT)
        export = materialize(records)
        raw = json.loads(path.read_text())
        refined = {o.get("behavior_signature") or o["group_signature"] for o in raw["observations"]}
        assert len(export.view_states) <= len(refined)
        cap_of = {a: c.id for c in export.capabilities for a in c.action_ids}
        view = {o: v.id for v in export.view_states for o in v.observation_ids}
        aff = {a: x.id for x in export.affordances for a in x.action_ids}
        outcomes = defaultdict(set)
        for r in records:
            if r.kind == "action" and r.status == "observed":
                outcomes[(view.get(r.source_obs), aff.get(r.action_id))].add(cap_of.get(r.action_id, "none"))
        assert all(len(v) == 1 for v in outcomes.values())


def test_every_capability_is_grounded_in_cited_evidence() -> None:
    for name in ("stateful_lab", "replay_lab", "js_heavy_lab", "whiteboard", "crawl_maze"):
        for path in [p for p in archive_paths(name) if p.exists()][:1]:
            records = import_path(path, name, ROOT)
            ids = {r.id for r in records}
            for cap in materialize(records).capabilities:
                assert cap.evidence_ids and set(cap.evidence_ids) <= ids
                if cap.behavioral_class:
                    assert set(cap.behavioral_class.evidence_ids) <= ids and cap.behavioral_class.rule


def test_legacy_production_code_does_not_depend_on_the_model() -> None:
    for module in sorted((ROOT / "agent1").glob("*.py")):
        tree = ast.parse(module.read_text())
        imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not any("model" in name for name in imported), module.name
