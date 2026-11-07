"""branch_lab: two independent safe writes each unlock a distinct deeper subtree (branching control)."""
import urllib.request
import urllib.error

import pytest

from development_apps.branch_lab import (ALWAYS_REACHABLE, FUNCTIONAL_CAPABILITIES, WRITE_UNLOCKS,
                                         start_branch_lab)


@pytest.fixture()
def server():
    srv, url, state = start_branch_lab()
    yield url, state
    srv.shutdown()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_a, **_k):
        return None


def _op():
    return urllib.request.build_opener(_NoRedirect())


def _get(op, url, path):
    try:
        return op.open(url.rstrip("/") + path).getcode()
    except urllib.error.HTTPError as e:
        return e.code


def _post(op, url, path):
    try:
        r = op.open(url.rstrip("/") + path, data=b"name=x&title=x")
        return r.getcode(), r.headers.get("Location")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location")


def test_both_subtrees_locked_until_their_writes(server):
    url, _ = server
    op = _op()
    assert _get(op, url, "/project/1") == 404
    assert _get(op, url, "/report/1") == 404
    c1, l1 = _post(op, url, "/projects")
    c2, l2 = _post(op, url, "/reports")
    assert (c1, l1) == (302, "/project/1")
    assert (c2, l2) == (302, "/report/1")
    for p in ("/project/1", "/project/1/settings", "/project/1/members",
              "/report/1", "/report/1/summary", "/report/1/export"):
        assert _get(op, url, p) == 200


def test_ground_truth_two_disjoint_deep_subtrees():
    a, b = WRITE_UNLOCKS["project_create"], WRITE_UNLOCKS["report_create"]
    assert a.isdisjoint(b)
    assert len(a) >= 3 and len(b) >= 3          # two competing deep subtrees
    unlocked = a | b
    assert ALWAYS_REACHABLE.isdisjoint(unlocked)
    assert ALWAYS_REACHABLE | unlocked | set(WRITE_UNLOCKS) <= FUNCTIONAL_CAPABILITIES
