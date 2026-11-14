"""Real-browser contract tests of the capability-aware hybrid (development fixture only).

One legacy run and one hybrid run on `development_apps/hybrid_lab.py` with the
same budget; assertions use the server log, the execution ledger, the ACG and
the hybrid decision log.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from agent1.explorer import Explorer
from agent1.live.acg import LiveACG
from agent1.live.ledger import ExecutionLedger
from agent1.model.routes import path_route
from agent1.schema import RunConfig
from development_apps.hybrid_lab import start_hybrid_lab

ROOT = Path(__file__).resolve().parents[1]
CONFIG = dict(policy="coverage", exploration_mode="persistent", max_seconds=45, max_transitions=40,
              max_browser_actions=120, settle_ms=60, action_timeout_ms=1500, allow_post_forms=True,
              replay_policy="structure", state_aware_exploration=True, acg_evidence=True)


def _run(tmp: Path, arm: str) -> dict:
    server, url, log, state = start_hybrid_lab()
    try:
        extra = {"exploration_policy": "hybrid_capabilities"} if arm == "hybrid" else {}
        explorer = Explorer(RunConfig(start_url=url, output_dir=tmp / arm, **CONFIG, **extra), ROOT)
        artifact = explorer.run()
    finally:
        server.shutdown()
    return {"explorer": explorer, "artifact": artifact, "log": list(log), "state": dict(state), "out": tmp / arm}


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("hybrid")
    return {"legacy": _run(tmp, "legacy"), "hybrid": _run(tmp, "hybrid")}


def _patterns(log) -> set[str]:
    return {f"{m} {path_route(p)}" for m, p in log}


def _decisions(out: Path) -> list[dict]:
    return [json.loads(x) for x in (out / "hybrid_decisions.jsonl").read_text().splitlines() if x.strip()]


def test_default_legacy_run_is_unchanged(runs):
    legacy = runs["legacy"]
    assert legacy["explorer"].hybrid is None and legacy["explorer"].hybrid_summary is None
    assert not (legacy["out"] / "hybrid_decisions.jsonl").exists()
    assert "exploration_policy" not in legacy["artifact"].config


def test_ledger_has_one_grounded_entry_per_step(runs):
    h = runs["hybrid"]
    summary = h["explorer"].hybrid_summary
    assert summary["ledger_integrity"] == []
    ledger = ExecutionLedger.load(h["out"] / "execution_ledger.jsonl")
    by_transition = Counter(e.transition_id for e in ledger.entries if e.transition_id)
    assert set(by_transition) == {t.id for t in h["artifact"].transitions}
    assert set(by_transition.values()) == {1}
    replays = Counter(e.replay_id for e in ledger.entries if e.replay_id)
    assert set(replays) == {r.id for r in h["artifact"].replays} and set(replays.values()) == {1}
    for e in ledger.entries:
        if e.outcome == "succeeded" and e.purpose == "discovery":
            t = next(t for t in h["artifact"].transitions if t.id == e.transition_id)
            assert e.result_obs == t.result_observation_id         # its own observation, never a later one


def test_distinct_behaviors_preserved_while_redundant_navigation_drops(runs):
    legacy, hybrid = runs["legacy"], runs["hybrid"]
    assert _patterns(hybrid["log"]) >= _patterns(legacy["log"])
    repeats = lambda a: sum(n - 1 for n in Counter((t.action.label, t.action.target) for t in a.transitions
                                                   if t.action.target).values())
    assert repeats(hybrid["artifact"]) < repeats(legacy["artifact"])
    # Before the frontier holds only redundant items, the hybrid never repeats an exact target in one role.
    rows = [r for r in _decisions(hybrid["out"]) if "reason" in r]
    first_fallback = next((r["n"] for r in rows if r["reason"] == "all_redundant_legacy_fallback"), len(rows))
    ledger = ExecutionLedger.load(hybrid["out"] / "execution_ledger.jsonl")
    before = {e.transition_id: e.session.role for e in ledger.entries
              if e.purpose == "discovery" and e.transition_id and int(e.plan_id[1:]) < first_fallback}
    keys = [(before[t.id], t.action.label, t.action.target) for t in hybrid["artifact"].transitions
            if t.id in before and t.action.target]
    assert keys and len(keys) == len(set(keys))


def test_twin_controls_with_different_operations_stay_distinct(runs):
    h = runs["hybrid"]
    pats = _patterns(h["log"])
    assert {"GET /api/first", "GET /api/second"} <= pats
    acg = LiveACG(application="t", sink=h["explorer"].evidence_sink)
    acg.sync(h["artifact"])
    export = acg.export()
    ops = {o.id: o.route for o in export.operations}
    holder = {r: {c.id for c in export.capabilities if any(ops[i] == r for i in c.operation_ids)}
              for r in ("/api/first", "/api/second")}
    assert holder["/api/first"] and holder["/api/second"] and not (holder["/api/first"] & holder["/api/second"])


def test_deferrals_are_grounded_in_executed_evidence_and_not_suppression(runs):
    h = runs["hybrid"]
    summary = h["explorer"].hybrid_summary
    executed = {t.id for t in h["artifact"].transitions}
    deferred = [d for r in _decisions(h["out"]) if "reason" in r for d in r["deferred"]]
    assert deferred and all(d["evidence"] and set(d["evidence"]) <= executed for d in deferred)
    assert set(summary["deferral_reasons"]) <= {"same_target_repeat", "family_settled", "cross_role_repeat"}
    # Deferred, not deleted: either still queued at the end or executed once nothing better remained.
    assert summary["redundant_actions_prevented"] + summary["deferred_then_executed"] == summary["deferred_items"]


def test_prerequisite_chain_is_continued_in_the_live_session(runs):
    h = runs["hybrid"]
    assert h["state"]["setup_finished"] >= 1
    rows = [r for r in _decisions(h["out"]) if r.get("reason", "").startswith("prerequisite_continuation")]
    labels = {(r["chosen"]["label"], r["reason"]) for r in rows}
    assert ("Continue", "prerequisite_continuation:enabled") in labels
    assert ("Load panel data", "prerequisite_continuation:revealed") in labels     # JavaScript-only reveal
    assert ("GET", "/api/panel") in h["log"]


def test_write_prerequisite_is_never_replayed(runs):
    h = runs["hybrid"]
    assert Counter(h["log"])[("POST", "/session")] <= 1
    ledger = ExecutionLedger.load(h["out"] / "execution_ledger.jsonl")
    member_paths = {t.id for t in h["artifact"].transitions
                    if any(d.label == "Enter member mode" for d in t.workflow_path)}
    for e in ledger.entries:
        if e.purpose == "verification" and e.replay_of in member_paths:
            assert e.outcome == "refused" and e.browser_actions == 0
