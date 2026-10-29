from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from .schema import Control, FormObservation, OutcomeSignal


SENSITIVE_QUERY_KEYS = re.compile(r"token|secret|password|passwd|auth|session|key|code", re.I)
INSTANCE_TOKEN = re.compile(
    r"(?<![A-Za-z])(?:\d+|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})(?![A-Za-z])",
    re.I,
)
WHITESPACE = re.compile(r"\s+")
COSMETIC_RUNTIME = re.compile(r"\b\d+\.\d{3,}s\b", re.I)
VOLATILE_CONTROL = re.compile(r"^(unnamed (button|link)|previous|next|prev|carousel)$", re.I)


def digest(value: object, length: int = 16) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


def compact_text(value: str, limit: int = 160) -> str:
    return WHITESPACE.sub(" ", value or "").strip()[:limit]


def normalize_instance_text(value: str) -> str:
    return INSTANCE_TOKEN.sub("{instance}", compact_text(value).lower())


def normalize_meaningful_text(value: str) -> str:
    """Normalize workflow content; DOM-marked cosmetics are removed at extraction."""

    return compact_text(COSMETIC_RUNTIME.sub("{runtime}", value).lower(), 8_000)


def content_fingerprint(value: str) -> str:
    return digest(normalize_meaningful_text(value))


def outcome_signature(signals: list[OutcomeSignal]) -> list[str]:
    return sorted(f"{item.kind}:{item.fingerprint}" for item in signals)


def sanitize_url(raw: str, base: str | None = None) -> str:
    resolved = urljoin(base or raw, raw)
    parts = urlsplit(resolved)
    safe_pairs: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        safe_pairs.append((key, "<redacted>" if SENSITIVE_QUERY_KEYS.search(key) else value[:120]))
    host = (parts.hostname or "").lower()
    if ":" in host:
        host = f"[{host}]"
    port = f":{parts.port}" if parts.port is not None else ""
    return urlunsplit((parts.scheme.lower(), host + port, parts.path or "/", urlencode(safe_pairs), ""))


def route_pattern(url: str) -> str:
    parts = urlsplit(url)
    path = INSTANCE_TOKEN.sub("{instance}", parts.path or "/")
    keys = sorted({key for key, _ in parse_qsl(parts.query, keep_blank_values=True)})
    return path + ("?" + "&".join(keys) if keys else "")


def same_origin(left: str, right: str) -> bool:
    return origin_tuple(left) == origin_tuple(right)


def origin_tuple(value: str) -> tuple[str, str, int]:
    part = urlsplit(value)
    port = part.port
    if port is None:
        port = 443 if part.scheme == "https" else 80
    return part.scheme.lower(), (part.hostname or "").lower(), port


def allowed_origin(start: str, target: str, aliases: list[str] | None = None) -> bool:
    allowed = {origin_tuple(start)}
    allowed.update(origin_tuple(item) for item in aliases or [])
    return origin_tuple(target) in allowed


def control_signature(
    kind: str,
    role: str,
    label: str,
    target: str | None,
    method: str | None,
    interaction: str = "click",
    component: str = "document",
) -> str:
    target_pattern = route_pattern(target) if target else ""
    return digest(
        {
            "kind": kind,
            "role": role,
            "label": normalize_instance_text(label),
            "target": target_pattern,
            "method": (method or "").upper(),
            "interaction": interaction,
            "component": component,
        }
    )


def group_control_signature(control: Control) -> str:
    """Functional control shape used only for reversible grouping.

    Link instance labels are retained in raw observations but omitted here when
    their target route shape is the same. Meaningful button labels stay part of
    the group because they often encode workflow semantics.
    """

    label = "" if control.kind == "link" else normalize_instance_text(control.label)
    return digest(
        {
            "kind": control.kind,
            "role": control.role,
            "label": label,
            "target": route_pattern(control.target) if control.target else "",
            "method": (control.method or "").upper(),
            "fields": [(field.name, field.input_type, field.required) for field in control.fields],
            "interaction": control.interaction,
            "component": control.component,
            "frame": route_pattern(control.frame_url) if control.frame_url else "",
        }
    )


def feature_action_signature(control: object) -> str:
    kind = getattr(control, "kind")
    target = getattr(control, "target", None)
    role = getattr(control, "role")
    method = getattr(control, "method", None)
    label = getattr(control, "label")
    fields = getattr(control, "fields", [])
    interaction = getattr(control, "interaction", "click")
    component = getattr(control, "component", "document")
    frame_url = getattr(control, "frame_url", "")
    return digest(
        {
            "kind": kind,
            "role": role,
            "target": route_pattern(target) if target else "",
            "method": (method or "").upper(),
            "label": "" if kind == "link" and target else normalize_instance_text(label),
            "fields": [(field.name, field.input_type, field.required) for field in fields],
            "interaction": interaction,
            "component": component,
            "frame": route_pattern(frame_url) if frame_url else "",
        }
    )


def signatures(
    *,
    url: str,
    title: str,
    controls: list[Control],
    forms: list[FormObservation],
    session_context: str,
    session_markers: dict[str, list[str]] | None = None,
    meaningful_text: str = "",
) -> tuple[str, str, str]:
    pattern = route_pattern(url)
    form_shapes = [
        {
            "method": form.method,
            "action": route_pattern(form.action),
            "fields": [(field.name, field.input_type, field.required) for field in form.fields],
        }
        for form in forms
    ]
    control_shapes = sorted(control.signature for control in controls if control.safe)
    content = content_fingerprint(meaningful_text)
    grouped_control_shapes = sorted(
        group_control_signature(control)
        for control in controls
        if control.safe and not VOLATILE_CONTROL.match(control.label)
    )
    raw = digest(
        {
            "url": url,
            "title": compact_text(title),
            "controls": control_shapes,
            "forms": form_shapes,
            "session": session_context,
            "session_markers": session_markers or {},
            "content": content,
        }
    )
    group = digest(
        {
            "route": pattern,
            "controls": grouped_control_shapes,
            "forms": form_shapes,
            "session": session_context,
            "session_markers": session_markers or {},
            "content": content,
        }
    )
    return raw, group, pattern


def feature_key(action_signature: str, outcome_signature: str = "") -> str:
    """Identify a workflow without recounting a repeated site-wide link."""

    return digest([action_signature, outcome_signature])
