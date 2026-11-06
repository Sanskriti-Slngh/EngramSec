"""Request-level write policy for browser-issued requests.

Exploration permissions are enforced where requests leave the browser, not only on
HTML form attributes (a script can intercept a GET form and POST, or a button's
handler can call fetch with any method).

    read_only          every non-safe method (anything but GET/HEAD/OPTIONS) is aborted
    disposable         writes are allowed on an operator-attested disposable environment,
                       up to ``max_write_requests``; DELETE and destructive-looking routes are
                       still aborted unless ``allow_destructive``
    legacy_post_forms  historical allow_post_forms=True behaviour (no request-level gate);
                       kept only so earlier configurations reproduce exactly

Every decision on a write is logged (method, route shape, decision); no values or bodies.
Blocked requests fail with ``net::ERR_ACCESS_DENIED`` so evidence can tell a policy
block apart from a scope block (``ERR_BLOCKED_BY_CLIENT``).
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from .state import route_pattern

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
ABORT_CODE = "accessdenied"            # Chromium reports net::ERR_ACCESS_DENIED
DESTRUCTIVE_ROUTE = re.compile(
    r"(?:^|[/_.-])(?:delete|destroy|drop|truncate|wipe|purge|erase|remove[-_]?all|delete[-_]?all|clear[-_]?all|"
    r"reset|factory[-_]?reset|deactivate|terminate|shutdown|uninstall)(?:$|[/_.?-])", re.I)
MAX_LOG = 500


class WritePolicy:
    def __init__(self, mode: str, max_write_requests: int = 50, allow_destructive: bool = False):
        self.mode = mode
        self.max_write_requests = max_write_requests
        self.allow_destructive = allow_destructive
        self.stats: dict[str, Any] = {"mode": mode, "allowed": 0, "blocked_read_only": 0, "blocked_destructive": 0,
                                      "blocked_write_cap": 0, "log": []}

    @property
    def enforcing(self) -> bool:
        return self.mode in {"read_only", "disposable"}

    def decide(self, method: str, url: str) -> str:
        method = (method or "GET").upper()
        if method in SAFE_METHODS or not self.enforcing:
            return "allow"
        path = urlsplit(url).path or "/"
        if self.mode == "read_only":
            decision = "blocked_read_only"
        elif not self.allow_destructive and (method == "DELETE" or DESTRUCTIVE_ROUTE.search(path)):
            decision = "blocked_destructive"
        elif self.stats["allowed"] >= self.max_write_requests:
            decision = "blocked_write_cap"
        else:
            decision = "allowed"
        self.stats[decision] += 1
        if len(self.stats["log"]) < MAX_LOG:
            self.stats["log"].append({"method": method, "route": route_pattern(url).split("?")[0], "decision": decision})
        return "allow" if decision == "allowed" else "block"
