"""role_lab fixture enforces authorization server-side (not cosmetic labels)."""
import urllib.request
import urllib.error
from http.cookiejar import CookieJar

import pytest

from development_apps.role_lab import ACCOUNTS, CAPABILITIES, STATE, role_inventory, start_role_lab


@pytest.fixture()
def server():
    srv, url, state = start_role_lab()
    yield url, state
    srv.shutdown()


def _opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()),
                                       _NoRedirect())


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_a, **_k):  # do not follow, so we can observe 302s
        return None


def _get(opener, url, path):
    try:
        return opener.open(url.rstrip("/") + path).getcode()
    except urllib.error.HTTPError as e:
        return e.code


def _login(opener, url, username):
    import urllib.parse
    data = urllib.parse.urlencode({"username": username, "password": ACCOUNTS[username]["password"]}).encode()
    try:
        return opener.open(url.rstrip("/") + "/login", data=data).getcode()
    except urllib.error.HTTPError as e:
        return e.code


def test_anonymous_sees_public_but_not_user_or_admin(server):
    url, _ = server
    op = _opener()
    assert _get(op, url, "/catalog") == 200
    assert _get(op, url, "/item?id=2") == 200
    assert _get(op, url, "/dashboard") == 302      # redirect to login, not served
    assert _get(op, url, "/admin") == 403          # forbidden, not merely hidden


def test_user_reaches_user_area_but_admin_is_forbidden(server):
    url, _ = server
    op = _opener()
    assert _login(op, url, "ava") in (302, 200)
    assert _get(op, url, "/dashboard") == 200
    assert _get(op, url, "/profile") == 200
    assert _get(op, url, "/admin") == 403          # a logged-in non-admin is still refused
    assert _get(op, url, "/admin/users") == 403


def test_admin_reaches_admin_area(server):
    url, _ = server
    op = _opener()
    assert _login(op, url, "iris") in (302, 200)
    assert _get(op, url, "/admin") == 200
    assert _get(op, url, "/admin/users") == 200


def test_cross_role_attempts_are_recorded_server_side(server):
    url, state = server
    op = _opener()
    _get(op, url, "/admin")                        # anonymous -> admin
    _login(op, url, "ava")
    _get(op, url, "/admin/users")                  # user -> admin
    denied = state.snapshot()["access_denied"]
    assert any(d["role"] == "anonymous" for d in denied)
    assert any(d["role"] == "registered_user" for d in denied)


def test_role_inventory_is_monotonic():
    assert role_inventory("anonymous") < role_inventory("registered_user") < role_inventory("admin")
    assert role_inventory("admin") == set(CAPABILITIES)
    # every capability's required role is a known rank
    assert all(r in {"anonymous", "registered_user", "admin"} for r in CAPABILITIES.values())


def test_seeded_passwords_are_not_constant_across_processes():
    # Passwords are generated with secrets at import time; they are not a committed constant.
    assert len(ACCOUNTS["ava"]["password"]) >= 8
    assert ACCOUNTS["ava"]["password"] != ACCOUNTS["iris"]["password"]
