"""Held-out Stage-1 variants: ground-truth classes are consistent, every capability is GET-reachable,
releases are gated only by item content, and the two variants are genuinely distinct shapes. Also asserts
the opt-in scheduling flags default OFF so the frozen baseline is preserved."""
import urllib.error
import urllib.request

import pytest

from development_apps.breadth_starved_variants import VARIANTS, start_variant, _truth


@pytest.fixture(params=sorted(VARIANTS))
def variant(request):
    srv, url, state, truth = start_variant(request.param)
    yield request.param, url, state, truth
    srv.shutdown()


def _get(url, path):
    try:
        with urllib.request.urlopen(url.rstrip("/") + path) as r:
            return r.getcode()
    except urllib.error.HTTPError as e:
        return e.code


def test_ground_truth_is_consistent(variant):
    _, _, _, t = variant
    assert t.always_reachable.isdisjoint(t.deep_functional)
    assert t.template_distinct_deep.isdisjoint(t.semantic_only_deep)
    assert t.template_distinct_deep | t.semantic_only_deep == t.deep_functional
    assert t.always_reachable | t.deep_functional == t.inventory
    # a non-trivial deep workload (so prioritization matters) and a real semantic slice
    assert len(t.deep_functional) >= 20
    assert len(t.semantic_only_deep) >= 4


def test_every_capability_is_get_reachable(variant):
    name, url, state, t = variant
    spec = VARIANTS[name]
    _get(url, "/")
    for s, leaf in spec.sections.items():
        _get(url, f"/{s}"); _get(url, f"/{leaf}/1")
    for hub, children in spec.hubs.items():
        _get(url, f"/{hub}")
        for c, grandkids in children.items():
            _get(url, f"/{hub}/{c}")
            for g in grandkids:
                _get(url, f"/{hub}/{c}/{g}")
    _get(url, f"/{spec.ambiguous}")
    for i in range(1, spec.ambiguous_items + 1):
        _get(url, f"/{spec.ambiguous}/{i}")
    for i in spec.release_ids:
        _get(url, f"/{spec.ambiguous}/{i}/changelog")
    assert set(state.snapshot()["functions"]) == t.inventory


def test_releases_gated_only_by_item_content(variant):
    name, url, _, _ = variant
    spec = VARIANTS[name]
    amb = spec.ambiguous
    assert _get(url, f"/{amb}/{spec.release_ids[0]}/changelog") == 200
    non_release = next(i for i in range(1, spec.ambiguous_items + 1) if i not in spec.release_ids)
    assert _get(url, f"/{amb}/{non_release}/changelog") == 404


def test_breadth_item_is_one_capability_regardless_of_count(variant):
    name, url, state, _ = variant
    spec = VARIANTS[name]
    sec, leaf = next(iter(spec.sections.items()))
    for n in (1, 2, spec.items):
        _get(url, f"/{leaf}/{n}")
    assert state.snapshot()["functions"].get(f"{sec}_item") == 3


def test_variants_are_distinct_shapes():
    a, b = _truth(VARIANTS["atlas"]), _truth(VARIANTS["orchard"])
    # different hub names / arity => disjoint template-distinct capability namespaces
    assert a.template_distinct_deep.isdisjoint(b.template_distinct_deep)
    assert VARIANTS["atlas"].nav != VARIANTS["orchard"].nav
    assert VARIANTS["atlas"].release_ids != VARIANTS["orchard"].release_ids


def test_scheduling_flags_default_off():
    from agent1.schema import RunConfig
    from pathlib import Path
    c = RunConfig(start_url="http://x/", output_dir=Path("/tmp/x"))
    assert c.fair_subtree_rotation is False
    assert c.focus_to_budget is False
    assert c.focus_stagnation_limit == 0
