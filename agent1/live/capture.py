"""Opt-in, privacy-preserving evidence capture for the live ACG (`acg_evidence`).

Attached to the existing explorer through side channels only: with the option
off nothing here runs and legacy artifacts are unchanged. Raw values never
leave this process:
- query values, identifier values and JSON body values become per-run keyed
  tokens (HMAC-SHA256 with a random key that exists only in memory);
- request and response bodies are reduced to key-path skeleton digests;
- WebSocket payloads are reduced to a skeleton digest and a keyed token of
  their short top-level discriminator values;
- out-of-scope WebSocket connections are refused and only counted.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any
import re
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from agent1.model.routes import DISPATCH_VALUE, is_identifier

JSON_TYPES = ("application/json", "+json", "text/json")
UUID = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)
MAX_SKELETON_PATHS = 200


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def skeleton(value: Any, prefix: str = "$", out: list[str] | None = None, depth: int = 0) -> list[str]:
    """Key paths with JSON types, arrays collapsed to `[]`; never values."""
    out = [] if out is None else out
    if len(out) >= MAX_SKELETON_PATHS or depth > 12:
        return out
    if isinstance(value, dict):
        out.append(f"{prefix}:object")
        for key in sorted(value)[:64]:
            skeleton(value[key], f"{prefix}.{key}", out, depth + 1)
    elif isinstance(value, list):
        out.append(f"{prefix}:array")
        for item in value[:3]:
            skeleton(item, f"{prefix}[]", out, depth + 1)
    else:
        out.append(f"{prefix}:{type(value).__name__}")
    return sorted(set(out))


def _digest(items: list[str]) -> str:
    return hashlib.sha256("\n".join(items).encode()).hexdigest()[:16]


def ws_in_scope(start_url: str, ws_url: str, aliases: list[str] | None, allowed_origin) -> bool:
    parts = urlsplit(ws_url)
    scheme = {"ws": "http", "wss": "https"}.get(parts.scheme, parts.scheme)
    return allowed_origin(start_url, parts._replace(scheme=scheme).geturl(), aliases)


class EvidenceSink:
    def __init__(self, max_body_bytes: int = 262_144) -> None:
        self._key = os.urandom(32)            # per run, memory only
        self.max_body_bytes = max_body_bytes
        self.http: dict[int, dict[str, Any]] = {}
        self.disabled: dict[str, list[Any]] = {}
        self.ws_frames: list[dict[str, Any]] = []
        self.counters: Counter = Counter()

    def token(self, value: Any) -> str:
        return hmac.new(self._key, str(value).encode(), hashlib.sha256).hexdigest()[:16]

    # ------------------------------------------------------- pseudonymization
    def pseudo_value(self, value: str) -> str:
        """Format-preserving keyed pseudonym: equal inputs map to equal outputs within a run, and
        the identifier/dispatch class used by the ACG resolvers is preserved."""
        if not value:
            return value
        digest = hmac.new(self._key, value.encode(), hashlib.sha256).hexdigest()
        if value.isdigit():
            return str(int(digest[:12], 16) % 10**9 + 10**9)
        if UUID.match(value):
            d = digest
            return f"{d[:8]}-{d[8:12]}-{d[12:16]}-{d[16:20]}-{d[20:32]}"
        if is_identifier(value):
            return ("1" + digest)[:max(16, len(value))]
        return "v" + "".join("ghjkmnpqrstvwxyz"[int(c, 16)] for c in digest[:15])

    def pseudo_url(self, url: str | None) -> str | None:
        if not url:
            return url
        parts = urlsplit(url)
        path = "/".join(self.pseudo_value(seg) if is_identifier(seg) else seg for seg in parts.path.split("/"))
        query = "&".join(f"{k}={self.pseudo_value(v)}" for k, v in parse_qsl(parts.query, keep_blank_values=True))
        return urlunsplit((parts.scheme, parts.netloc, path, query, ""))

    # ------------------------------------------------------------------ http
    def _identifier_tokens(self, prefix: str, value: Any, out: list[str], depth: int = 0) -> None:
        if depth > 12 or len(out) >= 64:
            return
        if isinstance(value, dict):
            for key in sorted(value)[:64]:
                self._identifier_tokens(f"{prefix}.{key}", value[key], out, depth + 1)
        elif isinstance(value, list):
            for item in value[:50]:
                self._identifier_tokens(f"{prefix}[]", item, out, depth + 1)
        elif isinstance(value, (str, int)) and not isinstance(value, bool) and is_identifier(str(value)):
            out.append(f"{prefix}={self.token(value)}")

    def on_http(self, event: Any, request: Any, response: Any = None, body_reader=None) -> None:
        """Attach structure-only evidence to a NetworkEvent the legacy recorder created. Never raises."""
        try:
            self._on_http(event, request, response, body_reader)
        except Exception:
            self.counters["capture_errors"] += 1

    def _on_http(self, event: Any, request: Any, response: Any = None, body_reader=None) -> None:
        extra: dict[str, Any] = {"captured_at": _utc()}
        parts = urlsplit(request.url)
        ids: list[str] = []
        for i, seg in enumerate(s for s in parts.path.split("/") if s):
            if is_identifier(seg):
                ids.append(f"url#{i}={self.token(seg)}")
        query = parse_qsl(parts.query, keep_blank_values=True)
        extra["query_tokens"] = {name: self.token(value) for name, value in query
                                 if DISPATCH_VALUE.match(value) or is_identifier(value)}
        ids += [f"query.{name}={self.token(value)}" for name, value in query if is_identifier(value)]
        post = None
        try:
            post = request.post_data
        except Exception:                      # binary bodies
            post = None
        if post:
            try:
                body = json.loads(post)
                extra["request_shape"] = _digest(skeleton(body))
                self._identifier_tokens("req$", body, ids)
            except (ValueError, TypeError):
                pass
        if response is not None and request.resource_type in {"xhr", "fetch"}:
            ctype = (response.headers.get("content-type") or "").lower()
            extra["content_class"] = "json" if any(t in ctype for t in JSON_TYPES) else \
                "html" if "html" in ctype else "other"
            if extra["content_class"] == "json" and body_reader is not None:
                try:
                    raw, status = body_reader(response)
                except Exception:              # page or context already closed: evidence is simply missing
                    raw, status = b"", "unavailable"
                self.counters["body_" + status] += 1
                if raw:
                    try:
                        data = json.loads(raw.decode("utf-8", errors="replace"))
                        extra["response_shape"] = _digest(skeleton(data))
                        self._identifier_tokens("resp$", data, ids)
                    except ValueError:
                        self.counters["response_not_json"] += 1
        extra["id_tokens"] = ids
        self.http[id(event)] = extra
        self.counters["http_events"] += 1

    # ------------------------------------------------------------- websocket
    def on_ws_frame(self, url: str, direction: str, payload: Any) -> None:
        frame: dict[str, Any] = {"at": _utc(), "url_path": urlsplit(url).path or "/", "direction": direction}
        try:
            data = json.loads(payload if isinstance(payload, str) else payload.decode("utf-8", errors="replace"))
            frame["skeleton"] = _digest(skeleton(data))
            if isinstance(data, dict):
                disc = sorted(f"{k}={self.token(v)}" for k, v in data.items()
                              if isinstance(v, str) and DISPATCH_VALUE.match(v) and not is_identifier(v))
                frame["discriminator"] = _digest(disc) if disc else None
        except (ValueError, AttributeError):
            frame["skeleton"] = "non_json:" + ("text" if isinstance(payload, str) else "binary")
            frame["discriminator"] = None
        self.ws_frames.append(frame)
        self.counters["ws_frames_" + direction] += 1

    def attach_websocket(self, ws: Any, in_scope: bool) -> None:
        if not in_scope:
            self.counters["ws_out_of_scope_seen"] += 1
            return
        url = ws.url
        ws.on("framesent", lambda payload: self.on_ws_frame(url, "sent", payload))
        ws.on("framereceived", lambda payload: self.on_ws_frame(url, "received", payload))

    def summary(self) -> dict[str, Any]:
        return {"counters": dict(self.counters), "disabled_observations": len(self.disabled),
                "disabled_controls": sum(len(v) for v in self.disabled.values()), "ws_frames": len(self.ws_frames)}
