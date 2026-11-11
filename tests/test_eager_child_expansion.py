"""Stage-2 eager child expansion: the opt-in flag defaults off, the metrics fields exist, and the
eligibility gates only batch plain same-origin GET, distinct-template, non-write children of a verified
GET parent. Pure-logic tests (no browser) over the explorer's eligibility helpers."""
from pathlib import Path
from types import SimpleNamespace as N

from agent1.explorer import Explorer
from agent1.schema import RunConfig, RunMetrics
from agent1.state import route_pattern


def _explorer():
    ex = object.__new__(Explorer)
    ex.config = N(start_url="http://localhost/", origin_aliases=[], state_aware_exploration=False,
                  restoration_shortcut="direct_url")
    return ex


def _link(target="http://localhost/reports/revenue", **over):
    d = dict(kind="link", interaction="click", target=target, provenance="snapshot",
             behavior_revision=None, input_plan_ref=None, fields=[], signature="sig:" + target)
    d.update(over)
    return N(**d)


def _parent():
    return N(id="P", group_signature="g", url="http://localhost/reports")


def _item(action, source="P", group="g"):
    return N(source_observation_id=source, expected_source_group=group, action=action)


def test_flag_and_metrics_defaults():
    c = RunConfig(start_url="http://x/", output_dir=Path("/tmp/x"))
    assert c.eager_child_expansion is False
    assert c.eager_expansion_max == 6
    m = RunMetrics()
    for f in ("eager_batches", "eager_children_expanded", "eager_parent_returns", "eager_returns_rejected"):
        assert getattr(m, f) == 0


def test_child_eligible_for_distinct_get_sibling():
    ex, p = _explorer(), _parent()
    a = _link("http://localhost/reports/revenue")
    assert ex._eager_child_ok_item(p, _item(a), seen_templates={route_pattern(p.url).split("?")[0]}, unsafe=set())


def test_child_rejected_when_template_already_seen():
    ex, p = _explorer(), _parent()
    a = _link("http://localhost/reports/revenue")
    seen = {route_pattern(a.target).split("?")[0]}          # same template already covered => no batching
    assert not ex._eager_child_ok_item(p, _item(a), seen, set())


def test_child_rejected_for_write_or_nonlink_or_cross_parent():
    ex, p = _explorer(), _parent()
    a = _link("http://localhost/reports/usage")
    seen = {route_pattern(p.url).split("?")[0]}
    # observed write / possible state change
    assert not ex._eager_child_ok_item(p, _item(a), seen, unsafe={a.signature})
    # a form submit is not a plain GET link
    assert not ex._eager_child_ok_item(p, _item(_link(kind="form_submit")), seen, set())
    # an input-bearing control is not a plain navigation
    assert not ex._eager_child_ok_item(p, _item(_link(input_plan_ref="plan1")), seen, set())
    # a child of a different parent observation is never batched here
    assert not ex._eager_child_ok_item(p, _item(a, source="OTHER"), seen, set())
    # a group mismatch (would not live-reuse) is rejected
    assert not ex._eager_child_ok_item(p, _item(a, group="other"), seen, set())


def test_parent_ok_requires_direct_url_regime_and_plain_get_path():
    ex, p = _explorer(), _parent()
    get_step = _link("http://localhost/reports")
    assert ex._eager_parent_ok(p, [get_step])                 # reached by a plain GET link
    # a non-GET / form step in the parent's own path disqualifies holding it
    assert not ex._eager_parent_ok(p, [_link(kind="form_submit")])
    # outside the direct_url restoration regime the saver stays off
    ex.config.restoration_shortcut = "none"
    assert not ex._eager_parent_ok(p, [get_step])
