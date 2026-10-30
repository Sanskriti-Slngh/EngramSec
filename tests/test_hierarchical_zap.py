from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent1.explorer import Explorer, HttpBudget
from agent1.exporter import build_graph_a
from agent1.hierarchical import AreaTourPlanner, area_key
from agent1.resource_spider import ResourceBudget, TypedResourceSpider
from agent1.schema import ActionDescriptor, FrontierItem, Observation, RunArtifact, RunConfig, utc_now
from agent1.zap_adapter import load_zap_evidence


def test_zap_import_scope_provenance_and_no_replay_promotion(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps({
        "schema": "zap-http-history-1", "run_id": "run-1",
        "source_origin": "http://crawlmaze:3460", "request_upper_bound": 4,
        "elapsed_seconds": 1.5, "records": [
            {"path": "/item/1", "method": "GET", "status": 200, "parameter_names": [], "body": "never-export"},
            {"path": "/candidate", "method": "GET", "status": 0, "parameter_names": []},
            {"path": "//outside.test/a", "method": "GET", "status": 200, "parameter_names": []},
            {"path": "/%2e%2e/admin", "method": "GET", "status": 200, "parameter_names": []},
            {"path": "/x?token=value", "method": "GET", "status": 200, "parameter_names": []},
        ],
    }), encoding="utf-8")
    rows, rejected, cost, elapsed = load_zap_evidence(path, "http://crawlmaze:3460", "http://127.0.0.1:8000/")
    assert len(rows) == 2 and rejected == 3 and cost == 4 and elapsed == 1.5
    assert rows[0].status == "external_response" and rows[1].status == "external_candidate"
    assert all(row.session_context == "unknown" for row in rows)
    with pytest.raises(ValueError, match="source origin"):
        load_zap_evidence(path, "http://other:3460", "http://127.0.0.1:8000/")
    graph = build_graph_a(RunArtifact(run_id="a", code_revision="test", config={}, started_at=utc_now(), external_discoveries=rows))
    assert {edge["type"] for edge in graph["edges"]} == {"external_report"}
    assert not graph["nodes"]["actions_evidence"] and not graph["replays"]
    assert "never-export" not in json.dumps(graph)


def test_shared_http_budget_and_seed_scope(tmp_path: Path) -> None:
    total = HttpBudget(2)
    resource = ResourceBudget(10, http_budget=total)
    assert total.consume() and resource.consume("document")
    assert not total.consume() and not resource.consume("document")
    spider = TypedResourceSpider("http://127.0.0.1:8000/", [], ResourceBudget(3), 3, 64000)
    assert spider.seed_external("http://127.0.0.1:8000/item/1")
    assert not spider.seed_external("http://127.0.0.1:8000/item/1")
    assert not spider.seed_external("http://outside.test/item/1")
    assert not spider.seed_external("http://127.0.0.1:8000/item?secret=x")
    config = RunConfig(start_url="http://127.0.0.1:8000/", output_dir=tmp_path, max_total_http_requests=10)
    explorer = Explorer(config, Path.cwd())
    explorer.http_budget.used = 7
    explorer.save_checkpoint()
    resumed = Explorer(config, Path.cwd())
    resumed._load_checkpoint(tmp_path / "checkpoint.json")
    assert resumed.http_budget.used == 7


def test_area_tour_keeps_contexts_separate_and_visits_other_areas() -> None:
    def obs(identifier: str, url: str, session: str) -> Observation:
        return Observation.model_construct(id=identifier, url=url, session_context=session, session_markers={}, group_signature=identifier)
    def item(source: str, signature: str) -> FrontierItem:
        action = ActionDescriptor.model_construct(signature=signature)
        return FrontierItem.model_construct(source_observation_id=source, expected_source_group=source, path=[], action=action, priority=0.0)
    a, b, other = obs("a", "http://127.0.0.1/a/1", "anon"), obs("b", "http://127.0.0.1/b/1", "anon"), obs("c", "http://127.0.0.1/a/2", "other")
    assert area_key(a) != area_key(other)
    planner = AreaTourPlanner()
    frontier = [item("a", f"a{i}") for i in range(9)] + [item("b", "b")]
    seen = []
    for _ in range(10):
        index = planner.choose(frontier, {"a": a, "b": b}, a, [])
        seen.append(frontier.pop(index).source_observation_id)
    assert "b" in seen[:9]


def test_prefix_reuse_requires_matching_session_and_strict_prefix(tmp_path: Path) -> None:
    def step(signature: str) -> ActionDescriptor:
        return ActionDescriptor.model_construct(signature=signature)
    def obs(markers: dict) -> Observation:
        return Observation.model_construct(id="o", url="http://127.0.0.1/a", session_markers=markers)
    item = FrontierItem.model_construct(path=[step("a"), step("b"), step("c")], action=step("x"))
    base = dict(start_url="http://127.0.0.1:8000/", output_dir=tmp_path)
    off = Explorer(RunConfig(**base), Path.cwd())
    on = Explorer(RunConfig(**base, state_reuse="prefix"), Path.cwd())
    anon, other = obs({}), obs({"cookie_names": ["sid"]})
    assert off._reusable_live_prefix(item, anon, [step("a")], anon, True) is None
    assert on._reusable_live_prefix(item, anon, [step("a")], anon, True) == 1
    assert on._reusable_live_prefix(item, anon, [], anon, True) == 0
    assert on._reusable_live_prefix(item, anon, [step("b")], anon, True) is None
    assert on._reusable_live_prefix(item, anon, [step("a"), step("b"), step("c")], anon, True) is None
    assert on._reusable_live_prefix(item, other, [step("a")], anon, True) is None
    assert on._reusable_live_prefix(item, anon, [step("a")], anon, False) is None


def test_area_distance_matches_executor_cost_model() -> None:
    from agent1.hierarchical import _distance
    assert _distance(("a",), ("a", "b", "c")) == 4  # root reload + full path
    assert _distance(("a",), ("a", "b", "c"), prefix_reuse=True) == 2
    assert _distance(("z",), ("a", "b"), prefix_reuse=True) == 3
    assert _distance(("a", "b"), ("a", "b")) == 0
    assert _distance(("a", "b"), ("a", "c", "d"), prefix_reuse=True) == 3  # history step + suffix
    assert _distance(("a", "b"), ("a", "c", "d")) == 4
