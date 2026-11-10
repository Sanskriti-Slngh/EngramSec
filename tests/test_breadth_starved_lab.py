"""breadth_starved_lab: GET-only breadth-starved fixture; every capability reachable, releases gated only
by item content, ground-truth classes correct. No auth/write/JS/destructive routes."""
import urllib.request
import urllib.error

import pytest

from development_apps.breadth_starved_lab import (
    ALWAYS_REACHABLE, DEEP_FUNCTIONAL, FUNCTIONAL_CAPABILITIES, SECTIONS, SEMANTIC_ONLY_DEEP,
    TEMPLATE_DISTINCT_DEEP, REPORTS, SETTINGS, OPS, RELEASE_IDS, ITEMS, UPDATES, start_breadth_starved_lab)


@pytest.fixture()
def server():
    srv, url, state = start_breadth_starved_lab()
    yield url, state
    srv.shutdown()


def _get(url, path):
    try:
        with urllib.request.urlopen(url.rstrip("/") + path) as r:
            return r.getcode()
    except urllib.error.HTTPError as e:
        return e.code


def test_ground_truth_is_consistent():
    assert ALWAYS_REACHABLE.isdisjoint(DEEP_FUNCTIONAL)
    assert TEMPLATE_DISTINCT_DEEP.isdisjoint(SEMANTIC_ONLY_DEEP)
    assert TEMPLATE_DISTINCT_DEEP | SEMANTIC_ONLY_DEEP == DEEP_FUNCTIONAL
    assert ALWAYS_REACHABLE | DEEP_FUNCTIONAL == FUNCTIONAL_CAPABILITIES
    # enough deep functionality that prioritization matters, and a non-trivial semantic slice
    assert len(DEEP_FUNCTIONAL) >= 20
    assert len(SEMANTIC_ONLY_DEEP) == len(RELEASE_IDS) >= 4


def test_every_capability_is_get_reachable(server):
    url, state = server
    _get(url, "/")
    for s, leaf in SECTIONS.items():
        _get(url, f"/{s}"); _get(url, f"/{leaf}/1")
    _get(url, "/reports")
    for t, views in REPORTS.items():
        _get(url, f"/reports/{t}")
        for v in views:
            _get(url, f"/reports/{t}/{v}")
    _get(url, "/settings")
    for a, subs in SETTINGS.items():
        _get(url, f"/settings/{a}")
        for s in subs:
            _get(url, f"/settings/{a}/{s}")
    _get(url, "/ops")
    for o, subs in OPS.items():
        _get(url, f"/ops/{o}")
        for s in subs:
            _get(url, f"/ops/{o}/{s}")
    _get(url, "/updates")
    for i in range(1, UPDATES + 1):
        _get(url, f"/updates/{i}")
    for i in RELEASE_IDS:
        _get(url, f"/updates/{i}/changelog")
    assert set(state.snapshot()["functions"]) == FUNCTIONAL_CAPABILITIES


def test_releases_gated_only_by_item_content(server):
    url, _ = server
    # a release exposes a changelog; a non-release item does not (same list template either way)
    assert _get(url, f"/updates/{RELEASE_IDS[0]}/changelog") == 200
    non_release = next(i for i in range(1, UPDATES + 1) if i not in RELEASE_IDS)
    assert _get(url, f"/updates/{non_release}/changelog") == 404


def test_breadth_item_is_one_capability_regardless_of_count(server):
    url, state = server
    leaf = SECTIONS["products"]  # "product"
    _get(url, f"/{leaf}/1"); _get(url, f"/{leaf}/2"); _get(url, f"/{leaf}/{ITEMS}")
    # visiting many items records the single shared item capability, not one per item
    assert state.snapshot()["functions"].get("products_item") == 3
