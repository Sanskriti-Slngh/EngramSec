"""Phase 1b evaluation foundation: simulator, shared executor, risk gate, baselines, scoring."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from agent1.model.evidence import AffordanceEvidence, Record, Source
from agent1.model.materialize import materialize
from agent1.planner.gate import RiskGate
from agent1.planner.interfaces import ExperimentPlan, Isolation, Step
from evaluation.appsim import ARCHITECTURES, SimAdapter, build, relabel
from evaluation.sim_eval import run
from evaluation.sim_scenarios import SCENARIOS, T2

ROOT = Path(__file__).resolve().parents[1]


def _walk(arch: str, seed: int, n: int = 25) -> list[Record]:
    spec = build(arch, seed)
    adapter = SimAdapter(spec)
    records = adapter.start()
    gate = RiskGate(adapter.isolation)
    gate.observe(records)
    for i in range(n):
        live = [r for r in records if r.kind == "observation"][-1]
        affs = [a for a in live.affordances or [] if a.safe and not a.disabled]
        step = Step(op="click", affordance=affs[i % len(affs)]) if affs and i % 5 else Step(op="goto", url="/")
        result = adapter.run(ExperimentPlan(steps=[step]), 100, gate, records)
        records.extend(result.records)
        gate.observe(records)
    return records


def test_simulator_is_deterministic_for_every_architecture() -> None:
    for arch in ARCHITECTURES:
        a, b = _walk(arch, 3), _walk(arch, 3)
        assert [r.model_dump() for r in a] == [r.model_dump() for r in b], arch
        assert build(arch, 3).summary() == build(arch, 3).summary()


def test_evidence_never_carries_hidden_truth() -> None:
    for arch in ARCHITECTURES:
        spec = build(arch, 5)
        text = json.dumps([r.model_dump(mode="json") for r in _walk(arch, 5)])
        assert not any(cap in text for cap in spec.caps), arch            # capability ids like "c3:fetch"
        assert not any(f'"{c.key}"' in text for c in spec.controls), arch  # control keys
        assert "hub_" not in text and "detail_" not in text and "never_enabled" not in text


def test_adapter_exposes_only_evidence_and_declarations() -> None:
    public = {n for n in dir(SimAdapter(build("crud", 0))) if not n.startswith("_")}
    assert public == {"costs", "isolation", "oracle", "run", "start"}


def test_planner_package_never_imports_the_simulator_or_evaluation() -> None:
    for module in sorted((ROOT / "agent1" / "planner").glob("*.py")):
        tree = ast.parse(module.read_text())
        names = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        names |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any(x.startswith("evaluation") for x in names), module.name


def test_gate_refuses_unsafe_disabled_and_known_writes() -> None:
    gate = RiskGate(Isolation(level=2, exploratory_writes=True))
    unsafe = AffordanceEvidence(kind="button", locator="b", safe=False, skip_reason="destructive_possible")
    assert gate.check(Step(op="click", affordance=unsafe), "http://x/", False) == "unsafe:destructive_possible"
    assert gate.check(Step(op="click", affordance=AffordanceEvidence(kind="button", locator="b", disabled=True)),
                      "http://x/", False) == "disabled"
    form = AffordanceEvidence(kind="form_submit", locator="f", method="POST", target="http://x/new")
    assert RiskGate(Isolation(level=0)).check(Step(op="click", affordance=form), "http://x/", False) == \
        "exploratory_write_not_permitted"
    from agent1.model.evidence import RequestEvidence
    records = [Record(id="o", seq=1, kind="observation", source=Source(artifact="t", pointer="o"), obs_id="o1",
                      url="http://x/"),
               Record(id="a", seq=2, kind="action", source=Source(artifact="t", pointer="a"), action_id="a1",
                      source_obs="o1", affordance=form, status="observed",
                      requests=[RequestEvidence(method="POST", url="http://x/new")])]
    gate.observe(records)
    assert gate.check(Step(op="click", affordance=form), "http://x/", False) == "known_write_not_replayable"
    l3 = RiskGate(Isolation(level=3, exploratory_writes=True, snapshot=True))
    l3.observe(records)
    assert l3.check(Step(op="click", affordance=form), "http://x/", True) is None
    assert l3.check(Step(op="click", affordance=form), "http://x/", False) == "known_write_not_replayable"


def test_snapshot_restore_requires_a_verified_start_state() -> None:
    for drift, expected in ((False, None), (True, "unverified_start_state")):
        adapter = SimAdapter(build("flaky", 1, flaky=0.0, snapshot_drift=drift))
        records = adapter.start()
        gate = RiskGate(adapter.isolation)
        result = adapter.run(ExperimentPlan(steps=[Step(op="snapshot")]), 10, gate, records)
        assert result.abort_reason == expected


def test_disabled_controls_yield_evidence_backed_condition_claims() -> None:
    records = _walk("workflow", 2, 40)
    export = materialize(records)
    preds = {c.predicate for c in export.claims}
    assert "observed_disabled" in preds and "establishes" in preds
    for c in export.claims:
        if c.predicate == "establishes":
            kinds = {r.split(":")[1] for r in c.evidence_ids}
            assert {"act", "obs"} <= kinds and c.rule == "enablement/1"


def test_relabel_changes_only_display_text() -> None:
    a, b = build("crud", 4), relabel(build("crud", 4), "zh")
    assert [c.label for c in a.controls] != [c.label for c in b.controls]
    strip = lambda s: [(c.key, c.page, c.cap, c.locator, c.op, c.target) for c in s.controls]
    assert strip(a) == strip(b)


def test_baselines_are_deterministic_and_scored_identically() -> None:
    for policy in ("bfs", "legacy_frontier"):
        r1, r2 = run(policy, "mixed", 2, 60), run(policy, "mixed", 2, 60)
        assert r1["decision_hash"] == r2["decision_hash"] and r1["final"] == r2["final"]
        assert 0 <= r1["final"]["recall"] <= 1 and r1["used"] <= 60


def test_t2_preregistration_matches_design_thresholds() -> None:
    assert T2["T2a"]["tolerance"] == 0.10 and T2["T2a"]["min_bin"] == 30
    assert T2["T2b"]["max_sampled_instances"] == 3
    assert T2["T2c"]["budgets"] == [100, 200, 400] and T2["T2c"]["min_seed_fraction"] == 0.80
    assert T2["T2d"]["min_ratio"] == 0.95
    assert SCENARIOS["instances"]["kw"]["instances"] == 200
    spec = build("large_list", 0, **SCENARIOS["instances"]["kw"])
    assert spec.summary()["observable_capabilities"] == 11      # 1 instance template + 10 others
