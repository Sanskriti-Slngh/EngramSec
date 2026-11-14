"""Capability Tour Scheduler: integrity, safety and invariance (Phase 1b-R, Phase 8)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import evaluation.sim_eval as se
from agent1.model.materialize import materialize
from agent1.model.schema import Status
from agent1.planner.tours import TOUR
from evaluation import appsim, t2r_eval
from evaluation.purity_check import scan

ROOT = Path(__file__).resolve().parents[1]
TOURS = ROOT / "agent1" / "planner" / "tours.py"
DEV = [("mixed", s, 150) for s in range(10)] + [("prerequisites", 0, 200), ("instances", 1, 150), ("flat", 2, 100)]


@pytest.fixture(autouse=True)
def _wired():
    t2r_eval.install()


@pytest.mark.parametrize("scenario,seed,budget", DEV)
def test_decisions_are_label_invariant_and_deterministic(scenario, seed, budget) -> None:
    hashes = {se.run("tour_full", scenario, seed, budget, label_mode=m)["decision_hash"]
              for m in (None, "random", "zh", None)}
    assert len(hashes) == 1


def test_scheduler_reads_no_labels_and_uses_none_of_the_failed_machinery() -> None:
    tree = ast.parse(TOURS.read_text())
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | attrs
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert not attrs & {"label", "labels", "title", "label_candidates"}
    assert not (names | imported) & {"binary_eig", "bind_distribution", "kl_bernoulli", "hb", "Allocator",
                                     "LAMBDA_UNLOCK", "DUCB_C", "DUCB_GAMMA", "eps", "family_allows_gt"}
    assert scan([TOURS]) == []


def test_hidden_truth_does_not_reach_the_scheduler(monkeypatch) -> None:
    def renamed(arch, seed, **kw):
        spec = appsim.build(arch, seed, **kw)
        mapping = {c: f"h{i}" for i, c in enumerate(sorted(spec.caps))}
        spec.caps = {mapping[k]: v for k, v in spec.caps.items()}
        for c in spec.controls:
            c.cap = mapping[c.cap]
            if c.variant:
                c.variant = (mapping[c.variant[0]],) + tuple(c.variant[1:])
        for p in spec.pages.values():
            p.area = "z"
        return spec
    base = {s: se.run("tour_full", "mixed", s, 120)["decision_hash"] for s in range(10)}
    monkeypatch.setattr(se, "build", renamed)
    assert {s: se.run("tour_full", "mixed", s, 120)["decision_hash"] for s in range(10)} == base


@pytest.fixture(scope="module")
def runs():
    t2r_eval.install()
    out = []
    for scenario, seeds, budget in (("mixed", range(10), 150), ("prerequisites", range(3), 200),
                                    ("instances", range(2), 150), ("diag:snapshot", range(2), 80),
                                    ("diag:snapshot_drift", range(2), 80), ("diag:snapshot_absent", range(2), 80),
                                    ("diag:search", range(2), 80)):
        for s in seeds:
            out.append(se.run("tour_full", scenario, s, budget, keep=True))
    return out


def test_every_question_cites_evidence_and_no_unsafe_control_is_clicked(runs) -> None:
    for r in runs:
        assert r["unsafe_attempts"] == 0
        ids = {x.id for x in r["records"]}
        for d in r["decision_log"]:
            c = d.get("chosen")
            if c and c["kind"] != "find_entry_point":         # role entry points cite the adapter declaration
                assert c["evidence"] and set(c["evidence"]) <= ids
        actions = {x.action_id: x for x in r["records"] if x.kind == "action"}
        for x in r["records"]:
            if x.kind == "action":
                assert x.affordance.safe and not x.affordance.disabled
            if x.kind == "replay" and x.action_id in actions:
                assert actions[x.action_id].affordance.safe


def test_no_verification_without_an_oracle_and_writes_need_verified_isolation(runs) -> None:
    for r in runs:
        records = r["records"]
        by_id = {x.id: x for x in records}
        for cap in materialize(records).capabilities:
            for rid in cap.reproduction_ids:
                assert by_id[rid].kind == "replay" and by_id[rid].independent_context
            if cap.status == Status.VERIFIED:
                kinds = {by_id[e].verification_kind for e in cap.behavioral_class.evidence_ids if by_id[e].kind == "replay"}
                assert kinds & {"paired_search", "cross_view"}
        if r["arch"] not in {"flaky", "diag_snapshot"}:
            assert t2r_eval._write_reexecutions(records) == 0


def test_chain_records_are_complete_and_tours_bounded(runs) -> None:
    for r in runs:
        if r["scenario"] != "prerequisites":
            continue
        sel_runs = []
        t2r_eval.install()
        se.run("tour_full", "prerequisites", r["seed"], 200)
        sched = t2r_eval._LAST[0].inner
        sel_runs.append(sched)
        ids = {x.id: x for x in r["records"]}
        for c in sched.chains.values():
            assert c["disabled_obs"] in ids and c["enabled_obs"] in ids and c["to_verify"]
            assert "candidate_claim" in c and "executed" in c
        chain_budget = len(sched.chains)
        for t in sched.tours + ([sched.tour] if sched.tour else []):
            assert t["length"] <= TOUR["max_length"] + chain_budget


def test_question_counts_do_not_grow_with_instances() -> None:
    from evaluation import sim_scenarios
    small = se.run("tour_full", "instances", 0, 60, keep=True)
    conf = dict(sim_scenarios.SCENARIOS["instances"])
    sim_scenarios.SCENARIOS["instances"] = {**conf, "kw": {**conf["kw"], "instances": 50}}
    try:
        fewer = se.run("tour_full", "instances", 0, 60, keep=True)
    finally:
        sim_scenarios.SCENARIOS["instances"] = conf
    a = max(d.get("open_discovery", 0) for d in small["decision_log"])
    b = max(d.get("open_discovery", 0) for d in fewer["decision_log"])
    assert a < 50 and abs(a - b) <= 3
    assert small["instances"]["non_split_instances"] <= 3
