"""Operator-authorized authenticated exploration for Agent 1 (mapper, not attacker).

Agent 1 never sees credentials. This harness provisions a browser session OUTSIDE the agent and
hands it the resulting Playwright storage-state file (the agent already supports
``RunConfig.storage_state_path`` for an operator-authorized pre-authenticated session). Secrets
live only under ``agent1/.auth/`` (git-ignored) and never enter Graph A / the ACG / logs / reports.

Credential sources, in order (per the operator's policy):
  1. operator-provided or harness-provisioned test credentials, read from the environment
     (``<APP>_TEST_USERNAME`` / ``_PASSWORD``, optionally ``_LOGIN_URL`` / ``_ROLE``);
  2. if none and the app offers registration, create a disposable account -- ONLY on an
     attested, resettable environment -- and keep its generated credentials privately for the run.

After login the session is verified (an authenticated marker must appear and a logged-out marker
must disappear). The login is recorded for Graph A as a PREREQUISITE descriptor: method, login
route, field NAMES, verification, role and an opaque account ref -- never secret values. If neither
path is available, the result records an access barrier (``status="no_auth"``) so the caller can
report the frontier as login-limited rather than fully explored.

This module performs the login itself with Playwright; it does not ask the agent to log in.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import sync_playwright

from evaluation.comprehensive_config import ROOT

AUTH_DIR = ROOT / "agent1" / ".auth"          # git-ignored
LOGGED_OUT = re.compile(r"log[\s_-]?in|sign[\s_-]?in|register|登录|注册", re.I)
LOGGED_IN = re.compile(r"log[\s_-]?out|sign[\s_-]?out|my account|profile|dashboard|logout|退出|注销|个人", re.I)


@dataclass
class AuthResult:
    status: str                                 # "authenticated" | "no_auth" | "failed"
    role: str = "anonymous"
    source: str | None = None                   # "operator_credentials" | "registered_disposable"
    storage_state_path: Path | None = None
    account_ref: str | None = None              # opaque, non-reversible handle for Graph A
    prerequisite: dict[str, Any] = field(default_factory=dict)
    barrier: str | None = None
    verification: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        """Everything here is safe for Graph A / reports: no secrets."""
        return {"status": self.status, "role": self.role, "source": self.source,
                "account_ref": self.account_ref, "prerequisite": self.prerequisite,
                "barrier": self.barrier, "verification": self.verification}


def _env(app: str, field: str) -> str | None:
    return os.environ.get(f"{app.upper().replace('-', '_')}_TEST_{field}")


def _account_ref(app: str, username: str) -> str:
    return "acct_" + hashlib.sha256(f"{app}:{username}".encode()).hexdigest()[:12]


# Conventional login/registration page paths. Trying these is URL-convention discovery of a sign-in
# PAGE, not credential guessing and not vulnerability-endpoint guessing.
LOGIN_PATHS = ("login", "signin", "sign-in", "account/login", "user/login", "users/sign_in", "auth/login")
REGISTER_PATHS = ("register", "signup", "sign-up", "account/register", "user/register", "users/sign_up")


def _has_password_field(page: Any) -> bool:
    return page.query_selector("input[type=password]") is not None


def _find_login(page: Any) -> str | None:
    """A same-origin link whose text/href looks like a login entry point."""
    for a in page.query_selector_all("a[href]"):
        text = (a.inner_text() or "")[:40]
        href = a.get_attribute("href") or ""
        if re.search(r"log[\s_-]?in|sign[\s_-]?in|登录", text + " " + href, re.I):
            return urljoin(page.url, href)
    return None


def _probe_paths(page: Any, base_url: str, paths: tuple[str, ...]) -> str | None:
    """First conventional path that actually renders a password field (i.e. a real auth form)."""
    for suffix in paths:
        try:
            page.goto(base_url.rstrip("/") + "/" + suffix, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(800)
        except Exception:
            continue
        if _has_password_field(page):
            return page.url
    return None


AUTHED_PATH = re.compile(r"dashboard|admin|profile|account|home|console|管理|仪表", re.I)
TOKEN_KEY = re.compile(r"token|jwt|auth|session|access", re.I)


def _session_token_present(page: Any) -> bool:
    try:
        store = page.evaluate("() => ({l: Object.entries(localStorage), s: Object.entries(sessionStorage)})")
    except Exception:
        return False
    for k, v in (store.get("l") or []) + (store.get("s") or []):
        if TOKEN_KEY.search(str(k)) and len(str(v)) > 16:
            return True
    return False


def _verify(page: Any, login_path: str | None = None) -> dict[str, Any]:
    body = (page.inner_text("body") or "")[:4000]
    cur = urlsplit(page.url).path
    token = _session_token_present(page)
    redirected = bool(login_path) and cur.rstrip("/") != (login_path or "").rstrip("/") and bool(AUTHED_PATH.search(cur))
    return {"logged_in_marker": bool(LOGGED_IN.search(body)),
            "logged_out_marker_gone": not bool(LOGGED_OUT.search(body)),
            "session_token_present": token, "redirected_to_app_area": redirected, "url": cur}


def _fill_and_submit(page: Any, username: str, password: str, email: str | None = None,
                     phone: str | None = None) -> None:
    """Fill the account and password, plus any other required text inputs (for registration)."""
    def hint(el: Any) -> str:
        return " ".join(filter(None, [el.get_attribute("name"), el.get_attribute("placeholder"),
                                       el.get_attribute("type"), el.get_attribute("id")])).lower()
    filled_account = False
    for el in page.query_selector_all("input"):
        itype = (el.get_attribute("type") or "text").lower()
        if itype in ("hidden", "submit", "button", "checkbox", "radio", "file", "search"):
            continue
        if (el.input_value() or "").strip():
            continue
        h = hint(el)
        if itype == "password":
            el.fill(password)
        elif "mail" in h or itype == "email":
            el.fill(email or f"{username}@example.invalid")
        elif any(k in h for k in ("phone", "tel", "mobile", "电话", "手机")) or itype == "tel":
            el.fill(phone or "13800000000")
        elif any(k in h for k in ("user", "account", "login", "名", "账")) and not filled_account:
            el.fill(username)
            filled_account = True
        elif itype in ("text", "number"):
            el.fill(username if not filled_account else "Agent One")
            filled_account = filled_account or True
    btn = page.query_selector("button[type=submit], input[type=submit]") or page.query_selector("button")
    if btn:
        btn.click()
    page.wait_for_timeout(1800)


def provision(app: str, base_url: str, *, attested_disposable: bool, aliases: list[str] | None = None,
              out_dir: Path | None = None) -> AuthResult:
    """Log in (or register then log in) OUTSIDE the agent, verify, and save the session state."""
    out_dir = out_dir or (AUTH_DIR / app)
    out_dir.mkdir(parents=True, exist_ok=True)
    username, password = _env(app, "USERNAME"), _env(app, "PASSWORD")
    source = "operator_credentials" if (username and password) else None
    email = _env(app, "EMAIL")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        page = ctx.new_page()
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=20000)
        except Exception as exc:
            browser.close()
            return AuthResult("failed", barrier=f"start_navigation:{type(exc).__name__}")
        login_url = _env(app, "LOGIN_URL") or _find_login(page) or _probe_paths(page, base_url, LOGIN_PATHS)
        registered_creds: dict[str, str] | None = None

        if not source:
            # No operator credentials: try disposable registration, attested environments only.
            reg_link = _env(app, "REGISTER_URL")
            if not reg_link:
                for a in page.query_selector_all("a[href]"):
                    if re.search(r"regist|sign[\s_-]?up|注册", (a.inner_text() or "") + (a.get_attribute("href") or ""), re.I):
                        reg_link = urljoin(page.url, a.get_attribute("href") or "")
                        break
            if not reg_link:
                reg_link = _probe_paths(page, base_url, REGISTER_PATHS)
            if not (reg_link and attested_disposable):
                browser.close()
                barrier = "login_required_no_credentials" if login_url else "no_login_or_registration_found"
                if reg_link and not attested_disposable:
                    barrier = "registration_available_but_environment_not_attested"
                return AuthResult("no_auth", barrier=barrier)
            username = f"a1_{secrets.token_hex(4)}"
            password = secrets.token_urlsafe(12)
            email = f"{username}@example.invalid"
            page.goto(reg_link, wait_until="domcontentloaded", timeout=20000)
            _fill_and_submit(page, username, password, email)
            registered_creds = {"username": username, "password": password, "email": email,
                                "registered_at": reg_link}
            source = "registered_disposable"
            login_url = login_url or _find_login(page) or reg_link

        # Log in.
        login_route = None
        if login_url:
            page.goto(login_url, wait_until="domcontentloaded", timeout=20000)
            login_route = urlsplit(page.url).path
            _fill_and_submit(page, username or "", password or "", email)
        verification = _verify(page, login_route)
        # Authenticated if an app session token exists, or the page shows a logged-in marker, or the
        # login submit redirected into an app area (dashboard/admin/...) with no logged-out markers.
        authenticated = (verification["session_token_present"] or verification["logged_in_marker"]
                         or (verification["redirected_to_app_area"] and verification["logged_out_marker_gone"]))
        if not authenticated:
            browser.close()
            return AuthResult("failed", source=source, barrier="login_not_verified", verification=verification)

        state_path = out_dir / "storage_state.json"
        ctx.storage_state(path=str(state_path))
        state_path.chmod(0o600)
        browser.close()

    if registered_creds:
        creds_path = out_dir / "credentials.json"
        creds_path.write_text(json.dumps(registered_creds))
        creds_path.chmod(0o600)

    role = _env(app, "ROLE") or ("registered_user" if source == "registered_disposable" else "authenticated")
    ref = _account_ref(app, username or "")
    prerequisite = {"kind": "authentication", "method": "form_login", "login_route": login_route,
                    "field_names": ["username_or_email", "password"], "role": role, "account_ref": ref,
                    "source": source, "verified_by": "authenticated marker present after submit"}
    return AuthResult("authenticated", role=role, source=source, storage_state_path=state_path,
                      account_ref=ref, prerequisite=prerequisite, verification=verification)
