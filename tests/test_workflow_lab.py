"""workflow_lab: a safe write genuinely unlocks deeper routes (positive control) vs a dead-end (negative)."""
import urllib.request
import urllib.error

import pytest

from development_apps.workflow_lab import (ALWAYS_REACHABLE, CATALOG_ITEMS, FUNCTIONAL_CAPABILITIES,
                                           WRITE_UNLOCKS, start_workflow_lab)


@pytest.fixture()
def server():
    srv, url, state = start_workflow_lab()
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


def _post(op, url, path, data):
    import urllib.parse
    try:
        r = op.open(url.rstrip("/") + path, data=urllib.parse.urlencode(data).encode())
        return r.getcode(), r.headers.get("Location")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location")


def test_navigation_breadth_is_present(server):
    url, _ = server
    op = _op()
    assert _get(op, url, "/catalog") == 200
    assert _get(op, url, "/guides") == 200
    assert _get(op, url, f"/item/{CATALOG_ITEMS}") == 200
    assert _get(op, url, f"/guide/{CATALOG_ITEMS}") == 200
    assert _get(op, url, "/workspace") == 200


def test_project_subtree_is_locked_until_the_create_write(server):
    url, _ = server
    op = _op()
    assert _get(op, url, "/project/1") == 404
    assert _get(op, url, "/project/1/settings") == 404
    code, loc = _post(op, url, "/projects", {"name": "Alpha"})
    assert code == 302 and loc == "/project/1"
    assert _get(op, url, "/project/1") == 200
    for sub in ("settings", "members", "tasks"):
        assert _get(op, url, f"/project/1/{sub}") == 200


def test_task_create_unlocks_task_detail(server):
    url, _ = server
    op = _op()
    _post(op, url, "/projects", {"name": "Alpha"})
    assert _get(op, url, "/project/1/task/1") == 404
    code, _ = _post(op, url, "/project/1/tasks", {"title": "T"})
    assert code == 302
    assert _get(op, url, "/project/1/task/1") == 200


def test_feedback_write_unlocks_only_a_dead_end(server):
    url, _ = server
    op = _op()
    code, loc = _post(op, url, "/feedback", {"message": "hi"})
    assert code == 302 and loc == "/feedback/thanks"
    assert _get(op, url, "/feedback/thanks") == 200
    assert WRITE_UNLOCKS["feedback_submit"] == {"feedback_thanks"}


def test_ground_truth_is_consistent():
    unlocked = set().union(*WRITE_UNLOCKS.values())
    assert ALWAYS_REACHABLE.isdisjoint(unlocked)
    assert ALWAYS_REACHABLE | unlocked | set(WRITE_UNLOCKS) <= FUNCTIONAL_CAPABILITIES
    assert len(WRITE_UNLOCKS["project_create"]) >= 4      # positive control: several deeper capabilities
    assert len(WRITE_UNLOCKS["feedback_submit"]) == 1     # negative control: one dead-end
