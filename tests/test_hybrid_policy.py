"""Deterministic tests of the capability-aware legacy hybrid (no browser).

The policy only reorders: a deferred item stays in the frontier and runs when
nothing non-redundant is left. These tests check that it reduces redundant work
while still covering every distinct behavior.
"""
from __future__ import annotations

from collections import Counter
from types import SimpleNamespace

from agent1.live.hybrid import (CapabilityPolicy, HybridController, Sample, continuation_signatures, exact_of,
                                family_of, verification_gate)
from agent1.schema import ActionDescriptor


def item(family, exact, behavior, role="anon", instance=None):
    return SimpleNamespace(family=family, exact=exact, role=role, instance=instance or exact, behavior=behavior)


def simulate(items, hybrid: bool, budget: int | None = None):
    """Legacy order = list order; the hybrid takes the first non-redundant item, else the legacy one."""
    policy, samples, remaining, executed = CapabilityPolicy(), [], list(items), []
    while remaining and (budget is None or len(executed) < budget):
        index = 0
        if hybrid:
            policy.rebuild(samples)
            index = next((i for i, it in enumerate(remaining)
                          if not policy.assess(it.family, it.exact, it.role).redundant), 0)
        it = remaining.pop(index)
        executed.append(it)
        samples.append(Sample(f"t{len(executed)}", it.family, it.exact, it.role, it.instance, it.behavior))
    return executed


def distinct(executed):
    return {(it.family, it.behavior, it.role) for it in executed}


def to_cover_all(items, hybrid):
    goal, seen = distinct(items), set()
    for n, it in enumerate(simulate(items, hybrid), 1):
        seen.add((it.family, it.behavior, it.role))
        if seen == goal:
            return n
    return None


# 1 -------------------------------------------------------------------------------------------
def test_01_list_of_200_records_exposing_one_capability():
    records = [item("link:/records/{id}", f"/records/{i}", ("GET /records/{id}", "navigated")) for i in range(200)]
    others = [item(f"other{i}", f"/o{i}", (f"GET /o{i}", "navigated")) for i in range(5)]
    items = records + others
    assert to_cover_all(items, hybrid=False) == 205
    assert to_cover_all(items, hybrid=True) == 2 + 5            # two representatives, then everything distinct
    # Under a tight budget the hybrid covers every distinct behavior; legacy covers one.
    assert distinct(simulate(items, True, budget=10)) == distinct(items)
    assert len(distinct(simulate(items, False, budget=10))) == 1
    # Nothing is dropped: with no budget limit every record still runs, just later.
    assert len(simulate(items, True)) == 205


# 2 -------------------------------------------------------------------------------------------
def test_02_structurally_identical_controls_with_different_operations_are_not_merged():
    twins = [item("h:/redefine:Check loans", "first", ("GET /api/first",)),
             item("h:/redefine:Check loans", "second", ("GET /api/second",)),
             item("h:/redefine:Check loans", "third", ("GET /api/first",))]
    executed = simulate(twins, hybrid=True)
    assert [it.exact for it in executed] == ["first", "second", "third"]
    policy = CapabilityPolicy()
    policy.rebuild([Sample("t1", *("h:/redefine:Check loans", "first", "anon", "first", ("GET /api/first",))),
                    Sample("t2", *("h:/redefine:Check loans", "second", "anon", "second", ("GET /api/second",)))])
    a = policy.assess("h:/redefine:Check loans", "third", "anon")
    assert not a.redundant and a.reason == "family_split"


def _descriptor(**kw) -> ActionDescriptor:
    base = dict(control_id="c", kind="button", label="History", role="button", css_path="#h", signature="s")
    return ActionDescriptor(**{**base, **kw})


# 3 -------------------------------------------------------------------------------------------
def test_03_handler_change_is_a_new_family_and_late_divergence_lifts_deferral():
    old, new = _descriptor(), _descriptor(behavior_revision="rev2")
    assert family_of("/items/{id}", old) != family_of("/items/{id}", new)
    policy = CapabilityPolicy()
    fam = family_of("/items/{id}", old)
    policy.rebuild([Sample("t1", fam, "e1", "anon", "i1", ("GET /api/h?mode=a",)),
                    Sample("t2", fam, "e2", "anon", "i2", ("GET /api/h?mode=a",))])
    assert policy.assess(fam, "e3", "anon").reason == "family_settled"
    assert policy.assess(family_of("/items/{id}", new), "e3", "anon").reason == "novel"
    policy.rebuild(policy.samples + [Sample("t3", fam, "e3", "anon", "i3", ("GET /api/h?mode=b",))])
    assert policy.assess(fam, "e4", "anon").reason == "family_split"      # evidence-backed split


# 4 -------------------------------------------------------------------------------------------
def test_04_global_navigation_repeated_across_templates():
    nav = [item("link:/shallow/a", "/shallow/a", ("GET /shallow/a", "navigated"), instance="/shallow/a")
           for _ in range(10)]
    pages = [item(f"page{i}", f"/p{i}", (f"GET /p{i}",)) for i in range(4)]
    interleaved = [x for pair in zip(nav, pages + [None] * 6) for x in pair if x is not None]
    executed = simulate(interleaved, hybrid=True, budget=5)
    assert sum(it.family == "link:/shallow/a" for it in executed) == 1
    assert distinct(executed) == distinct(interleaved)
    # Same target from different source templates is one exact key; a label alone never is.
    d1 = _descriptor(kind="link", label="Overview", target="http://h/shallow/a", method="GET")
    d2 = _descriptor(kind="link", label="Overview", target="http://h/shallow/a", method="GET", css_path="footer a")
    assert exact_of("/", "g1", d1) == exact_of("/reports", "g9", d2)
    same_label = [_descriptor(label="Save"), _descriptor(label="Save")]
    assert family_of("/notes", same_label[0]) != family_of("/records/{id}", same_label[1])


# 5 -------------------------------------------------------------------------------------------
def _obs(oid, path, group="g", role_ctx="ctx", cookies=()):
    return SimpleNamespace(id=oid, url=f"http://h{path}", route_pattern=path, group_signature=group,
                           session_context=role_ctx, session_markers={"cookie_names": list(cookies)})


def _frontier_item(source, label, kind="button", target=None):
    d = _descriptor(label=label, kind=kind, target=target, signature=f"sig:{label}", control_id=label,
                    method="GET" if target else None)
    return SimpleNamespace(source_observation_id=source.id, expected_source_group=source.group_signature, action=d)


def _controller(observations):
    by_id = {o.id: o for o in observations}
    ex = SimpleNamespace(_observation_by_id=by_id.get, evidence_sink=None, frontier=[],
                         artifact=SimpleNamespace(metrics=SimpleNamespace(browser_actions=0), transitions=[],
                                                  observations=observations))
    return HybridController(ex)


def test_05_stateful_chain_continues_past_the_local_burst_limit():
    setup = _obs("o1", "/setup")
    review, cont = _frontier_item(setup, "Review", "link", "http://h/setup/review"), _frontier_item(setup, "Continue")
    h = _controller([setup])
    found = continuation_signatures("/setup", {"sig:Accept", "sig:Review"}, "/setup",
                                    {"sig:Accept", "sig:Review", "sig:Continue"}, {"sig:Continue"}, set())
    assert found == {"sig:Continue": "enabled"}
    h.open["sig:Continue"] = {"kind": "enabled", "after": "t1", "page": "/setup"}
    index, local = h.select([review, cont], setup, lambda c: True, legacy_index=None, local_burst=8)
    assert (index, local) == (1, True)
    assert h.decisions[-1]["reason"] == "prerequisite_continuation:enabled"
    # Without the hypothesis the legacy choice stands (burst limit reached -> frontier head).
    h.open.clear()
    assert h.select([review, cont], setup, lambda c: True, legacy_index=None, local_burst=8)[0] == 0


# 6 -------------------------------------------------------------------------------------------
def test_06_disabled_control_becoming_enabled_since_the_last_visit():
    found = continuation_signatures("/setup", {"sig:Review"}, "/setup/review", {"sig:Finish", "sig:Home"},
                                    set(), last_visit_disabled={"sig:Finish"})
    assert found == {"sig:Finish": "enabled"}            # navigation alone reveals nothing else
    assert continuation_signatures("/setup", set(), "/setup/review", {"sig:Finish"}, set(), set()) == {}


# 7 -------------------------------------------------------------------------------------------
def test_07_javascript_only_state_change_reveals_controls_on_the_same_page():
    found = continuation_signatures("/lab/multi", {"sig:Begin"}, "/lab/multi", {"sig:Begin", "sig:Continue"},
                                    set(), set())
    assert found == {"sig:Continue": "revealed"}
    # Another record of the same template is a different page, not a revealed control.
    assert continuation_signatures("/records/1", {"sig:a"}, "/records/2", {"sig:a", "sig:b"}, set(), set()) == {}


# 8 -------------------------------------------------------------------------------------------
def test_08_safe_read_only_replay_is_feasible():
    assert verification_gate(["open", "load"], write_signatures=set(), unreachable_prefixes=set(),
                             requires_session=False) == (True, "feasible")


# 9 -------------------------------------------------------------------------------------------
def test_09_replay_requiring_unavailable_state_changing_prerequisites_is_blocked():
    writes = {"enter_member_mode"}
    assert verification_gate(["enter_member_mode", "prefs"], writes, set(), False) == \
        (False, "state_changing_prerequisite")
    assert verification_gate(["open", "enter_member_mode"], writes, set(), False) == \
        (False, "write_capable_operation")
    assert verification_gate(["prefs"], set(), set(), requires_session=True) == (False, "session_state_unavailable")
    assert verification_gate(["a", "b", "c"], set(), {("a", "b")}, False) == (False, "prefix_unreachable")
    assert verification_gate(["a", "x"], set(), {("a", "b")}, False) == (True, "feasible")


# 10 ------------------------------------------------------------------------------------------
def test_10_ambiguous_equivalence_is_not_deferred():
    p = CapabilityPolicy()
    p.rebuild([Sample("t1", "F", "e1", "anon", "i1", ("GET /x",))])
    assert p.assess("F", "e2", "anon").reason == "uncertain"                   # one sample is not a family
    p.rebuild([Sample("t1", "F", "e1", "anon", "i1", ("GET /x",)), Sample("t2", "F", "e1b", "anon", "i1", ("GET /x",))])
    assert p.assess("F", "e2", "anon").reason == "uncertain"                   # same instance twice
    assert p.assess("G", "e2", "anon").reason == "novel"                       # no evidence at all


def test_cross_role_repeats_need_matching_transfer_samples():
    anon = [Sample(f"a{i}", f"F{i}", f"e{i}", "anon", f"e{i}", (f"op{i}",)) for i in range(4)]
    p = CapabilityPolicy()
    p.rebuild(anon + [Sample("m0", "F0", "e0", "member", "e0", ("op0",))])
    assert p.assess("F2", "e2", "member").reason == "uncertain"                # one transfer sample so far
    p.rebuild(anon + [Sample("m0", "F0", "e0", "member", "e0", ("op0",)),
                      Sample("m1", "F1", "e1", "member", "e1", ("op1",))])
    a = p.assess("F2", "e2", "member")
    assert a.redundant and a.reason == "cross_role_repeat"
    p.rebuild(anon + [Sample("m0", "F0", "e0", "member", "e0", ("op0",)),
                      Sample("m1", "F1", "e1", "member", "e1", ("op1-member-only",)),
                      Sample("m2", "F3", "e3", "member", "e3", ("op3",))])
    assert not p.assess("F2", "e2", "member").redundant                        # a divergent role is re-explored


def test_all_redundant_falls_back_to_legacy_choice():
    page = _obs("o1", "/")
    a, b = _frontier_item(page, "A", "link", "http://h/a"), _frontier_item(page, "B", "link", "http://h/b")
    h = _controller([page])
    fa = family_of("/", a.action)
    h.policy.rebuild([Sample("t1", fa, exact_of("/", "g", a.action), "ctx", "http://h/a", ("GET /a",)),
                      Sample("t2", family_of("/", b.action), exact_of("/", "g", b.action), "ctx", "http://h/b",
                             ("GET /b",))])
    h.assess = lambda it: h.policy.assess(family_of("/", it.action), exact_of("/", "g", it.action), "ctx")
    index, _ = h.select([a, b], page, lambda c: True, legacy_index=0, local_burst=0)
    assert index == 0 and h.decisions[-1]["reason"] == "all_redundant_legacy_fallback"
    assert Counter(d["reason"] for d in h.decisions[-1]["deferred"]) == Counter({"same_target_repeat": 2})


def test_post_eval_rerender_does_not_reopen_an_executed_control():
    """Post-evaluation fix (JS-heavy lab): continuation is only for controls not yet executed on that page and role."""
    home_a, home_b = _obs("o1", "/", group="g1"), _obs("o2", "/", group="g2")
    reports = SimpleNamespace(signature="sig:Open reports")
    workflow = SimpleNamespace(signature="sig:Open workflow")
    h = _controller([home_a, home_b])
    h.ex.artifact.transitions = [SimpleNamespace(id="t0", source_observation_id="o1", action=reports),
                                 SimpleNamespace(id="t1", source_observation_id="o1", action=workflow)]
    home_a.controls = [SimpleNamespace(signature="sig:Open workflow", safe=True)]
    home_b.controls = [SimpleNamespace(signature=s, safe=True) for s in ("sig:Open workflow", "sig:Open reports",
                                                                          "sig:Load late")]
    h._learn_continuation(home_a, home_b, h.ex.artifact.transitions[1])
    assert set(h.open) == {"sig:Load late"}
    assert h.counters["hypothesis_already_executed"] == 1
