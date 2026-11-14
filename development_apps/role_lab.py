"""Role-authorization fixture (development only; stdlib; genuine server-side enforcement).

Three permission contexts with REAL authorization checks (not cosmetic role labels), so an
authenticated-exploration experiment can measure what each role can actually reach:

- anonymous: the public catalog only (``/``, ``/catalog``, ``/item?id=N``).
- registered user (login required): ``/dashboard``, ``/orders``, ``/order/new`` (POST create),
  ``/profile`` (GET + POST update). Anonymous requests to these redirect (302) to ``/login``.
- administrator (admin role required): ``/admin``, ``/admin/users``, ``/admin/settings`` (POST),
  ``/admin/user/<id>/delete`` (POST, destructive). Non-admin requests to any ``/admin*`` get 403.

Authorization is enforced from the session cookie (``rolelab_session``) mapped to a seeded account,
never from anything the client asserts. Seeded-account passwords are generated at import time with
``secrets`` and kept only in process memory (``ACCOUNTS``); nothing secret is committed, and the agent
never receives them -- the harness provisions a session OUTSIDE the agent (see evaluation/auth_provision).

Ground truth for recall/precision:
- ``CAPABILITIES`` maps each capability key to the minimum role that may execute it.
- ``role_inventory(role)`` is the set of capability keys reachable by that role (monotonic: admin >= user
  >= anonymous), used as the per-role denominator.
- ``STATE.functions`` is the server-side ledger of capability keys actually executed during a run
  (the numerator). ``STATE.access_denied`` records every cross-role attempt the server refused.
"""
from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

# Seeded accounts. Passwords are random per process and live only here (never committed, never sent to
# the agent, never written to Graph A / the ACG / reports).
ACCOUNTS: dict[str, dict[str, str]] = {
    "ava": {"password": secrets.token_urlsafe(9), "role": "registered_user"},
    "iris": {"password": secrets.token_urlsafe(9), "role": "admin"},
}

# capability key -> minimum role required to execute it.
CAPABILITIES: dict[str, str] = {
    "catalog_browse": "anonymous",
    "item_view": "anonymous",
    "search_catalog": "anonymous",
    "dashboard_view": "registered_user",
    "orders_view": "registered_user",
    "order_create": "registered_user",
    "profile_view": "registered_user",
    "profile_update": "registered_user",
    "admin_panel_view": "admin",
    "admin_users_view": "admin",
    "admin_settings_update": "admin",
    "admin_user_delete": "admin",
}
_RANK = {"anonymous": 0, "registered_user": 1, "admin": 2}


def role_inventory(role: str) -> set[str]:
    """Capabilities reachable by `role` (monotonic by privilege)."""
    r = _RANK.get(role, 0)
    return {k for k, need in CAPABILITIES.items() if _RANK[need] <= r}


ITEMS = {1: "Harbor rope", 2: "Brass compass", 3: "Chart case", 4: "Signal lamp"}


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.sessions: dict[str, str] = {}           # token -> username
        self.functions: dict[str, int] = {}          # capability key -> times executed
        self.access_denied: list[dict] = []          # refused cross-role attempts
        self.orders: list[dict] = []
        self.settings = {"site_title": "Role Lab", "theme": "default"}
        self.profiles = {"ava": {"display_name": "Ava", "bio": "user"}}
        self.log: list[dict] = []
        self.users = dict(ACCOUNTS)

    def executed(self, key: str) -> None:
        with self.lock:
            self.functions[key] = self.functions.get(key, 0) + 1

    def denied(self, who: str, role: str, path: str) -> None:
        with self.lock:
            self.access_denied.append({"account": who, "role": role, "path": path})

    def snapshot(self) -> dict:
        with self.lock:
            return {"functions": dict(self.functions), "access_denied": list(self.access_denied),
                    "orders": len(self.orders), "settings": dict(self.settings)}


STATE = _State()


def _page(title: str, body: str) -> str:
    return (f"<!doctype html><html><head><title>{title}</title></head><body>"
            f"<nav aria-label='main'><a href='/'>Home</a> <a href='/catalog'>Catalog</a> "
            f"<a href='/dashboard'>Dashboard</a> <a href='/admin'>Admin</a></nav>"
            f"<main>{body}</main></body></html>")


class RoleLabHandler(BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        return

    # -------------------------------------------------- session / authorization
    def _account(self) -> tuple[str | None, str]:
        """(username, role) from the session cookie; ('', 'anonymous') when unauthenticated."""
        cookie = self.headers.get("Cookie", "")
        token = ""
        for part in cookie.split(";"):
            if part.strip().startswith("rolelab_session="):
                token = part.strip().split("=", 1)[1]
        with STATE.lock:
            user = STATE.sessions.get(token)
        if not user:
            return None, "anonymous"
        return user, ACCOUNTS.get(user, {}).get("role", "registered_user")

    def _send(self, body: str, status: int = 200, ctype: str = "text/html",
              cookie: str | None = None, location: str | None = None) -> None:
        raw = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        if location:
            self.send_header("Location", location)
        self.end_headers()
        self.wfile.write(raw)

    def _require(self, minimum: str, path: str) -> tuple[str | None, str] | None:
        """Enforce authorization. Returns (user, role) if allowed, else sends the refusal and returns None."""
        user, role = self._account()
        if _RANK[role] >= _RANK[minimum]:
            return user, role
        if minimum == "admin":
            STATE.denied(user or "anonymous", role, path)
            self._send(_page("Forbidden", "<h1>403</h1><p>Administrator access required.</p>"), status=403)
        else:
            STATE.denied(user or "anonymous", role, path)
            self._send("", status=302, location="/login")
        return None

    # -------------------------------------------------- routing
    def do_GET(self) -> None:
        parts = urlsplit(self.path)
        path, qs = parts.path, parse_qs(parts.query)
        with STATE.lock:
            STATE.log.append({"method": "GET", "path": path})

        if path == "/" or path == "/catalog":
            STATE.executed("catalog_browse")
            rows = "".join(f"<li><a href='/item?id={i}'>{n}</a></li>" for i, n in ITEMS.items())
            form = "<form action='/catalog' method='get'><input name='q' aria-label='search'>" \
                   "<button>Search</button></form>"
            if qs.get("q"):
                STATE.executed("search_catalog")
            return self._send(_page("Catalog", f"<h1>Catalog</h1>{form}<ul>{rows}</ul>"))
        if path == "/item":
            STATE.executed("item_view")
            iid = (qs.get("id") or ["1"])[0]
            name = ITEMS.get(int(iid) if iid.isdigit() else 0, "Unknown")
            return self._send(_page("Item", f"<h1>{name}</h1><a href='/catalog'>Back</a>"))
        if path == "/login":
            return self._send(_page("Login", "<h1>Sign in</h1><form action='/login' method='post'>"
                                     "<input name='username' aria-label='username'>"
                                     "<input name='password' type='password' aria-label='password'>"
                                     "<button>Log in</button></form>"))
        if path == "/logout":
            return self._send("", status=302, cookie="rolelab_session=; Max-Age=0", location="/")

        if path == "/dashboard":
            auth = self._require("registered_user", path)
            if not auth:
                return
            user, _ = auth
            STATE.executed("dashboard_view")
            return self._send(_page("Dashboard", f"<h1>Welcome {user}</h1>"
                                    "<a href='/orders'>Orders</a> <a href='/profile'>Profile</a> "
                                    "<a href='/order/new'>New order</a>"))
        if path == "/orders":
            auth = self._require("registered_user", path)
            if not auth:
                return
            STATE.executed("orders_view")
            with STATE.lock:
                mine = [o for o in STATE.orders if o["user"] == auth[0]]
            rows = "".join(f"<li>{o['item']}</li>" for o in mine) or "<li>No orders yet</li>"
            return self._send(_page("Orders", f"<h1>Your orders</h1><ul>{rows}</ul>"))
        if path == "/order/new":
            auth = self._require("registered_user", path)
            if not auth:
                return
            return self._send(_page("New order", "<form action='/order/new' method='post'>"
                                    "<input name='item' aria-label='item'><button>Place order</button></form>"))
        if path == "/profile":
            auth = self._require("registered_user", path)
            if not auth:
                return
            STATE.executed("profile_view")
            with STATE.lock:
                prof = STATE.profiles.get(auth[0], {"display_name": auth[0], "bio": ""})
            return self._send(_page("Profile", "<form action='/profile' method='post'>"
                                    f"<input name='display_name' aria-label='display name' value='{prof['display_name']}'>"
                                    f"<input name='bio' aria-label='bio' value='{prof['bio']}'>"
                                    "<button>Save</button></form>"))

        if path == "/admin":
            auth = self._require("admin", path)
            if not auth:
                return
            STATE.executed("admin_panel_view")
            return self._send(_page("Admin", "<h1>Admin panel</h1><a href='/admin/users'>Users</a> "
                                    "<a href='/admin/settings'>Settings</a>"))
        if path == "/admin/users":
            auth = self._require("admin", path)
            if not auth:
                return
            STATE.executed("admin_users_view")
            rows = "".join(
                f"<li>{u} ({a['role']}) <form action='/admin/user/{u}/delete' method='post' "
                f"style='display:inline'><button>Delete</button></form></li>" for u, a in STATE.users.items())
            return self._send(_page("Users", f"<h1>Users</h1><ul>{rows}</ul>"))
        if path == "/admin/settings":
            auth = self._require("admin", path)
            if not auth:
                return
            with STATE.lock:
                s = dict(STATE.settings)
            return self._send(_page("Settings", "<form action='/admin/settings' method='post'>"
                                    f"<input name='site_title' aria-label='site title' value='{s['site_title']}'>"
                                    "<button>Update</button></form>"))
        return self._send(_page("Not found", "<h1>404</h1>"), status=404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode() if length else ""
        form = {k: v[0] for k, v in parse_qs(raw).items()}
        path = urlsplit(self.path).path
        with STATE.lock:
            STATE.log.append({"method": "POST", "path": path})

        if path == "/login":
            user = form.get("username", "")
            pw = form.get("password", "")
            if user in ACCOUNTS and secrets.compare_digest(pw, ACCOUNTS[user]["password"]):
                token = secrets.token_hex(16)
                with STATE.lock:
                    STATE.sessions[token] = user
                return self._send("", status=302,
                                  cookie=f"rolelab_session={token}; Path=/; HttpOnly", location="/dashboard")
            return self._send(_page("Login", "<h1>Sign in</h1><p>Invalid credentials.</p>"
                                    "<form action='/login' method='post'>"
                                    "<input name='username' aria-label='username'>"
                                    "<input name='password' type='password' aria-label='password'>"
                                    "<button>Log in</button></form>"), status=401)

        if path == "/order/new":
            auth = self._require("registered_user", path)
            if not auth:
                return
            with STATE.lock:
                STATE.orders.append({"user": auth[0], "item": form.get("item", "unspecified")})
            STATE.executed("order_create")
            return self._send("", status=302, location="/orders")
        if path == "/profile":
            auth = self._require("registered_user", path)
            if not auth:
                return
            with STATE.lock:
                STATE.profiles[auth[0]] = {"display_name": form.get("display_name", auth[0]),
                                           "bio": form.get("bio", "")}
            STATE.executed("profile_update")
            return self._send("", status=302, location="/profile")

        if path == "/admin/settings":
            auth = self._require("admin", path)
            if not auth:
                return
            with STATE.lock:
                STATE.settings["site_title"] = form.get("site_title", STATE.settings["site_title"])
            STATE.executed("admin_settings_update")
            return self._send("", status=302, location="/admin/settings")
        if path.startswith("/admin/user/") and path.endswith("/delete"):
            auth = self._require("admin", path)
            if not auth:
                return
            target = path[len("/admin/user/"):-len("/delete")]
            with STATE.lock:
                STATE.users.pop(target, None)
            STATE.executed("admin_user_delete")
            return self._send("", status=302, location="/admin/users")
        return self._send(_page("Not found", "<h1>404</h1>"), status=404)


def start_role_lab(port: int = 0) -> tuple[ThreadingHTTPServer, str, _State]:
    STATE.reset()
    server = ThreadingHTTPServer(("127.0.0.1", port), RoleLabHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    return server, url, STATE


if __name__ == "__main__":
    srv, url, _ = start_role_lab(8077)
    print(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
