"""gated_get_lab: a functional hub reached by GET reveals a deep subtree of distinct operations; no writes."""
import urllib.request
import urllib.error

import pytest

from development_apps.gated_get_lab import (ALWAYS_REACHABLE, CATALOG_ITEMS, DEEP_GET_SUBTREE,
                                            FUNCTIONAL_CAPABILITIES, SECTIONS, start_gated_get_lab)


@pytest.fixture()
def server():
    srv, url, state = start_gated_get_lab()
    yield url, state
    srv.shutdown()


def _get(url, path):
    try:
        with urllib.request.urlopen(url.rstrip("/") + path) as r:
            return r.getcode()
    except urllib.error.HTTPError as e:
        return e.code


def test_breadth_and_hub_are_reachable(server):
    url, _ = server
    assert _get(url, "/catalog") == 200
    assert _get(url, f"/item/{CATALOG_ITEMS}") == 200
    assert _get(url, "/dashboard") == 200


def test_hub_reveals_a_deep_distinct_subtree(server):
    url, state = server
    for p in ("/dashboard", "/dashboard/reports", "/dashboard/settings", "/dashboard/billing",
              "/dashboard/reports/monthly", "/dashboard/reports/annual", "/dashboard/reports/export",
              "/dashboard/settings/profile", "/dashboard/settings/security",
              "/dashboard/billing/invoices", "/dashboard/billing/plan"):
        assert _get(url, p) == 200
    funcs = set(state.snapshot()["functions"])
    assert DEEP_GET_SUBTREE <= funcs


def test_ground_truth_distinguishes_functional_subtree_from_breadth():
    # the hub's children are distinct operations (a functional area), two levels deep
    assert len(DEEP_GET_SUBTREE) >= 8
    assert ALWAYS_REACHABLE.isdisjoint(DEEP_GET_SUBTREE)
    assert ALWAYS_REACHABLE | DEEP_GET_SUBTREE == FUNCTIONAL_CAPABILITIES
    # sections are breadth leaves of a single template each
    assert set(SECTIONS.values()) and "item" in SECTIONS.values()
