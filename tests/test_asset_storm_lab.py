"""asset_storm_lab serves a shared static bundle on every page and records functional executions."""
import urllib.request

import pytest

from development_apps.asset_storm_lab import FUNCTIONAL_CAPABILITIES, MODULES, PAGES, start_asset_storm_lab


@pytest.fixture()
def server():
    srv, url, state = start_asset_storm_lab()
    yield url, state
    srv.shutdown()


def _get(url, path):
    with urllib.request.urlopen(url.rstrip("/") + path) as r:
        return r.getcode(), r.read().decode(errors="replace")


def test_every_page_links_the_full_module_bundle(server):
    url, _ = server
    for path in PAGES:
        code, body = _get(url, path if path != "/" else "/")
        assert code == 200
        # all script modules referenced -> a navigation re-pulls the whole bundle
        assert all(m in body for m in MODULES)


def test_navigation_refetches_assets_and_waste_is_measured(server):
    url, state = server
    for path in PAGES:
        _get(url, path if path != "/" else "/")
    # browsers would re-request the shared assets per page, but this direct client does not execute
    # <script> tags; fetch the bundle explicitly for two pages to simulate the refetch the agent causes.
    for _ in range(2):
        for m in MODULES[:5]:
            _get(url, m)
    snap = state.snapshot()
    assert snap["asset_requests_total"] >= 10
    assert snap["asset_refetch_waste"] >= 5          # the second pass is pure refetch


def test_functional_capabilities_are_recorded(server):
    url, state = server
    _get(url, "/")
    _get(url, "/gallery?q=rope")
    _get(url, "/detail?id=2")
    _get(url, "/api/stats")
    funcs = set(state.snapshot()["functions"])
    assert {"home_view", "gallery_view", "search", "detail_view", "stats_xhr"} <= funcs
    assert funcs <= FUNCTIONAL_CAPABILITIES
