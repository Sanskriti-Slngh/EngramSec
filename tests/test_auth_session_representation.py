"""Authenticated-exploration representation: role separation and credential hygiene.

Phase 1 of the authenticated-coverage milestone found no tests asserting that (a) a role is carried by
session_context so capabilities from different permission contexts do not merge, and (b) no credential or
session-token value is ever placed in the records the agent keeps. These cover both. The restoration
session guard itself is already covered by test_restoration_contract.
"""
from types import SimpleNamespace as N

from agent1.action_behavior import action_identity, record_instance
from evaluation.auth_provision import AuthResult, _account_ref


def _obs(session, markers=None):
    return N(url="http://localhost/orders", session_context=session, session_markers=markers or {},
             route_pattern="/orders", state_signature="s", content_fingerprint="s")


def _control(css="#save"):
    return N(kind="form_submit", css_path=css, role="button", interaction="click", component="main",
             frame_index=0, behavior_revision=None, target=None, fields=[])


def test_same_page_and_control_under_different_roles_do_not_merge():
    # Identical route + control, two permission contexts: their action identities must differ so a
    # user-role capability and an admin-role capability are never collapsed into one.
    user, admin = _obs("registered_user"), _obs("admin")
    assert action_identity(user, _control()) != action_identity(admin, _control())


def test_role_difference_survives_identical_cookie_names():
    # user and admin on the same app typically share the SAME cookie name (e.g. a session id); the role
    # label, not session_markers, is what keeps them distinct.
    shared = {"cookie_names": ["session"], "local_storage_keys": [], "session_storage_keys": []}
    user, admin = _obs("registered_user", shared), _obs("admin", shared)
    assert user.session_markers == admin.session_markers
    assert action_identity(user, _control()) != action_identity(admin, _control())


def test_anonymous_vs_authenticated_record_instance_differ():
    anon = N(url="http://localhost/records/1", session_context="anonymous", session_markers={},
             route_pattern="/records/{id}")
    auth = N(url="http://localhost/records/1", session_context="registered_user", session_markers={},
             route_pattern="/records/{id}")
    assert record_instance(anon) != record_instance(auth)


def test_auth_result_public_view_contains_no_secrets():
    # A provisioned result carries a role, an opaque account ref, and a prerequisite descriptor -- never
    # a username value or password.
    r = AuthResult(status="authenticated", role="registered_user", source="registered_disposable",
                   account_ref=_account_ref("app", "ava"),
                   prerequisite={"kind": "authentication", "method": "form_login", "login_route": "/login",
                                 "field_names": ["username_or_email", "password"], "role": "registered_user",
                                 "account_ref": _account_ref("app", "ava")})
    blob = repr(r.public())
    assert "password" in blob            # the FIELD NAME may appear
    assert "ava" not in blob             # the username VALUE must not
    assert r.public()["account_ref"].startswith("acct_")
    # account_ref is a one-way digest prefix, not the username
    assert "ava" not in r.public()["account_ref"]


def test_account_ref_is_stable_and_opaque():
    a = _account_ref("role_lab", "ava")
    assert a == _account_ref("role_lab", "ava")          # stable within an app
    assert a != _account_ref("role_lab", "iris")         # distinguishes accounts
    assert a != _account_ref("other_app", "ava")         # scoped by app
    assert len(a) == len("acct_") + 12
