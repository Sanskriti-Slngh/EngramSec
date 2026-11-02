"""Phase 3: deterministic real-browser tests of the tour executor adapter (before any A/B)."""
from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from agent1.explorer import Explorer
from agent1.live.executor import TourExecutor
from agent1.live.shadow import ActiveTourRunner
from agent1.model.importer import _affordance
from agent1.planner.interfaces import ExperimentPlan, Step
from agent1.schema import RunConfig
from development_apps.phase2_lab import start_phase2_lab

ROOT = Path(__file__).resolve().parents[1]


class Harness:
    def __init__(self, explorer, browser, session, log, state):
        self.ex, self.browser, self.session, self.log, self.state = explorer, browser, session, log, state
        self.runner = ActiveTourRunner(explorer.config, explorer.evidence_sink)
        self.runner._artifact = explorer.artifact
        self.executor = TourExecutor(explorer, self.runner)
        explorer._navigate_start(session, "initial")
        self.live = session.observe(explorer._next_sequence())
        explorer._record_observation(self.live, [])
        self.path = []

    def aff(self, label: str, disabled: bool = False):
        pool = self.ex.evidence_sink.disabled.get(self.live.id, []) if disabled else self.live.controls
        control = next(c for c in pool if c.label.startswith(label))
        a = _affordance(control.model_dump(mode="json"))
        return a.model_copy(update={"target": self.runner.live._pseudo(a.target)})

    def run(self, steps, target=None, kind="bind_affordance"):
        self.runner.live.sync(self.ex.artifact)
        self.runner.sched.gate.observe(self.runner.live.records())
        self.runner._seen_records = {r.id for r in self.runner.live.records()}
        result, self.live, self.path = self.executor.run(self.browser, self.session, ExperimentPlan(kind=kind, steps=steps),
                                                         self.live, self.path, target)
        return result

    def click(self, label, **kw):
        return self.run([Step(op="click", affordance=self.aff(label))], **kw)

    def posts(self, path):
        return sum(1 for m, p in self.log if m == "POST" and p == path)


@contextmanager
def harness(start: str = "", lab: str = "phase2"):
    if lab == "phase2":
        server, url, log, state = start_phase2_lab()
    else:
        from development_apps.stateful_lab import start_stateful_lab
        server, url, _, log = start_stateful_lab(Path(tempfile.mkdtemp()) / "lab.sqlite")
        state = {}
    config = RunConfig(start_url=url + start, output_dir=Path(tempfile.mkdtemp()), policy="multidimensional",
                       exploration_mode="persistent", max_seconds=120, max_transitions=60, max_browser_actions=150,
                       settle_ms=80, action_timeout_ms=1500, allow_post_forms=False, state_aware_exploration=True,
                       max_total_http_requests=400, acg_evidence=True, exploration_policy="tours")
    explorer = Explorer(config, ROOT)
    explorer.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            with explorer._browser_session(browser) as session:
                yield Harness(explorer, browser, session, log, state)
            browser.close()
    finally:
        assert explorer.http_budget.redirect_scope_violations == 0
        server.shutdown()


def test_replaced_handler_and_dynamic_controls_are_resolved_live():
    with harness("items/48213") as h:
        assert h.click("History").completed
        assert h.click("Upgrade view").completed
        compare = h.aff("Compare")                                         # created by the previous action
        assert h.run([Step(op="click", affordance=compare)]).completed
        assert h.click("History").completed
        h.run([Step(op="fresh"), Step(op="goto", url=h.runner.live._pseudo(h.live.url))])
        gone = h.run([Step(op="click", affordance=compare)])               # page reloaded: control not created
        assert gone.abort_reason == "control_not_found" and gone.actions == 0
        history = [t for t in h.ex.artifact.transitions if t.action.label.startswith("History")]
        assert [e.url.split("mode=")[-1] for t in history for e in t.network] == ["a", "b"]  # new handler attributed


def test_disabled_control_session_workflow_and_session_reset():
    with harness("setup") as h:
        result = h.run([Step(op="click", affordance=h.aff("Continue", disabled=True))])
        assert result.abort_reason == "control_disabled" and result.actions == 0
        assert h.click("Accept terms").completed and h.click("Continue").completed
        assert h.click("Review").completed and h.click("Finish setup").completed
        assert h.state.get("setup_finished") == 1                         # chain completed in one session
        before = len(h.log)
        h.run([Step(op="fresh"), Step(op="goto", url=h.runner.live._pseudo(h.live.url))])
        result = h.run([Step(op="click", affordance=h.aff("Finish setup", disabled=True))])
        assert result.abort_reason == "control_disabled"                   # the reset destroyed the prerequisite
        assert h.state.get("setup_finished") == 1 and not any(p == "/api/setup/finish" for _, p in h.log[before:])


def test_two_records_and_restoration_to_the_wrong_record():
    with harness("items") as h:
        assert h.click("Copper kettle").completed
        kettle = h.live.id
        assert h.run([Step(op="back")]).completed and h.click("Linen apron").completed
        apron_history = h.aff("History")
        result = h.run([Step(op="click", affordance=apron_history)], target=kettle)
        assert result.abort_reason == "record_identity_mismatch" and result.actions == 0
        assert not any("history" in p for _, p in h.log)
        assert h.run([Step(op="click", affordance=apron_history)], target=h.live.id).completed
        assert any(p == "/api/items/48217/history" for _, p in h.log)       # the intended record only


def test_javascript_form_post_is_never_repeated():
    with harness("notes") as h:
        assert h.click("Add note").completed and h.posts("/api/notes") == 1
        again = h.click("Add note")
        assert not again.completed and h.posts("/api/notes") == 1          # known write: refused, not replayed


def test_unsafe_control_is_never_executed():
    with harness(lab="stateful") as h:
        unsafe = [c for c in h.live.controls if not c.safe]
        assert unsafe
        a = _affordance(unsafe[0].model_dump(mode="json"))
        result = h.run([Step(op="click", affordance=a.model_copy(update={"target": h.runner.live._pseudo(a.target)}))])
        assert result.abort_reason == "control_unsafe" and result.actions == 0
        assert h.posts("/api/delete") == 0


def test_unsupported_operations_are_refused_not_approximated():
    with harness() as h:
        for steps in ([Step(op="snapshot")], [Step(op="fresh", role="administrator")]):
            result = h.run(steps)
            assert result.abort_reason.startswith("unsupported_operation") and result.actions == 0
        result = h.run([Step(op="click", affordance=h.aff("Search"), input="primary")])
        assert result.abort_reason == "unsupported_input_variant" and result.actions == 0


def test_legacy_arm_instrumentation_is_behavior_preserving():
    import re
    from development_apps.stateful_lab import start_stateful_lab
    host = re.compile(r"127\.0\.0\.1:\d+")
    runs = []
    for extra in ({}, {"acg_evidence": True, "action_ledger": True}):
        server, url, _, log = start_stateful_lab(Path(tempfile.mkdtemp()) / "lab.sqlite")
        try:
            out = Path(tempfile.mkdtemp())
            explorer = Explorer(RunConfig(start_url=url, output_dir=out, policy="multidimensional",
                                          exploration_mode="persistent", max_seconds=35, max_transitions=30,
                                          max_browser_actions=100, settle_ms=60, action_timeout_ms=1500,
                                          allow_post_forms=True, replay_policy="structure",
                                          state_aware_exploration=True, **extra), ROOT)
            artifact = explorer.run()
            runs.append(([(t.action.css_path, host.sub("H", t.action.target or ""),
                           [(e.method, host.sub("H", e.url)) for e in t.network]) for t in artifact.transitions],
                         sorted(m + p for m, p in log if m == "POST")))
            if extra:
                assert (out / "action_ledger.json").exists() and explorer.action_ledger
        finally:
            server.shutdown()
    assert runs[0] == runs[1]
