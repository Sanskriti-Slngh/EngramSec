"""Tests for the spa_router_lab measurable-SPA fixture (server behaviour + ground truth)."""
import json
import urllib.request

import pytest

from development_apps.spa_router_lab import MEMBER_COOKIE, ground_truth, start_spa_router_lab


@pytest.fixture()
def lab():
    server, _thread, url = start_spa_router_lab()
    try:
        yield url
    finally:
        server.shutdown()


def _get(url: str, cookie: str | None = None) -> tuple[int, str]:
    req = urllib.request.Request(url)
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
        return e.code, e.read().decode()


def test_shell_served_at_root_and_deep_link(lab):
    for path in ("", "app/dashboard", "app/settings"):
        status, body = _get(lab + path)
        assert status == 200
        assert "SPA Router Lab" in body
        assert "history.pushState" in body  # genuinely a pushState SPA


def test_ground_truth_counts():
    gt = ground_truth()
    assert gt["anonymous_total"] == 10
    assert gt["member_total"] == 2
    assert len(gt["capabilities"]) == 12


def test_view_ping_is_recorded(lab):
    _get(lab + "api/view?r=dashboard")
    status, body = _get(lab + "__eval__/stats")
    stats = json.loads(body)
    assert any("/api/view?r=dashboard" in k for k in stats)


def test_admin_view_gated_by_member_cookie(lab):
    status_anon, _ = _get(lab + "api/view?r=admin")
    assert status_anon == 403
    status_member, body = _get(lab + "api/view?r=admin", cookie=MEMBER_COOKIE)
    assert status_member == 200
    assert json.loads(body)["ok"] is True


def test_admin_audit_gated(lab):
    assert _get(lab + "api/admin/audit")[0] == 403
    assert _get(lab + "api/admin/audit", cookie=MEMBER_COOKIE)[0] == 200
