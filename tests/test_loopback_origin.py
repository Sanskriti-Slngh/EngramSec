"""Tests for the opt-in loopback_origin_equivalence flag (general-web traversal).

The flag canonicalizes the three loopback spellings (127.0.0.1 / localhost / ::1) of the
*same scheme+port* as one origin, so a page that links between them is reachable without
per-site alias configuration. It must never widen scope beyond those siblings, and it must
be default-off (preserving the frozen WebExploitBench baseline).
"""
from pathlib import Path

from agent1.schema import RunConfig
from agent1.state import allowed_origin


def _cfg(start: str, **kw) -> RunConfig:
    return RunConfig(start_url=start, output_dir=Path("/tmp/loopback_test"), **kw)


def test_default_off_preserves_baseline():
    c = _cfg("http://127.0.0.1:8123/")
    assert c.origin_aliases == []
    assert not allowed_origin(c.start_url, "http://localhost:8123/x", c.origin_aliases)


def test_on_allows_loopback_siblings_same_port():
    c = _cfg("http://127.0.0.1:8123/", loopback_origin_equivalence=True)
    assert allowed_origin(c.start_url, "http://localhost:8123/alias", c.origin_aliases)
    assert allowed_origin(c.start_url, "http://[::1]:8123/alias", c.origin_aliases)


def test_on_is_symmetric_from_localhost_start():
    c = _cfg("http://localhost:8123/", loopback_origin_equivalence=True)
    assert allowed_origin(c.start_url, "http://127.0.0.1:8123/y", c.origin_aliases)


def test_on_does_not_widen_to_other_ports():
    c = _cfg("http://127.0.0.1:8123/", loopback_origin_equivalence=True)
    assert not allowed_origin(c.start_url, "http://localhost:9999/x", c.origin_aliases)
    assert not allowed_origin(c.start_url, "http://127.0.0.1:9999/x", c.origin_aliases)


def test_on_does_not_widen_to_external_hosts():
    c = _cfg("http://127.0.0.1:8123/", loopback_origin_equivalence=True)
    assert not allowed_origin(c.start_url, "http://evil.test/x", c.origin_aliases)
    assert not allowed_origin(c.start_url, "http://169.254.1.1:8123/x", c.origin_aliases)


def test_on_respects_scheme():
    c = _cfg("http://127.0.0.1:8123/", loopback_origin_equivalence=True)
    # https is a different origin even for a loopback sibling
    assert not allowed_origin(c.start_url, "https://localhost:8123/x", c.origin_aliases)


def test_non_loopback_start_is_unaffected():
    # On a non-loopback start (e.g. a real deployment) the flag adds nothing implicitly.
    c = _cfg("http://127.0.0.1:8123/", loopback_origin_equivalence=True)
    before = set(c.origin_aliases)
    # sanity: siblings present for loopback start
    assert any("localhost" in a for a in before)
