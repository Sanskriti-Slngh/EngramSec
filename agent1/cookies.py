"""Cookie bridge between the browser context and the bounded passive reader.

The bounded reader runs outside Playwright, so it has no cookie jar of its
own. It must still act as the same authorized user agent as the browser:

* requests carry exactly the cookies the browser context would send to that
  URL (Playwright filters by domain, path and Secure);
* `Set-Cookie` in a passive response is applied to the browser context using
  the RFC 6265 storage model. A server that rotates or revokes a session on
  any request has already changed server-side state by the time the response
  arrives. Dropping the update would leave the browser holding an invalidated
  identifier.

Only cookie *names* are ever written to evidence; values are never recorded.
"""
from __future__ import annotations

import ipaddress
import re
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.parse import urlsplit

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
SAME_SITE = {"strict": "Strict", "lax": "Lax", "none": "None"}


@dataclass
class CookieUpdate:
    name: str
    value: str = ""
    domain: str = ""
    host_only: bool = True
    path: str = "/"
    expires: float | None = None  # None means a session cookie
    secure: bool = False
    http_only: bool = False
    same_site: str = "Lax"
    delete: bool = False
    reject_reason: str | None = None


def _default_path(url_path: str) -> str:
    """RFC 6265 section 5.1.4."""
    if not url_path.startswith("/") or url_path.count("/") <= 1:
        return "/"
    return url_path[: url_path.rfind("/")]


def _is_ip_or_local(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return host in LOCAL_HOSTS


def _domain_matches(host: str, domain: str) -> bool:
    """RFC 6265 section 5.1.3 (IP addresses only match exactly)."""
    if host == domain:
        return True
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        return host.endswith("." + domain)


def parse_set_cookie(header: str, request_url: str, now: float | None = None) -> CookieUpdate:
    """Parse one Set-Cookie header per RFC 6265 section 5.2 and 5.3."""
    now = time.time() if now is None else now
    parts = urlsplit(request_url)
    host = (parts.hostname or "").lower()
    pair, *attributes = header.split(";")
    if "=" not in pair:
        return CookieUpdate(name="", reject_reason="no_name_value_pair")
    name, value = (item.strip() for item in pair.split("=", 1))
    if not name:
        return CookieUpdate(name="", reject_reason="no_name_value_pair")
    cookie = CookieUpdate(name=name, value=value, domain=host, path=_default_path(parts.path or "/"))
    max_age: int | None = None
    expires: float | None = None
    domain_attr = ""
    for attribute in attributes:
        key, _, raw = attribute.partition("=")
        key, raw = key.strip().lower(), raw.strip()
        if key == "expires":
            try:
                expires = parsedate_to_datetime(raw).timestamp()
            except (TypeError, ValueError, IndexError):
                continue
        elif key == "max-age" and re.fullmatch(r"-?\d+", raw):
            max_age = int(raw)
        elif key == "domain" and raw:
            domain_attr = raw.lstrip(".").lower()
        elif key == "path":
            cookie.path = raw if raw.startswith("/") else _default_path(parts.path or "/")
        elif key == "secure":
            cookie.secure = True
        elif key == "httponly":
            cookie.http_only = True
        elif key == "samesite":
            cookie.same_site = SAME_SITE.get(raw.lower(), "Lax")
    if max_age is not None:  # Max-Age takes precedence over Expires
        cookie.expires = now + max_age if max_age > 0 else None
        cookie.delete = max_age <= 0
    elif expires is not None:
        cookie.expires = expires
        cookie.delete = expires <= now
    if domain_attr:
        if not _domain_matches(host, domain_attr):
            cookie.reject_reason = "domain_mismatch"
            return cookie
        # Chromium never stores a domain cookie for an IP literal or localhost.
        cookie.domain, cookie.host_only = domain_attr, domain_attr == host and _is_ip_or_local(host)
    if cookie.secure and parts.scheme != "https" and host not in LOCAL_HOSTS:
        cookie.reject_reason = "secure_from_insecure_origin"
    elif name.startswith("__Secure-") and not cookie.secure:
        cookie.reject_reason = "prefix_rules"
    elif name.startswith("__Host-") and (not cookie.secure or domain_attr or cookie.path != "/"):
        cookie.reject_reason = "prefix_rules"
    elif cookie.same_site == "None" and not cookie.secure:
        cookie.reject_reason = "samesite_none_without_secure"
    return cookie


def context_cookie_bridge(context: Any) -> tuple[Callable[[str], tuple[str | None, list[str]]],
                                                 Callable[[str, list[str]], dict[str, Any]]]:
    """Return (source, sink) bound to one Playwright browser context.

    source(url) -> (Cookie header or None, sorted cookie names).
    sink(url, set_cookie_headers) -> {"names": [...], "applied": n, "deleted": n, "rejected": {reason: n}}.
    """

    def source(url: str) -> tuple[str | None, list[str]]:
        cookies = context.cookies(url)
        # RFC 6265 section 5.4: longer paths first.
        cookies.sort(key=lambda item: -len(item.get("path") or "/"))
        header = "; ".join(f"{item['name']}={item['value']}" for item in cookies)
        return header or None, sorted({item["name"] for item in cookies})

    def sink(url: str, headers: list[str]) -> dict[str, Any]:
        outcome: dict[str, Any] = {"names": [], "applied": 0, "deleted": 0, "rejected": {}}
        additions = []
        for header in headers:
            update = parse_set_cookie(header, url)
            if update.name:
                outcome["names"].append(update.name)
            if update.reject_reason:
                outcome["rejected"][update.reject_reason] = outcome["rejected"].get(update.reject_reason, 0) + 1
                continue
            if update.delete:
                context.clear_cookies(name=update.name, path=update.path,
                                      domain=re.compile(r"^\.?" + re.escape(update.domain) + "$"))
                outcome["deleted"] += 1
                continue
            cookie = {"name": update.name, "value": update.value, "path": update.path,
                      "domain": update.domain if update.host_only else "." + update.domain,
                      "secure": update.secure, "httpOnly": update.http_only, "sameSite": update.same_site}
            if update.expires is not None:
                cookie["expires"] = update.expires
            additions.append(cookie)
        if additions:
            context.add_cookies(additions)
            outcome["applied"] = len(additions)
        outcome["names"] = sorted(set(outcome["names"]))
        return outcome

    return source, sink
