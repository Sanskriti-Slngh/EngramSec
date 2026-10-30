"""Bounded, passive extraction of URL references actually present in responses.

This module never guesses routes. Callers remain responsible for origin checks,
deduplication, fetch budgets, and recording whether a candidate was fetched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from .state import SENSITIVE_QUERY_KEYS, allowed_origin, compact_text


def _safe_resource_url(value: str) -> str:
    parts = urlsplit(value)
    safe_query = urlencode([(key, "<redacted>") for key, _ in parse_qsl(parts.query, keep_blank_values=True)])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, safe_query, ""))


MAX_REFERENCES_PER_RESPONSE = 250
MAX_TEXT_BYTES = 1_000_000
_URL_PATTERN = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I | re.S)
_IMPORT_PATTERN = re.compile(r"@import\s+(?:url\(\s*)?(['\"])(.*?)\1", re.I)
_MODULE_PATTERN = re.compile(
    r"\b(?:import|export)\s+(?:[^;'\"]*?\s+from\s*)?['\"]([^'\"]+)['\"]"
)
_DYNAMIC_IMPORT_PATTERN = re.compile(r"\bimport\s*\(\s*['\"]([^'\"]+)['\"]")
_CALL_REFERENCE_PATTERN = re.compile(r"(?:\bfetch|\bnew\s+URL)\s*\(\s*['\"]([^'\"]{1,512})['\"]")
_XHR_PATTERN = re.compile(r"\.open\s*\(\s*['\"][A-Z]+['\"]\s*,\s*['\"]([^'\"]{1,512})['\"]", re.I)
_REFRESH_PATTERN = re.compile(r"^\s*\d+(?:\.\d+)?\s*;\s*url\s*=\s*(['\"]?)(.*?)\1\s*$", re.I)


@dataclass(frozen=True)
class ResourceReference:
    url: str
    kind: str
    source_type: str
    source: str
    relation: str = ""


def _normalized(raw: str, base: str, *, kind: str, source_type: str, source: str, relation: str = "") -> ResourceReference | None:
    raw = (raw or "").strip().strip("\"'")
    if not raw or raw.startswith(("#", "data:", "blob:", "javascript:", "mailto:", "tel:", "about:")):
        return None
    try:
        resolved = urljoin(base, raw)
        parts = urlsplit(resolved)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            return None
        normalized = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, ""))
    except (ValueError, TypeError):
        return None
    return ResourceReference(normalized, kind, source_type, source[:200], relation[:80])


class _DocumentReferences(HTMLParser):
    def __init__(self, response_url: str):
        super().__init__(convert_charrefs=True)
        self.response_url = response_url
        self.base_url = response_url
        self.references: list[ResourceReference] = []
        self._base_seen = False
        self._raw_script = False
        self._raw_style = False

    def _add(self, raw: str, kind: str, tag: str, attr: str, relation: str = "") -> None:
        if len(self.references) >= MAX_REFERENCES_PER_RESPONSE:
            return
        item = _normalized(raw, self.base_url, kind=kind, source_type="html", source=f"<{tag}>[{attr}]", relation=relation)
        if item:
            self.references.append(item)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "base" and not self._base_seen and values.get("href"):
            self.base_url = urljoin(self.response_url, values["href"])
            self._base_seen = True
        rels = set(values.get("rel", "").lower().split())
        kind = "navigation" if tag in {"a", "area"} else "api" if tag == "form" else "asset"
        attrs_by_tag = {
            "a": ("href",), "area": ("href",), "link": ("href",),
            "img": ("src",), "script": ("src",), "iframe": ("src",), "frame": ("src",),
            "video": ("src", "poster"), "audio": ("src",), "source": ("src",),
            "track": ("src",), "embed": ("src",), "object": ("data",),
            "form": ("action",), "input": ("src", "formaction"),
            "button": ("formaction",), "blockquote": ("cite",), "q": ("cite",),
            "del": ("cite",), "ins": ("cite",),
        }
        for attr in attrs_by_tag.get(tag, ()):
            if values.get(attr):
                rel = " ".join(sorted(rels))
                actual_kind = (
                    "navigation"
                    if tag in {"a", "area"} or attr == "formaction" or rels.intersection({"canonical", "alternate", "next", "prev"})
                    else "api" if tag == "form" else "asset"
                )
                self._add(values[attr], actual_kind, tag, attr, rel)
        for attr in ("srcset", "imagesrcset"):
            if values.get(attr):
                for candidate in values[attr].split(",")[:32]:
                    raw = candidate.strip().split()[0] if candidate.strip() else ""
                    self._add(raw, "asset", tag, attr, "srcset")
        if values.get("style"):
            for match in _URL_PATTERN.finditer(values["style"][:8192]):
                self._add(match.group(2), "asset", tag, "style", "css-url")
        if tag == "meta" and values.get("http-equiv", "").lower() == "refresh":
            match = _REFRESH_PATTERN.match(values.get("content", ""))
            if match:
                self._add(match.group(2), "navigation", tag, "content", "refresh")
        if tag == "script":
            self._raw_script = not bool(values.get("src"))
        if tag == "style":
            self._raw_style = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._raw_script = False
        elif tag == "style":
            self._raw_style = False

    def handle_data(self, data: str) -> None:
        if self._raw_script:
            for item in extract_script_references(data[:MAX_TEXT_BYTES], self.base_url):
                if len(self.references) < MAX_REFERENCES_PER_RESPONSE:
                    self.references.append(item)
        elif self._raw_style:
            for item in extract_css_references(data[:MAX_TEXT_BYTES], self.base_url):
                if len(self.references) < MAX_REFERENCES_PER_RESPONSE:
                    self.references.append(item)


def extract_html_references(text: str, response_url: str) -> list[ResourceReference]:
    parser = _DocumentReferences(response_url)
    parser.feed((text or "")[:MAX_TEXT_BYTES])
    parser.close()
    return _dedupe(parser.references)


def extract_css_references(text: str, response_url: str) -> list[ResourceReference]:
    source = (text or "")[:MAX_TEXT_BYTES]
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    values: list[ResourceReference] = []
    for match in _URL_PATTERN.finditer(source):
        item = _normalized(match.group(2), response_url, kind="asset", source_type="css", source="url()")
        if item:
            values.append(item)
    for match in _IMPORT_PATTERN.finditer(source):
        item = _normalized(match.group(2), response_url, kind="asset", source_type="css", source="@import")
        if item:
            values.append(item)
    return _dedupe(values)


def extract_script_references(text: str, response_url: str, *, limit: int = 128) -> list[ResourceReference]:
    source = (text or "")[:MAX_TEXT_BYTES]
    candidates: list[tuple[str, str]] = []
    candidates.extend((match.group(1), "module-import") for match in _MODULE_PATTERN.finditer(source))
    candidates.extend((match.group(1), "module-import") for match in _DYNAMIC_IMPORT_PATTERN.finditer(source))
    candidates.extend((match.group(1), "observed-call-argument") for match in _CALL_REFERENCE_PATTERN.finditer(source))
    candidates.extend((match.group(1), "observed-call-argument") for match in _XHR_PATTERN.finditer(source))
    values: list[ResourceReference] = []
    for raw, evidence in candidates[:limit]:
        item = _normalized(raw, response_url, kind="api" if evidence == "observed-call-argument" else "asset", source_type="script", source=evidence)
        if item:
            values.append(item)
    return _dedupe(values)


def extract_header_references(headers: dict[str, str], response_url: str) -> list[ResourceReference]:
    values: list[ResourceReference] = []
    for key, header_value in headers.items():
        key = key.lower()
        if key == "location":
            item = _normalized(header_value, response_url, kind="navigation", source_type="header", source="Location")
            if item:
                values.append(item)
        elif key == "refresh":
            match = re.search(r"\burl\s*=\s*(['\"]?)(.*?)\1\s*$", header_value, re.I)
            if match:
                item = _normalized(match.group(2), response_url, kind="navigation", source_type="header", source="Refresh")
                if item:
                    values.append(item)
        elif key == "link":
            for part in re.findall(r"<([^>]+)>\s*((?:;[^,]*)?)", header_value[:16_000]):
                target, params = part
                rel_match = re.search(r"\brel\s*=\s*['\"]?([^;'\"]+)", params, re.I)
                rel = rel_match.group(1).strip().lower() if rel_match else "link"
                kind = "navigation" if rel in {"alternate", "canonical", "next", "prev"} else "asset"
                item = _normalized(target, response_url, kind=kind, source_type="header", source="Link", relation=rel)
                if item:
                    values.append(item)
    return _dedupe(values)


def extract_references(text: str, response_url: str, content_type: str, headers: dict[str, str] | None = None) -> list[ResourceReference]:
    media = (content_type or "").lower().split(";", 1)[0].strip()
    result = extract_header_references(headers or {}, response_url)
    if media in {"text/html", "application/xhtml+xml"}:
        result.extend(extract_html_references(text, response_url))
    elif media == "text/css":
        result.extend(extract_css_references(text, response_url))
    elif "javascript" in media or media in {"application/ecmascript", "text/ecmascript"}:
        result.extend(extract_script_references(text, response_url))
    return _dedupe(result)


def _dedupe(items: list[ResourceReference]) -> list[ResourceReference]:
    result: list[ResourceReference] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (item.url, item.kind, item.source_type)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result[:MAX_REFERENCES_PER_RESPONSE]


class ResourceBudget:
    """Run-scoped budget shared by browser contexts and replay sessions."""

    def __init__(self, limit: int):
        self.limit = limit
        self.attempted = 0


class TypedResourceSpider:
    def __init__(
        self,
        start_url: str,
        aliases: list[str],
        budget: ResourceBudget,
        max_depth: int,
        max_body_bytes: int,
    ):
        self.start_url = start_url
        self.aliases = aliases
        self.budget = budget
        self.max_depth = max_depth
        self.max_body_bytes = max_body_bytes
        self.queue: list[tuple[ResourceReference, str, int]] = []
        self.seen: set[str] = set()
        self.evidence: list[dict[str, object]] = []
        self._evidence_seen: set[tuple[object, ...]] = set()

    def _record(self, record: dict[str, object]) -> None:
        key = (
            record.get("url"), record.get("kind"), record.get("source_type"),
            record.get("source_url"), record.get("source"), record.get("relation"),
            record.get("depth"), record.get("status"), record.get("http_status"),
        )
        if key not in self._evidence_seen:
            self._evidence_seen.add(key)
            self.evidence.append(record)

    def observe_response(self, text: str, url: str, content_type: str, headers: dict[str, str]) -> None:
        for reference in extract_references(text, url, content_type, headers):
            safe_url = _safe_resource_url(reference.url)
            in_scope = allowed_origin(self.start_url, reference.url, self.aliases)
            sensitive = any(SENSITIVE_QUERY_KEYS.search(key) for key, _ in parse_qsl(urlsplit(reference.url).query))
            record: dict[str, object] = {
                "url": safe_url,
                "kind": reference.kind,
                "source_type": reference.source_type,
                "source_url": _safe_resource_url(url),
                "source": reference.source,
                "relation": reference.relation,
                "depth": 0,
                "status": "discovered",
            }
            if not in_scope:
                record["status"] = "out_of_scope"
            elif sensitive:
                record["status"] = "sensitive_reference"
            elif reference.kind != "api" and safe_url not in self.seen:
                self.seen.add(safe_url)
                self.queue.append((reference, url, 1))
            self._record(record)

    def fetch_pending(self, request_context: object) -> list[dict[str, object]]:
        fetched: list[dict[str, object]] = []
        while self.queue:
            reference, source_url, depth = self.queue.pop(0)
            if depth > self.max_depth:
                self._record({
                    "url": _safe_resource_url(reference.url), "kind": reference.kind,
                    "source_type": reference.source_type, "source_url": _safe_resource_url(source_url),
                    "source": reference.source, "relation": reference.relation,
                    "depth": depth, "status": "depth_limited",
                })
                continue
            if self.budget.attempted >= self.budget.limit:
                self._record({
                "url": _safe_resource_url(reference.url), "kind": reference.kind,
                "source_type": reference.source_type, "source_url": _safe_resource_url(source_url),
                    "source": reference.source, "relation": reference.relation,
                    "depth": depth, "status": "budget_limited",
                })
                continue
            if not allowed_origin(self.start_url, reference.url, self.aliases):
                continue
            if any(SENSITIVE_QUERY_KEYS.search(key) for key, _ in parse_qsl(urlsplit(reference.url).query)):
                continue
            self.budget.attempted += 1
            try:
                response = request_context.get(reference.url, timeout=5_000, max_redirects=0)  # type: ignore[attr-defined]
                headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
                content_type = headers.get("content-type", "")
                body_size = int(headers.get("content-length", "0") or 0)
                # Playwright buffers response.body() as a whole.  Require a
                # declared bounded length rather than pretending slicing the
                # returned bytes bounds memory use.
                body = (
                    response.body()
                    if 0 < body_size <= self.max_body_bytes
                    else b""
                )
                charset_match = re.search(r"charset\s*=\s*['\"]?([^;\s'\"]+)", content_type, re.I)
                encoding = charset_match.group(1) if charset_match else "utf-8"
                try:
                    text = body.decode(encoding, errors="replace")
                except LookupError:
                    text = body.decode("utf-8", errors="replace")
                final_url = response.url
                status = int(response.status)
                location = headers.get("location")
                redirect_target = urljoin(final_url, location) if location else None
                record = {
                    "url": _safe_resource_url(reference.url), "kind": reference.kind,
                    "source_type": reference.source_type, "source_url": _safe_resource_url(source_url),
                    "source": reference.source, "relation": reference.relation,
                    "depth": depth, "status": "fetched" if status < 400 else "failed",
                    "http_status": status, "content_type": content_type[:160],
                    "redirected_to": _safe_resource_url(redirect_target) if redirect_target else None,
                    "error": None if status < 400 else f"HTTP {status}",
                }
                if status < 400:
                    discovered = extract_references(text, final_url, content_type, headers)
                    for child in discovered:
                        safe = _safe_resource_url(child.url)
                        if safe in self.seen:
                            continue
                        self.seen.add(safe)
                        self._record({
                            "url": safe, "kind": child.kind,
                            "source_type": child.source_type,
                            "source_url": _safe_resource_url(final_url),
                            "source": child.source, "relation": child.relation,
                            "depth": depth, "status": "discovered",
                        })
                        if child.kind != "api" and depth < self.max_depth and allowed_origin(self.start_url, child.url, self.aliases):
                            if not any(SENSITIVE_QUERY_KEYS.search(key) for key, _ in parse_qsl(urlsplit(child.url).query)):
                                self.queue.append((child, final_url, depth + 1))
                self._record(record)
                fetched.append(record)
            except Exception as exc:
                record = {
                "url": _safe_resource_url(reference.url), "kind": reference.kind,
                "source_type": reference.source_type, "source_url": _safe_resource_url(source_url),
                    "source": reference.source, "relation": reference.relation,
                    "depth": depth, "status": "failed",
                    "error": type(exc).__name__,
                }
                self._record(record)
                fetched.append(record)
        drained = self.evidence
        self.evidence = []
        return drained
