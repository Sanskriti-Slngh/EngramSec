"""Small deterministic diagnostic applications for Phase 1b-R (T2R D1–D4).

Built from appsim's building blocks without modifying appsim.py or any T2
scenario. They exist because the original T2 apps can never exercise:
- a search oracle that can pass (the T2 search filters a list that is already
  fully visible, so the frozen `collection_query/1` rule cannot fire);
- write verification from a verified snapshot (T2 never made it eligible).

`solve_*` are scripted plans, independent of any scheduler, proving each
expected outcome is reachable through the shared adapter and materializer.
"""
from __future__ import annotations

from agent1.model.evidence import Record
from agent1.model.materialize import materialize
from agent1.planner.gate import RiskGate
from agent1.planner.interfaces import ExperimentPlan, Isolation, Step

from evaluation.appsim import AppSpec, SimAdapter, _Builder, _static

DIAGNOSTICS = ("diag_search", "diag_snapshot", "diag_snapshot_drift", "diag_snapshot_absent")


def build(arch: str, seed: int, **kw) -> AppSpec:
    b = _Builder(arch, seed)
    if arch == "diag_search":
        hub, w = b.hub("a1")
        ent = b.entity(12)
        detail = b.page("detail_a1", f"/{w}/{{id}}", "a1", entity=ent).key
        s = b.word()
        results = b.page("results_a1", f"/{w}/{s}", "a1", results_of=ent).key
        b.control(hub, b.cap("a1", "collection_query"), "form_submit", "main>form", effect="search",
                  op=("GET", f"/{w}/{s}", ("q",), None, "document"), fields=(("q", "search", False),), target=results)
        b.control(results, b.cap("a1", "instance_view"), "link", "main>ul", per_instance=ent, target=detail,
                  effect="navigate")
        b.control(detail, b.cap("a1", "fetch"), "button", "main", op=("GET", f"/api/{w}/{{id}}/{b.word()}", (), None,
                                                                       "fetch"), effect="fetch")
        _static(b, "a2", 1, 2)
        b.spec.isolation = Isolation(level=2, exploratory_writes=True, roles=["anonymous"], start_url="/")
    else:
        hub, w = b.hub("a1")
        ent = b.entity(3)
        detail = b.page("detail_a1", f"/{w}/{{id}}", "a1", entity=ent).key
        b.control(hub, b.cap("a1", "instance_view"), "link", "main>ul", per_instance=ent, target=detail,
                  effect="navigate")
        b.control(detail, b.nav_caps[hub], "link", "header", target=hub, effect="navigate")
        b.control(detail, b.cap("a1", "instance_creation", writes=True), "form_submit", "main>section",
                  op=("POST", f"/{w}/{b.word()}", ("name",), "form", "document"), effect="create",
                  fields=(("name", "text", True),), target=detail)
        _static(b, "a2", 1, 2)
        if arch == "diag_snapshot_absent":
            b.spec.isolation = Isolation(level=2, exploratory_writes=True, roles=["anonymous"], start_url="/")
        else:
            b.spec.isolation = Isolation(level=3, exploratory_writes=True, snapshot=True, roles=["anonymous"],
                                         start_url="/")
            b.spec.snapshot_drift = arch == "diag_snapshot_drift"
    return b.finish()


def _exec(adapter: SimAdapter, gate: RiskGate, records: list[Record], plan: ExperimentPlan):
    result = adapter.run(plan, 1000, gate, records)
    records.extend(result.records)
    gate.observe(records)
    return result


def _click(records: list[Record], pred) -> Step:
    live = [r for r in records if r.kind == "observation"][-1]
    return Step(op="click", affordance=next(a for a in live.affordances if pred(a)))


def solve_search(seed: int) -> list[Record]:
    adapter = SimAdapter(build("diag_search", seed))
    records = adapter.start()
    gate = RiskGate(adapter.isolation)
    nav = _click(records, lambda a: a.component == "nav")
    nav_act = _exec(adapter, gate, records, ExperimentPlan(steps=[nav])).action_ids[0]
    hub_url = [r for r in records if r.kind == "observation"][-1].url
    form = _click(records, lambda a: a.kind == "form_submit")
    search_act = _exec(adapter, gate, records, ExperimentPlan(steps=[form])).action_ids[0]
    for _ in range(2):
        steps = [Step(op="fresh"), nav.model_copy(update={"replay_of": nav_act}),
                 form.model_copy(update={"replay_of": search_act, "input": "primary", "oracle_capture": "before_after"}),
                 Step(op="goto", url=hub_url),
                 form.model_copy(update={"replay_of": search_act, "input": "contrast", "oracle_capture": "before_after"})]
        _exec(adapter, gate, records, ExperimentPlan(steps=steps, oracle="paired_search", oracle_action=search_act))
    return records


def solve_snapshot(seed: int, arch: str = "diag_snapshot") -> tuple[list[Record], object]:
    adapter = SimAdapter(build(arch, seed))
    records = adapter.start()
    gate = RiskGate(adapter.isolation)
    nav = _click(records, lambda a: a.component == "nav")
    nav_act = _exec(adapter, gate, records, ExperimentPlan(steps=[nav])).action_ids[0]
    hub_url = [r for r in records if r.kind == "observation"][-1].url
    row = _click(records, lambda a: a.target and a.component.startswith("main>ul"))
    row_act = _exec(adapter, gate, records, ExperimentPlan(steps=[row])).action_ids[0]
    form = _click(records, lambda a: a.kind == "form_submit")
    create_act = _exec(adapter, gate, records, ExperimentPlan(steps=[form])).action_ids[0]
    steps = [Step(op="snapshot"), nav.model_copy(update={"replay_of": nav_act}),
             row.model_copy(update={"replay_of": row_act}),
             form.model_copy(update={"replay_of": create_act, "oracle_capture": "after"}),
             Step(op="goto", url=hub_url, oracle_capture="after")]
    result = _exec(adapter, gate, records, ExperimentPlan(steps=steps, oracle="cross_view", oracle_action=create_act))
    return records, result


def verified_classes(records: list[Record]) -> set[str]:
    return {c.behavioral_class.name for c in materialize(records).capabilities
            if c.behavioral_class and str(c.status) == "verified"}
