"""Execution-grounded state and restoration: contract tests (real browser) and audit regressions."""
from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from agent1.explorer import Explorer
from agent1.live.grounded import GroundedExecutor, GroundedTourRunner
from agent1.live.ledger import ExecutionLedger, cookie_digest
from agent1.live.reachability import ReachabilityModel
from agent1.model.evidence import AffordanceEvidence, Record, RequestEvidence, Source
from agent1.model.importer import _affordance
from agent1.planner.designer import restore
from agent1.planner.interfaces import Costs, ExperimentPlan, ExperimentResult, Step
from agent1.planner.knowledge import Knowledge
from agent1.planner.questions import generate
from agent1.schema import RunConfig

ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------- audit (defect A)
def test_ingest_refuses_to_credit_a_final_observation_to_an_earlier_step():
    S = lambda i: Source(artifact="t", pointer=i)
    k = Knowledge()
    k.start([Record(id="o0", seq=0, kind="observation", source=S("o0"), obs_id="o0", url="http://x/", affordances=[])])
    a1 = AffordanceEvidence(kind="link", locator="a1", target="http://x/list")
    a2 = AffordanceEvidence(kind="link", locator="a2", target="http://x/list/7")
    plan = ExperimentPlan(steps=[Step(op="fresh"), Step(op="click", affordance=a1, replay_of="t1"),
                                 Step(op="click", affordance=a2)])
    final = Record(id="o9", seq=9, kind="observation", source=S("o9"), obs_id="o9", url="http://x/list/7", affordances=[])
    act = Record(id="a9", seq=10, kind="action", source=S("a9"), action_id="a9", source_obs="o8", result_obs="o9",
                 affordance=a2, status="observed", requests=[RequestEvidence(method="GET", url="http://x/list/7")])
    # Before the fix this silently filed o9 under the `fresh` step (empty trail, new epoch).
    with pytest.raises(ValueError, match="execution association"):
        k.ingest(plan, ExperimentResult(records=[final, act], actions=3, completed=True, live_obs="o9"), "o0")


# ------------------------------------------------------------------- harness
class Grounded:
    def __init__(self, explorer, browser, session, log, state):
        self.ex, self.browser, self.session, self.log, self.state = explorer, browser, session, log, state
        self.runner = GroundedTourRunner(explorer.config, explorer.evidence_sink)
        self.runner._artifact = explorer.artifact
        self.executor = GroundedExecutor(explorer, self.runner)
        self.runner.executor = self.executor
        explorer._navigate_start(session, "initial")
        self.live = session.observe(explorer._next_sequence())
        explorer._record_observation(self.live, [])
        self.path = []

    def pseudo(self, url):
        return self.runner.live._pseudo(url)

    def aff(self, label, disabled=False, obs=None):
        obs = obs or self.live
        pool = self.ex.evidence_sink.disabled.get(obs.id, []) if disabled else obs.controls
        a = _affordance(next(c for c in pool if c.label.startswith(label)).model_dump(mode="json"))
        return a.model_copy(update={"target": self.pseudo(a.target)})

    def run(self, steps, target=None, kind="bind_affordance"):
        self.runner.live.sync(self.ex.artifact)
        self.runner.sched.gate.observe(self.runner.live.records())
        self.runner._seen_records = {r.id for r in self.runner.live.records()}
        result, self.live, self.path = self.executor.run(self.browser, self.session, ExperimentPlan(kind=kind, steps=steps),
                                                         self.live, self.path, target)
        return result, self.runner.ledger.plan(f"p{self.executor.plans}")

    def click(self, label, **kw):
        return self.run([Step(op="click", affordance=self.aff(label))], **kw)

    def knowledge(self):
        self.runner.live.sync(self.ex.artifact)
        records = self.runner.live.records()
        k = self.runner._knowledge(records, self.ex.artifact)
        k.refresh(self.runner.live.export())
        return k

    def restoration(self, target_obs, independent=True):
        return restore(self.knowledge(), self.live.id, [target_obs], self.runner.iso, Costs(), independent=independent)

    def requests(self, path):
        return sum(1 for m, p in self.log if p == path)

    def check_contract(self):
        ledger = self.runner.ledger
        assert ledger.integrity() == []
        out = Path(tempfile.mkdtemp()) / "ledger.jsonl"
        ledger.save(out)
        assert ReachabilityModel.from_ledger(ExecutionLedger.load(out)).dump() == ReachabilityModel.from_ledger(ledger).dump()
        transitions = [e.transition_id for e in ledger.entries if e.transition_id]
        assert len(transitions) == len(set(transitions))                       # no evidence shared between steps


@contextmanager
def grounded(start="", lab="restoration"):
    if lab == "restoration":
        from development_apps.restoration_lab import start_restoration_lab
        server, url, log, state = start_restoration_lab()
    else:
        from development_apps.phase2_lab import start_phase2_lab
        server, url, log, state = start_phase2_lab()
    config = RunConfig(start_url=url + start, output_dir=Path(tempfile.mkdtemp()), policy="multidimensional",
                       exploration_mode="persistent", max_seconds=150, max_transitions=80, max_browser_actions=200,
                       settle_ms=80, action_timeout_ms=1500, allow_post_forms=False, state_aware_exploration=True,
                       max_total_http_requests=500, acg_evidence=True, exploration_policy="tours_grounded")
    explorer = Explorer(config, ROOT)
    explorer.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            with explorer._browser_session(browser) as session:
                g = Grounded(explorer, browser, session, log, state)
                yield g
                g.check_contract()
            browser.close()
    finally:
        assert explorer.http_budget.redirect_scope_violations == 0
        server.shutdown()


# ------------------------------------------------------------------- audit (defect B)
def test_trails_come_from_executed_steps_not_another_records_return_path():
    from agent1.live.shadow import ActiveTourRunner
    with grounded("items", lab="phase2") as g:
        g.click("Copper kettle"); g.click("History"); g.run([Step(op="back")])
        g.click("Linen apron"); g.click("History"); g.click("Upgrade view")
        k = g.knowledge()
        upgrade = [t for t in g.ex.artifact.transitions if t.action.label.startswith("Upgrade")][-1]
        labels = {t.id: t.action.label for t in g.ex.artifact.transitions}
        trail = [labels.get(s.action, "?") for s in k.obs[upgrade.source_observation_id].trail]
        assert "Copper kettle" not in trail and trail[-2:] == ["Linen apron", "History"]
        legacy = ActiveTourRunner(g.ex.config, g.ex.evidence_sink)
        old = legacy._knowledge(g.runner.live.records(), g.ex.artifact)
        old_trail = [labels.get(s.action, "?") for s in old.obs[upgrade.source_observation_id].trail]
        assert "Copper kettle" in old_trail                                     # the demonstrated defect


# ------------------------------------------------------------------- contract tests
def test_01_multistep_restoration_with_intermediate_observations():
    with grounded() as g:
        g.click("Records"); g.click("Quarry ledger")
        target = g.live
        g.click("Records")
        r = g.restoration(target.id)
        assert r is not None and r.kind == "fresh" and len(r.steps) == 3
        result, steps = g.run(r.steps + [Step(op="click", affordance=g.aff("Notes", obs=target))], target=target.id)
        assert result.completed and [s.outcome for s in steps] == ["succeeded"] * 4
        assert len({s.result_obs for s in steps}) == 4                         # each step its own observation
        assert steps[2].actual_record == steps[2].expected_record and steps[2].expected_record
        assert g.requests("/api/records/7302/notes") == 1 and g.requests("/api/records/7301/notes") == 0
        assert g.executor.restorations["verified"] == 1


def test_02_failed_intermediate_step_fabricates_nothing():
    with grounded("records/7301") as g:
        g.click("Edit mode")
        draft = g.aff("Save draft")
        g.click("Save draft")
        draft_action = g.ex.artifact.transitions[-1].id
        before = len(g.ex.artifact.transitions)
        result, steps = g.run([Step(op="fresh"), Step(op="click", affordance=draft, replay_of=draft_action, purpose="restore"),
                               Step(op="click", affordance=g.aff("Notes"))])
        assert [s.outcome for s in steps] == ["succeeded", "failed", "not_attempted"]
        assert steps[1].reason == "control_not_found" and steps[1].browser_actions == 0 and steps[2].result_obs is None
        assert len(g.ex.artifact.transitions) == before and g.requests("/api/records/7301/draft") == 1
        assert draft_action in ReachabilityModel.from_ledger(g.runner.ledger).blocked_actions()
        assert draft_action in g.knowledge().blocked_actions                   # never planned through again


def test_03_redirect_to_the_wrong_state_is_a_structured_failure():
    with grounded("gate") as g:
        g.click("Unlock"); g.click("Draft")
        draft = g.live
        result, steps = g.run([Step(op="fresh"), Step(op="goto", url=g.pseudo(draft.url), expect_obs=draft.id, purpose="restore"),
                               Step(op="click", affordance=g.aff("Preview", obs=draft))], target=draft.id)
        assert not result.completed and steps[1].outcome == "failed"
        assert steps[1].reason == "arrived_at_wrong_state:route" and steps[2].outcome == "not_attempted"
        assert g.requests("/api/gate/preview") == 0


def test_04_handler_change_evidence_stays_with_its_own_step():
    with grounded("records/7301") as g:
        _, first = g.click("Notes"); g.click("Edit mode"); _, second = g.click("Notes")
        net = {t.id: [e.url for e in t.network] for t in g.ex.artifact.transitions}
        assert first[0].transition_id != second[0].transition_id
        assert any("mode=view" in u for u in net[first[0].transition_id])
        assert any("mode=edit" in u for u in net[second[0].transition_id])


def test_05_disabled_control_then_enabled():
    with grounded("gate") as g:
        _, steps = g.run([Step(op="click", affordance=g.aff("Proceed", disabled=True))])
        assert steps[0].outcome == "failed" and steps[0].reason == "control_disabled" and steps[0].browser_actions == 0
        assert steps[0].stage == "attempted" and g.requests("/api/gate/proceed") == 0
        g.click("Unlock")
        result, _ = g.click("Proceed")
        assert result.completed and g.state["proceeded"] == 1


def test_06_session_reset_invalidates_prerequisites():
    with grounded("gate") as g:
        g.click("Unlock")
        enabled = g.live
        g.run([Step(op="fresh")])
        _, steps = g.run([Step(op="click", affordance=g.aff("Proceed", obs=enabled))], target=enabled.id)
        assert steps[0].outcome == "failed" and steps[0].reason == "control_disabled"   # stale state not trusted
        r = g.restoration(enabled.id)
        assert r.kind == "fresh"                                               # never "stay"/"same context"
        result, _ = g.run(r.steps + [Step(op="click", affordance=g.aff("Proceed", obs=enabled))], target=enabled.id)
        assert result.completed and g.state["proceeded"] == 1                  # prerequisite re-established, then used


def test_07_direct_url_to_the_wrong_record_fails():
    with grounded("records") as g:
        g.click("Harbor survey"); harbor = g.live
        g.run([Step(op="back")]); g.click("Quarry ledger"); quarry = g.live
        result, steps = g.run([Step(op="goto", url=g.pseudo(quarry.url), expect_obs=harbor.id, purpose="restore"),
                               Step(op="click", affordance=g.aff("Notes", obs=harbor))], target=harbor.id)
        assert steps[0].reason == "arrived_at_wrong_state:record" and steps[1].outcome == "not_attempted"
        assert g.requests("/api/records/7301/notes") == g.requests("/api/records/7302/notes") == 0


def test_08_refused_write_is_never_reproposed():
    with grounded("records/7301") as g:
        for _ in range(30):
            plan, target = g.runner.propose(g.ex.artifact, g.live.id, g.ex.artifact.metrics.browser_actions)
            if plan is None:
                break
            result, g.live, g.path = g.executor.run(g.browser, g.session, plan, g.live, g.path, target)
            g.runner.complete(result)
        assert g.state["archived"] == 1 and g.runner.repeated_blocked == 0
        refused = [p["proposal"]["question"] for p in g.runner.proposals
                   if p.get("proposal") and (p.get("executed") or {}).get("refused")]
        for q in set(refused):
            idx = [i for i, p in enumerate(g.runner.proposals) if (p.get("proposal") or {}).get("question") == q]
            first_refusal = next(i for i in idx if (g.runner.proposals[i].get("executed") or {}).get("refused"))
            assert not [i for i in idx if i > first_refusal], q


def test_09_state_changing_get_is_never_repeated():
    with grounded("counter") as g:
        assert g.click("Bump")[0].completed and g.state["bumps"] == 1
        _, steps = g.click("Bump")
        assert steps[0].outcome == "refused" and steps[0].reason == "known_state_change" and g.state["bumps"] == 1
        model = ReachabilityModel.from_ledger(g.runner.ledger)
        assert any(e.changes_state and not e.reusable(False) for e in model.edges.values())


def test_10_restoration_through_a_javascript_only_state():
    with grounded() as g:
        g.click("Tabs"); g.click("Tab B")
        panel = g.live
        g.click("Records")
        attempts = []
        for _ in range(2):
            r = g.restoration(panel.id, independent=False)
            assert r is not None
            result, steps = g.run(r.steps + [Step(op="click", affordance=g.aff("Load B data", obs=panel))],
                                  target=panel.id)
            attempts.append((r.kind, result.abort_reason))
            if result.completed:
                break
        # History back reloads the page and loses the client-only tab: that is detected, recorded and
        # not retried; the next plan reconstructs the state by replaying the tab click.
        assert result.completed and g.requests("/api/tabs/b") == 1, attempts
        assert all(a[1] is None or a[1].startswith("restoration_mismatch") for a in attempts)
        assert len({a[0] for a in attempts}) == len(attempts)


def test_11_deterministic_replay_mismatch_is_not_retried():
    with grounded() as g:
        g.click("Status")
        status = g.ex.artifact.transitions[-1]
        home = g.ex._observation_by_id(status.source_observation_id)
        result, steps = g.run([Step(op="fresh"), Step(op="click", affordance=g.aff("Status", obs=home),
                                                      replay_of=status.id)], target=home.id, kind="reproduce")
        assert steps[-1].verification_result == "mismatch"
        assert g.ex.artifact.replays[-1].status == "failed"
        g.runner._question_of[steps[-1].plan_id] = "reproduce:status"
        g.runner.propose(g.ex.artifact, g.live.id, g.ex.artifact.metrics.browser_actions)
        assert "reproduce:status" in g.runner.sched.no_reproduce


def test_12_role_and_session_identity_with_cookie_markers():
    with grounded() as g:
        g.click("Records"); g.click("Harbor survey")
        cookies = g.session.context.cookies()
        assert any(c["name"] == "sid" for c in cookies)
        sid = next(c["value"] for c in cookies if c["name"] == "sid")
        for e in g.runner.ledger.entries:
            assert e.session.role == "anonymous" and e.session.account_ref is None
        assert any(e.session.cookie_names_digest == cookie_digest(["sid"]) for e in g.runner.ledger.entries)
        out = Path(tempfile.mkdtemp()) / "l.jsonl"
        g.runner.ledger.save(out)
        assert sid not in out.read_text()
        g.runner.propose(g.ex.artifact, g.live.id, g.ex.artifact.metrics.browser_actions)
        assert g.runner.sched.st.entered_roles == {"anonymous"}
        assert not [q for q in generate(g.knowledge(), g.runner.sched.st, g.runner.iso) if q.kind == "find_entry_point"]
