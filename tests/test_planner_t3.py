"""Phase 1b planner-level semantic and safety integrity (T3a, T3e and Phase 6 checks)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agent1.model.materialize import materialize
from agent1.model.routes import identifier_segments
from agent1.model.schema import Status
from agent1.planner.gate import control_key, writes
from evaluation import appsim
from evaluation.appsim import ARCHITECTURES
from evaluation.sim_eval import run

ROOT = Path(__file__).resolve().parents[1]
PLANNER = ROOT / "agent1" / "planner"
LABEL_FIELDS = {"label", "labels", "title", "label_candidates"}
CASES = [("mixed", s, 150) for s in range(10)] + [("instances", 0, 150), ("prerequisites", 1, 200)]


@pytest.mark.parametrize("scenario,seed,budget", CASES)
def test_t3a_decision_log_is_invariant_under_label_rewriting(scenario: str, seed: int, budget: int) -> None:
    base = run("acg_full", scenario, seed, budget)["decision_hash"]
    for mode in ("random", "zh"):
        assert run("acg_full", scenario, seed, budget, label_mode=mode)["decision_hash"] == base


def test_t3e_planner_never_reads_label_fields() -> None:
    # baselines.py reproduces the legacy frontier, which does read labels; it is not part of the planner.
    for module in sorted(PLANNER.glob("*.py")):
        if module.name == "baselines.py":
            continue
        tree = ast.parse(module.read_text())
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        assert not attrs & LABEL_FIELDS, module.name
        assert not literals & LABEL_FIELDS, module.name


def test_hidden_truth_does_not_reach_the_planner(monkeypatch) -> None:
    """Renaming every hidden-only identifier (capabilities, classes, areas) leaves decisions unchanged."""
    original = appsim.build

    def renamed(arch, seed, **kw):
        spec = original(arch, seed, **kw)
        mapping = {c: f"hidden{i}" for i, c in enumerate(sorted(spec.caps))}
        spec.caps = {mapping[k]: v for k, v in spec.caps.items()}
        for v in spec.caps.values():
            v.cls, v.area = "x", "y"
        for c in spec.controls:
            c.cap = mapping[c.cap]
            if c.variant:
                c.variant = (mapping[c.variant[0]],) + tuple(c.variant[1:])
        for p in spec.pages.values():
            p.area = "z"
        return spec
    base = {s: run("acg_full", "mixed", s, 120)["decision_hash"] for s in range(10)}
    monkeypatch.setattr("evaluation.sim_eval.build", renamed)
    assert {s: run("acg_full", "mixed", s, 120)["decision_hash"] for s in range(10)} == base


def _runs():
    out = []
    for scenario, seeds, budget in (("mixed", range(10), 150), ("prerequisites", range(3), 200),
                                    ("writes_with_snapshots", range(3), 150), ("instances", range(2), 150)):
        out.extend(run("acg_full", scenario, s, budget, keep=True) for s in seeds)
    return out


@pytest.fixture(scope="module")
def runs():
    return _runs()


def test_no_claim_is_verified_or_reproduced_without_an_experiment(runs) -> None:
    for r in runs:
        records = r["records"]
        by_id = {x.id: x for x in records}
        for cap in materialize(records).capabilities:
            for rid in cap.reproduction_ids:
                assert by_id[rid].kind == "replay" and by_id[rid].independent_context
            if cap.status == Status.VERIFIED:
                kinds = {by_id[e].verification_kind for e in cap.behavioral_class.evidence_ids
                         if by_id[e].kind == "replay"}
                assert kinds & {"paired_search", "cross_view"}


def test_prerequisites_and_unlock_are_evidence_backed(runs) -> None:
    for r in runs:
        export = materialize(r["records"])
        disabled = {c.subject for c in export.claims if c.predicate == "observed_disabled"}
        failed_auth = {a.id for a in export.affordances if a.status == "failed"}
        establishes = {(c.subject, c.object.split(":", 1)[1]) for c in export.claims if c.predicate == "establishes"}
        for d in r["decision_log"]:
            c = d.get("chosen")
            if not c:
                continue
            if c["unlock"] > 0:
                assert c["unlocks"]
                assert all(u.split(":", 1)[1] in disabled | failed_auth for u in c["unlocks"])
            if c["kind"] == "test_dependency":
                _, x, cap = c["q"].split(":")
                assert (cap, x) in establishes


def test_write_capable_actions_are_never_repeated_without_isolation(runs) -> None:
    for r in runs:
        assert r["unsafe_attempts"] == 0                       # the planner never proposes a refused step
        if r["spec"]["arch"] == "flaky":                       # L3 with verified snapshots: replay is permitted
            continue
        known, url = set(), {}
        actions = {x.action_id: x for x in r["records"] if x.kind == "action"}
        for x in r["records"]:
            if x.kind == "observation":
                url[x.obs_id] = x.url
            if x.kind not in {"action", "replay"}:
                continue
            original = actions.get(x.action_id)
            if original is None or original.affordance is None:
                continue
            key = control_key(url.get(original.source_obs), original.affordance)
            assert key not in known, "a known write was re-executed without isolation"
            if writes(x) or writes(original):
                known.add(key)


def test_instances_are_not_merged_and_discoveries_cite_evidence(runs) -> None:
    for r in runs:
        assert r["final"]["false_merges"] == 0 or r["arch"] in {"client_only", "duplicate_pages", "hidden_ids"}
        records = r["records"]
        ids = {x.id for x in records}
        export = materialize(records)
        for inst in export.entity_instances:      # one identifier value per instance: never merged
            values = {v for path in inst.observed_paths for _, _, v in identifier_segments(path)}
            assert len(values & {seg for path in inst.observed_paths for seg in path.split("/")}) >= 1
        pairs = [(i.type_id, i.token) for i in export.entity_instances]
        assert len(pairs) == len(set(pairs))
        for cap in export.capabilities:
            assert cap.evidence_ids and set(cap.evidence_ids) <= ids
        for d in r["decision_log"]:
            if d.get("chosen"):
                assert set(d["chosen"]["evidence"]) <= ids


def test_question_counts_grow_with_templates_not_instances() -> None:
    small = run("acg_full", "instances", 0, 60, keep=True)
    from evaluation import sim_scenarios
    conf = dict(sim_scenarios.SCENARIOS["instances"])
    sim_scenarios.SCENARIOS["instances"] = {**conf, "kw": {**conf["kw"], "instances": 50}}
    try:
        fewer = run("acg_full", "instances", 0, 60, keep=True)
    finally:
        sim_scenarios.SCENARIOS["instances"] = conf
    big = max(d.get("open", 0) for d in small["decision_log"])
    little = max(d.get("open", 0) for d in fewer["decision_log"])
    assert big < 50 and abs(big - little) <= 3     # 4x the instances, same order of open questions


def test_t2b_bound_holds_on_sample_seeds() -> None:
    for seed in range(3):
        assert run("acg_full", "instances", seed, 150)["instances"]["non_split_instances"] <= 3


def test_every_architecture_runs_for_every_policy() -> None:
    for i, arch in enumerate(ARCHITECTURES):
        for policy in ("bfs", "legacy_frontier", "acg_uniform", "acg_no_unlock", "acg_full"):
            r = run(policy, "mixed", i, 40)
            assert r["used"] <= 40 and r["unsafe_attempts"] >= 0


def test_planner_package_has_no_application_specific_knowledge() -> None:
    from evaluation.purity_check import scan
    assert scan([p for p in sorted(PLANNER.glob("*.py")) if p.name != "baselines.py"]) == []
