"""Opt-in direct-URL restoration and well-known (robots.txt / sitemap.xml) discovery."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent1.explorer import BrowserSession, Explorer
from agent1.resource_spider import extract_references, extract_robots_sitemaps
from agent1.schema import ActionDescriptor, EvidenceStatus, FrontierItem, ReadinessEvidence, RunConfig, Transition
from tests.test_restoration_contract import BASE, board, ctl, page


# ------------------------------------------------------------------ robots.txt / sitemap.xml
def test_robots_yields_sitemaps_and_literal_allow_disallow_paths_only():
    text = ("User-agent: *\nDisallow: /private/area\nAllow: /public/page.html  # note\nDisallow: /\n"
            "Disallow: /*.pdf$\nDisallow: /tmp*\nSitemap: http://127.0.0.1:9/map.xml\n# Disallow: /commented\n")
    refs = {(r.url, r.source) for r in extract_robots_sitemaps(text, BASE + "robots.txt")}
    assert refs == {(BASE + "private/area", "Disallow:"), (BASE + "public/page.html", "Allow:"),
                    ("http://127.0.0.1:9/map.xml", "Sitemap:")}
    sitemap = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>http://127.0.0.1:9/a</loc></url></urlset>'
    assert [r.url for r in extract_references(sitemap, BASE + "sitemap.xml", "application/xml")] == [BASE + "a"]


def test_well_known_locations_are_seeded_once_and_only_in_scope(tmp_path):
    explorer = Explorer(RunConfig(start_url=BASE, output_dir=tmp_path, typed_resource_spider=True,
                                  well_known_discovery=True), tmp_path)
    spider = explorer.resource_spider
    assert spider.seed_well_known(BASE + "robots.txt") and not spider.seed_well_known(BASE + "robots.txt")
    assert not spider.seed_well_known("http://elsewhere.test/robots.txt")
    assert not spider.seed_well_known(BASE + "sitemap.xml?x=1")
    assert RunConfig(start_url=BASE, output_dir=tmp_path).well_known_discovery is False


# ------------------------------------------------------------------ direct-URL restoration
class _Session:
    def __init__(self, arrive):
        self.arrive, self.visited = arrive, []
        self.page = SimpleNamespace(url=BASE)
        self.last_readiness, self.last_navigation_network, self.last_navigation_resources = ReadinessEvidence(), [], []

    def goto(self, url):
        self.visited.append(url)
        self.page.url = url
        return 1

    def observe(self, _):
        return self.arrive

    def find_current(self, observation, descriptor):
        return BrowserSession.find_current(None, observation, descriptor)


def _setup(tmp_path, steps, policy="strict", shortcut="direct_url", url_path="board"):
    explorer = Explorer(RunConfig(start_url=BASE, output_dir=tmp_path, restoration_shortcut=shortcut,
                                  restoration_policy=policy), tmp_path)
    expected, _ = page(url_path, *board())
    path = [ActionDescriptor(control_id=f"c{i}", kind=k, label=f"s{i}", role="link" if k == "link" else "button",
                             css_path=f"a{i}", target=t, signature=f"sig{i}", interaction="click",
                             fields=[], provenance=prov) for i, (k, t, prov) in enumerate(steps)]
    item = FrontierItem(source_observation_id=expected.id, expected_source_signature=expected.state_signature,
                        expected_source_group=expected.group_signature, action=path[-1], path=path, priority=0.0)
    return explorer, expected, item


LINKS = [("link", BASE + "categories", "snapshot"), ("link", BASE + "board", "snapshot")]


def test_a_plain_link_chain_is_restored_by_one_direct_navigation(tmp_path):
    explorer, expected, item = _setup(tmp_path, LINKS)
    session = _Session(expected)
    assert explorer._direct_url_restore(session, item, expected, expected.group_signature) is expected
    assert session.visited == [expected.url]
    stats = explorer.artifact.metrics.restoration_contract["direct_url"]
    assert stats == {"attempted": 1, "accepted": 1, "fallback": 0, "actions_saved": 2}
    assert explorer.artifact.metrics.discovery_root_reloads == 0


@pytest.mark.parametrize("steps", [
    [("link", BASE + "categories", "snapshot"), ("button", None, "snapshot")],          # a handler step
    [("link", BASE + "categories", "observed_listener")],                               # listener provenance
    [("link", "http://elsewhere.test/x", "snapshot")],                                  # out of scope
])
def test_paths_with_handlers_listeners_or_foreign_links_are_never_shortcut(tmp_path, steps):
    explorer, expected, item = _setup(tmp_path, steps)
    session = _Session(expected)
    assert explorer._direct_url_restore(session, item, expected, expected.group_signature) is None
    assert session.visited == []


def test_a_step_once_seen_writing_or_changing_state_is_never_shortcut(tmp_path):
    explorer, expected, item = _setup(tmp_path, LINKS)
    explorer.artifact.transitions.append(Transition(
        id="t", source_observation_id=expected.id, source_state_signature="s", source_group_signature="g",
        action=item.path[0], workflow_path=[item.path[0]], status=EvidenceStatus.FAILED, error="x",
        behavior={"possible_state_change": True}, started_at="x", ended_at="x", run_id="r"))
    session = _Session(expected)
    assert explorer._direct_url_restore(session, item, expected, expected.group_signature) is None
    assert session.visited == []


def test_a_different_arrival_falls_back_unless_the_contract_accepts_it(tmp_path):
    explorer, expected, item = _setup(tmp_path, LINKS)
    other, _ = page("board", *board(done=1, marked=(1,)))
    session = _Session(other)
    assert explorer._direct_url_restore(session, item, expected, expected.group_signature) is None   # strict: fall back
    assert explorer.artifact.metrics.restoration_contract["direct_url"]["fallback"] == 1
    # A redacted (sensitive-query) URL is never navigated to directly.
    redacted = expected.model_copy(update={"url": BASE + "board?token=<redacted>"})
    assert explorer._direct_url_restore(_Session(expected), item, redacted, expected.group_signature) is None


def test_default_configuration_keeps_path_replay(tmp_path):
    explorer, expected, item = _setup(tmp_path, LINKS, shortcut="none")
    session = _Session(expected)
    assert explorer._direct_url_restore(session, item, expected, expected.group_signature) is None
    assert RunConfig(start_url=BASE, output_dir=tmp_path).restoration_shortcut == "none"
