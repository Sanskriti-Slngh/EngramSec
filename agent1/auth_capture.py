"""Operator-side UI login → Playwright storage_state capture.

Agent 1 never types credentials during exploration; authenticated surface is reached by starting every
context from an operator-provided session (`RunConfig.storage_state_path`). This helper produces that
session by performing a genuine **UI login** (filling the form and submitting in a real browser) and
saving the full client auth state — cookies **and** localStorage/sessionStorage per origin.

Why a UI login and not an API call: many SPAs gate authenticated views on client state the login flow
writes (e.g. white-jotter stores `localStorage['username']` and a role in its Vuex store). An API-only
login sets the session cookie but not that client state, so the authenticated UI never appears. Driving
the real form runs the app's own login code, so `storage_state` captures everything the app needs.

CLI:
    python -m agent1.auth_capture --url http://127.0.0.1:PORT/ --user admin --password 123 \
        --out session.json [--username-selector ...] [--password-selector ...] [--submit-selector ...] \
        [--success-url-contains /admin] [--wait-ms 4000] [--ignore-https-errors]
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

# Heuristics for finding the fields when selectors are not given.
_USERNAME_CANDIDATES = (
    "input[type='email']",
    "input[name*='user' i]", "input[name*='email' i]", "input[name*='login' i]",
    "input[id*='user' i]", "input[id*='email' i]", "input[id*='login' i]",
    "input[placeholder*='user' i]", "input[placeholder*='email' i]",
    "input[type='text']",
)
_SUBMIT_CANDIDATES = (
    "button[type='submit']", "input[type='submit']",
    "button:has-text('Log in')", "button:has-text('Login')", "button:has-text('Sign in')",
    "button:has-text('登录')", "button:has-text('登 录')",
    "form button",
)


@dataclass
class LoginResult:
    output_path: Path
    cookies: int
    local_storage_keys: dict[str, list[str]] = field(default_factory=dict)
    final_url: str = ""
    verified: bool | None = None


def _first_visible(page, selectors):
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            if loc.count() > 0 and loc.is_visible():
                return loc
        except Exception:
            continue
    return None


def capture_login_session(
    login_url: str,
    username: str,
    password: str,
    output_path: str | Path,
    *,
    username_selector: str | None = None,
    password_selector: str | None = None,
    submit_selector: str | None = None,
    success_url_contains: str | None = None,
    wait_ms: int = 4000,
    ignore_https_errors: bool = False,
    headless: bool = True,
) -> LoginResult:
    """Perform a UI login at `login_url` and save the resulting session to `output_path`.

    Field/submit selectors are auto-detected when not provided. Returns a LoginResult describing the
    captured session (so the operator can sanity-check it before handing the file to `storage_state_path`).
    """
    from playwright.sync_api import sync_playwright

    output_path = Path(output_path)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            context = browser.new_context(ignore_https_errors=ignore_https_errors)
            page = context.new_page()
            page.goto(login_url, wait_until="domcontentloaded")
            # Wait for the password field to exist (covers SPA login routes that render after load).
            pwd_sel = password_selector or "input[type='password']"
            page.wait_for_selector(pwd_sel, timeout=wait_ms)

            pwd = page.locator(pwd_sel).first
            user = (page.locator(username_selector).first if username_selector
                    else _first_visible(page, _USERNAME_CANDIDATES))
            if user is None:
                raise RuntimeError("could not locate a username field; pass --username-selector")
            user.fill(username)
            pwd.fill(password)

            submit = (page.locator(submit_selector).first if submit_selector
                      else _first_visible(page, _SUBMIT_CANDIDATES))
            if submit is not None:
                submit.click()
            else:
                pwd.press("Enter")

            # Give the login its round-trip + client-state writes.
            if success_url_contains:
                try:
                    page.wait_for_url(f"**{success_url_contains}**", timeout=wait_ms)
                except Exception:
                    pass
            page.wait_for_timeout(wait_ms)

            verified: bool | None = None
            if success_url_contains:
                verified = success_url_contains in page.url

            state = context.storage_state()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(state))
            ls = {o.get("origin", ""): [kv.get("name") for kv in o.get("localStorage", [])]
                  for o in state.get("origins", [])}
            return LoginResult(
                output_path=output_path, cookies=len(state.get("cookies", [])),
                local_storage_keys=ls, final_url=page.url, verified=verified,
            )
        finally:
            browser.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="UI-login → storage_state capture for Agent 1 authenticated runs.")
    ap.add_argument("--url", required=True, help="login page URL")
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--out", required=True, help="output storage_state JSON path")
    ap.add_argument("--username-selector")
    ap.add_argument("--password-selector")
    ap.add_argument("--submit-selector")
    ap.add_argument("--success-url-contains")
    ap.add_argument("--wait-ms", type=int, default=4000)
    ap.add_argument("--ignore-https-errors", action="store_true")
    ap.add_argument("--headed", action="store_true", help="run with a visible browser")
    a = ap.parse_args()
    r = capture_login_session(
        a.url, a.user, a.password, a.out,
        username_selector=a.username_selector, password_selector=a.password_selector,
        submit_selector=a.submit_selector, success_url_contains=a.success_url_contains,
        wait_ms=a.wait_ms, ignore_https_errors=a.ignore_https_errors, headless=not a.headed,
    )
    print(json.dumps({
        "output_path": str(r.output_path), "cookies": r.cookies,
        "local_storage_keys": r.local_storage_keys, "final_url": r.final_url, "verified": r.verified,
    }, indent=2))


if __name__ == "__main__":
    main()
