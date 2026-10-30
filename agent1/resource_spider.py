"""Bounded, passive extraction of URL references actually present in responses.

This module never guesses routes. Callers remain responsible for origin checks,
deduplication, fetch budgets, and recording whether a candidate was fetched.
"""

from __future__ import annotations

import re
import random
import ast
import json
import xml.etree.ElementTree as ET
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from collections import defaultdict
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from tree_sitter import Language, Parser
import tree_sitter_javascript

from .state import SENSITIVE_QUERY_KEYS, allowed_origin, compact_text, digest


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
    confidence: str = "observed_literal"


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
            "applet": ("code", "codebase", "archive"), "param": ("value",),
            "table": ("background",), "image": ("href", "xlink:href"),
            "use": ("href", "xlink:href"),
        }
        for attr in attrs_by_tag.get(tag, ()):
            if values.get(attr):
                rel = " ".join(sorted(rels))
                actual_kind = (
                    "navigation"
                    if tag in {"a", "area"} or attr == "formaction" or rels.intersection({"canonical", "alternate", "next", "prev"})
                    else "navigation" if rels.intersection({"sitemap"})
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
        if tag == "meta" and values.get("name", "").lower() == "msapplication-config":
            self._add(values.get("content", ""), "asset", tag, "content", "msapplication-config")
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
    parser = Parser(Language(tree_sitter_javascript.language()))
    root = parser.parse(source.encode("utf-8", errors="replace")).root_node
    constants: dict[str, str] = {}
    element_types: dict[str, str] = {}

    def children(node: object) -> list[object]:
        return list(getattr(node, "children", []))

    def node_text(node: object) -> str:
        return getattr(node, "text", b"").decode("utf-8", errors="replace")

    def literal(node: object | None) -> str | None:
        if node is None:
            return None
        kind = getattr(node, "type", "")
        raw = node_text(node)
        if kind == "string":
            try:
                return ast.literal_eval(raw)
            except (SyntaxError, ValueError):
                return None
        if kind == "template_string" and not any(child.type == "template_substitution" for child in children(node)):
            content = raw[1:-1]
            try:
                return bytes(content, "utf-8").decode("unicode_escape")
            except UnicodeDecodeError:
                return content
        if kind == "identifier" and raw in constants:
            return constants[raw]
        if kind == "binary_expression":
            parts = children(node)
            if len(parts) >= 3 and node_text(parts[1]).strip() == "+":
                left = literal(parts[0])
                right = literal(parts[2])
                if left is not None and right is not None and len(left) + len(right) <= 2048:
                    return left + right
        if kind == "new_expression":
            constructor = getattr(node, "child_by_field_name")("constructor")
            args = getattr(node, "child_by_field_name")("arguments")
            arg_nodes = [child for child in children(args) if getattr(child, "type", "") not in {"(", ")", ","}] if args else []
            if node_text(constructor) == "URL" and arg_nodes:
                return literal(arg_nodes[0])
        return None

    def walk(node: object):
        yield from _walk_nodes(node)

    # Resolve only immutable, local constant strings. This is intentionally not
    # a general interpreter and never executes delivered JavaScript.
    for node in walk(root):
        if getattr(node, "type", "") == "variable_declarator":
            name = getattr(node, "child_by_field_name")("name")
            value = getattr(node, "child_by_field_name")("value")
            if name is not None and value is not None:
                resolved = literal(value)
                if resolved is not None:
                    constants[node_text(name)] = resolved
                if getattr(value, "type", "") == "call_expression":
                    fn = getattr(value, "child_by_field_name")("function")
                    args = getattr(value, "child_by_field_name")("arguments")
                    arg_nodes = [child for child in children(args) if getattr(child, "type", "") not in {"(", ")", ","}] if args else []
                    if node_text(fn) == "document.createElement" and arg_nodes:
                        tag = literal(arg_nodes[0])
                        if tag:
                            element_types[node_text(name)] = tag.lower()

    candidates: list[tuple[str, str, str]] = []
    tags_by_attr = {
        "src": {"script", "img", "iframe", "frame", "audio", "video", "source", "track", "embed"},
        "href": {"link", "a", "area", "image", "use", "script"},
        "poster": {"video"},
        "data": {"object"},
    }
    for node in walk(root):
        kind = getattr(node, "type", "")
        if kind in {"import_statement", "export_statement"}:
            value = getattr(node, "child_by_field_name")("source")
            raw = literal(value)
            if raw:
                candidates.append((raw, "asset", "module-import"))
        elif kind == "call_expression":
            fn = getattr(node, "child_by_field_name")("function")
            args = getattr(node, "child_by_field_name")("arguments")
            if args is None:
                continue
            arg_nodes = [child for child in children(args) if getattr(child, "type", "") not in {"(", ")", ","}]
            if not arg_nodes:
                continue
            name = node_text(fn)
            if getattr(fn, "type", "") == "import" or name == "import":
                raw = literal(arg_nodes[0])
                if raw:
                    candidates.append((raw, "asset", "dynamic-import"))
            elif name in {"fetch", "Request", "window.open", "open", "location.assign", "location.replace"}:
                raw = literal(arg_nodes[0])
                if raw:
                    candidate_kind = "navigation" if name in {"window.open", "open", "location.assign", "location.replace"} else "api"
                    candidates.append((raw, candidate_kind, f"call:{name}"))
            elif name.endswith(".open") and len(arg_nodes) >= 2:
                raw = literal(arg_nodes[1])
                if raw:
                    candidates.append((raw, "api", "call:xhr.open"))
            elif name.endswith(".setAttribute") and len(arg_nodes) >= 2:
                attr, raw = literal(arg_nodes[0]), literal(arg_nodes[1])
                receiver = node_text(getattr(fn, "child_by_field_name")("object"))
                tag = element_types.get(receiver, "")
                if attr and raw and attr.lower() in {key for key, valid_tags in tags_by_attr.items() if tag in valid_tags}:
                    candidates.append((raw, "asset", f"dynamic-element:{tag}.{attr.lower()}"))
        elif kind == "new_expression":
            constructor = getattr(node, "child_by_field_name")("constructor")
            args = getattr(node, "child_by_field_name")("arguments")
            arg_nodes = [child for child in children(args) if getattr(child, "type", "") not in {"(", ")", ","}] if args else []
            if node_text(constructor) == "Request" and arg_nodes:
                raw = literal(arg_nodes[0])
                if raw:
                    candidates.append((raw, "api", "new:Request"))
            elif node_text(constructor) == "URL" and arg_nodes:
                parent = getattr(node, "parent", None)
                enclosing = getattr(parent, "parent", None) if parent is not None else None
                enclosing_fn = (
                    getattr(enclosing, "child_by_field_name")("function")
                    if enclosing is not None and getattr(enclosing, "type", "") == "call_expression"
                    else None
                )
                if node_text(enclosing_fn) in {"fetch", "Request"}:
                    continue
                raw = literal(arg_nodes[0])
                if raw:
                    candidates.append((raw, "asset", "new:URL"))
        elif kind == "assignment_expression":
            left = getattr(node, "child_by_field_name")("left")
            right = getattr(node, "child_by_field_name")("right")
            raw = literal(right)
            if raw and getattr(left, "type", "") == "member_expression":
                obj = node_text(getattr(left, "child_by_field_name")("object"))
                prop = node_text(getattr(left, "child_by_field_name")("property"))
                if prop == "location" and obj in {"location", "window", "document"} or prop == "href" and "location" in obj:
                    candidates.append((raw, "navigation", f"assignment:{obj}.{prop}"))
                elif obj in element_types and prop in tags_by_attr and element_types[obj] in tags_by_attr[prop]:
                    candidates.append((raw, "asset", f"dynamic-element:{element_types[obj]}.{prop}"))

    result: list[ResourceReference] = []
    for raw, ref_kind, evidence in candidates[:limit]:
        item = _normalized(raw, response_url, kind=ref_kind, source_type="script-ast", source=evidence)
        if item:
            result.append(item)
    return _dedupe(result)


def extract_uncertain_script_candidates(text: str, response_url: str, *, limit: int = 64) -> list[dict[str, str | None]]:
    """Record dynamic request/navigation expressions without fabricating URLs."""
    source = (text or "")[:MAX_TEXT_BYTES]
    parser = Parser(Language(tree_sitter_javascript.language()))
    root = parser.parse(source.encode("utf-8", errors="replace")).root_node

    def children(node: object) -> list[object]:
        return list(getattr(node, "children", []))

    def text_of(node: object) -> str:
        return getattr(node, "text", b"").decode("utf-8", errors="replace")

    constants: dict[str, str] = {}
    for node in (item for item in _walk_nodes(root) if getattr(item, "type", "") == "variable_declarator"):
        name = getattr(node, "child_by_field_name")("name")
        value = getattr(node, "child_by_field_name")("value")
        if name is not None and value is not None and getattr(value, "type", "") == "string":
            try:
                constants[text_of(name)] = ast.literal_eval(text_of(value))
            except (SyntaxError, ValueError):
                pass

    def static(node: object | None) -> str | None:
        if node is None:
            return None
        if getattr(node, "type", "") == "string":
            try:
                return ast.literal_eval(text_of(node))
            except (SyntaxError, ValueError):
                return None
        if getattr(node, "type", "") == "identifier":
            return constants.get(text_of(node))
        if getattr(node, "type", "") == "binary_expression":
            parts = children(node)
            if len(parts) >= 3 and text_of(parts[1]).strip() == "+":
                left, right = static(parts[0]), static(parts[2])
                if left is not None and right is not None:
                    return left + right
        if getattr(node, "type", "") == "new_expression":
            constructor = getattr(node, "child_by_field_name")("constructor")
            args = getattr(node, "child_by_field_name")("arguments")
            values = [child for child in children(args) if getattr(child, "type", "") not in {"(", ")", ","}] if args else []
            if text_of(constructor) == "URL" and values:
                return static(values[0])
        return None

    def prefix(node: object) -> str | None:
        kind = getattr(node, "type", "")
        if kind == "template_string":
            raw = text_of(node)[1:-1]
            return raw.split("${", 1)[0][:80] or None
        if kind == "binary_expression":
            parts = children(node)
            if parts:
                value = static(parts[0])
                return value[:80] if value else None
        return None

    candidates: list[dict[str, str | None]] = []
    for node in _walk_nodes(root):
        kind = getattr(node, "type", "")
        target = None
        call = ""
        candidate_kind = "api"
        if kind == "call_expression":
            fn = getattr(node, "child_by_field_name")("function")
            args = getattr(node, "child_by_field_name")("arguments")
            if args is None:
                continue
            arg_nodes = [child for child in children(args) if getattr(child, "type", "") not in {"(", ")", ","}]
            name = text_of(fn)
            if name in {"fetch", "Request"} and arg_nodes:
                target, call = arg_nodes[0], f"call:{name}"
            elif name.endswith(".open") and len(arg_nodes) >= 2:
                target, call = arg_nodes[1], "call:xhr.open"
            elif name in {"location.assign", "location.replace", "window.open", "open"} and arg_nodes:
                target, call, candidate_kind = arg_nodes[0], f"call:{name}", "navigation"
        elif kind == "assignment_expression":
            left = getattr(node, "child_by_field_name")("left")
            right = getattr(node, "child_by_field_name")("right")
            left_text = text_of(left)
            if any(token in left_text for token in ("location", ".href")):
                target, call, candidate_kind = right, "assignment:navigation", "navigation"
        if target is None or static(target) is not None:
            continue
        shape = getattr(target, "type", "expression")
        raw_prefix = prefix(target)
        if raw_prefix and ("?" in raw_prefix or "#" in raw_prefix):
            raw_prefix = raw_prefix.split("?", 1)[0].split("#", 1)[0]
        fingerprint = digest([response_url, call, shape, raw_prefix], 20)
        candidates.append({
            "kind": candidate_kind,
            "source": call,
            "expression_fingerprint": fingerprint,
            "candidate_prefix": raw_prefix,
            "confidence": "low",
        })
        if len(candidates) >= limit:
            break
    return candidates


def _walk_nodes(node: object):
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(getattr(current, "children", [])))


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


def extract_manifest_references(text: str, response_url: str) -> list[ResourceReference]:
    try:
        manifest = json.loads((text or "")[:MAX_TEXT_BYTES])
    except (TypeError, ValueError):
        return []
    result: list[ResourceReference] = []
    if isinstance(manifest, dict):
        for key in ("start_url", "scope"):
            raw = manifest.get(key)
            if isinstance(raw, str):
                item = _normalized(raw, response_url, kind="navigation", source_type="manifest", source=key)
                if item:
                    result.append(item)
        for entry in manifest.get("icons", []) + manifest.get("screenshots", []):
            if isinstance(entry, dict) and isinstance(entry.get("src"), str):
                item = _normalized(entry["src"], response_url, kind="asset", source_type="manifest", source="icon-or-screenshot")
                if item:
                    result.append(item)
    return _dedupe(result)


def extract_xml_references(text: str, response_url: str) -> list[ResourceReference]:
    source = (text or "")[:MAX_TEXT_BYTES]
    try:
        root = ET.fromstring(source)
    except ET.ParseError:
        return []
    result: list[ResourceReference] = []
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1].lower() if isinstance(element.tag, str) else ""
        value = (element.text or "").strip()
        if tag in {"loc", "url", "link", "href"} and value:
            item = _normalized(value, response_url, kind="navigation", source_type="xml", source=tag)
            if item:
                result.append(item)
        for attr, raw in element.attrib.items():
            if attr.rsplit("}", 1)[-1].lower() in {"href", "src"}:
                item = _normalized(raw, response_url, kind="asset", source_type="xml", source=f"{tag}[{attr}]")
                if item:
                    result.append(item)
    return _dedupe(result)


def extract_robots_sitemaps(text: str, response_url: str) -> list[ResourceReference]:
    result: list[ResourceReference] = []
    for line in (text or "")[:MAX_TEXT_BYTES].splitlines():
        match = re.match(r"\s*sitemap\s*:\s*(\S+)\s*$", line, re.I)
        if match:
            item = _normalized(match.group(1), response_url, kind="navigation", source_type="robots", source="Sitemap:")
            if item:
                result.append(item)
    return _dedupe(result)


def _extract_script_references_regex(text: str, response_url: str) -> list[ResourceReference]:
    source = (text or "")[:MAX_TEXT_BYTES]
    candidates: list[tuple[str, str]] = []
    candidates.extend((match.group(1), "module-import") for match in _MODULE_PATTERN.finditer(source))
    candidates.extend((match.group(1), "module-import") for match in _DYNAMIC_IMPORT_PATTERN.finditer(source))
    candidates.extend((match.group(1), "observed-call-argument") for match in _CALL_REFERENCE_PATTERN.finditer(source))
    candidates.extend((match.group(1), "observed-call-argument") for match in _XHR_PATTERN.finditer(source))
    values: list[ResourceReference] = []
    for raw, evidence in candidates[:128]:
        item = _normalized(
            raw, response_url,
            kind="api" if evidence == "observed-call-argument" else "asset",
            source_type="script", source=evidence,
        )
        if item:
            values.append(item)
    return _dedupe(values)


def extract_references(
    text: str,
    response_url: str,
    content_type: str,
    headers: dict[str, str] | None = None,
    javascript_parser: str = "ast",
) -> list[ResourceReference]:
    media = (content_type or "").lower().split(";", 1)[0].strip()
    result = extract_header_references(headers or {}, response_url)
    if media in {"text/html", "application/xhtml+xml", "image/svg+xml"}:
        result.extend(extract_html_references(text, response_url))
    elif media == "text/css":
        result.extend(extract_css_references(text, response_url))
    elif "javascript" in media or media in {"application/ecmascript", "text/ecmascript"}:
        result.extend(
            _extract_script_references_regex(text, response_url)
            if javascript_parser == "legacy_regex"
            else extract_script_references(text, response_url)
        )
    elif media in {"application/manifest+json", "application/json"}:
        result.extend(extract_manifest_references(text, response_url))
    elif media in {"application/xml", "text/xml", "application/rss+xml", "application/atom+xml"}:
        result.extend(extract_xml_references(text, response_url))
    elif media.startswith("text/") and "robots.txt" in urlsplit(response_url).path.lower():
        result.extend(extract_robots_sitemaps(text, response_url))
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

    def __init__(self, limit: int, per_class_limits: dict[str, int | None] | None = None):
        self.limit = limit
        self.per_class_limits = per_class_limits or {}
        self.attempted = 0
        self.attempted_by_class: defaultdict[str, int] = defaultdict(int)
        self.new_references = 0
        self.responses = 0

    def remaining(self, candidate_class: str) -> bool:
        class_limit = self.per_class_limits.get(candidate_class)
        return (
            self.attempted < self.limit
            and (class_limit is None or self.attempted_by_class[candidate_class] < class_limit)
        )

    def consume(self, candidate_class: str) -> bool:
        if not self.remaining(candidate_class):
            return False
        self.attempted += 1
        self.attempted_by_class[candidate_class] += 1
        return True


class TypedResourceSpider:
    def __init__(
        self,
        start_url: str,
        aliases: list[str],
        budget: ResourceBudget,
        max_depth: int,
        max_body_bytes: int,
        frontier_policy: str = "fifo",
        random_seed: int = 0,
        class_budgets: dict[str, int | None] | None = None,
        javascript_parser: str = "ast",
    ):
        self.start_url = start_url
        self.aliases = aliases
        self.budget = budget
        self.max_depth = max_depth
        self.max_body_bytes = max_body_bytes
        self.started_monotonic = time.monotonic()
        if class_budgets:
            self.budget.per_class_limits.update(class_budgets)
        if javascript_parser not in {"legacy_regex", "ast"}:
            raise ValueError(f"unknown JavaScript reference parser: {javascript_parser}")
        self.javascript_parser = javascript_parser
        if frontier_policy not in {"fifo", "route_diverse", "marginal_value", "random"}:
            raise ValueError(f"unknown resource frontier policy: {frontier_policy}")
        self.frontier_policy = frontier_policy
        self._random = random.Random(random_seed)
        self.queue: list[tuple[ResourceReference, str, int]] = []
        self.seen: set[str] = set()
        self.discovered_urls: set[str] = set()
        self.fetched: set[str] = set()
        self._fetched_routes: set[str] = set()
        self._fetched_classes: set[str] = set()
        self._yield_by_class: defaultdict[str, list[int]] = defaultdict(lambda: [0, 0])
        self.evidence: list[dict[str, object]] = []
        self._evidence_seen: set[tuple[object, ...]] = set()

    def _record(self, record: dict[str, object]) -> None:
        record.setdefault("elapsed_ms", int((time.monotonic() - self.started_monotonic) * 1_000))
        key = (
            record.get("url"), record.get("kind"), record.get("source_type"),
            record.get("source_url"), record.get("source"), record.get("relation"),
            record.get("depth"), record.get("status"), record.get("http_status"),
            record.get("expression_fingerprint"),
        )
        if key not in self._evidence_seen:
            self._evidence_seen.add(key)
            self.evidence.append(record)

    def restore_from_evidence(self, items: list[dict[str, object]]) -> None:
        """Rebuild the frontier after checkpoint resume from evidence only."""
        fetched_urls: set[str] = set()
        for item in items:
            raw_url = item.get("url")
            if not isinstance(raw_url, str) or not raw_url:
                continue
            safe_url = _safe_resource_url(raw_url)
            self.discovered_urls.add(safe_url)
            reference = ResourceReference(
                url=raw_url,
                kind=str(item.get("kind", "asset")),
                source_type=str(item.get("source_type", "unknown")),
                source=str(item.get("source", "")),
                relation=str(item.get("relation", "")),
                confidence=str(item.get("confidence", "observed_literal")),
            )
            status = item.get("status")
            if status in {"fetched", "failed"}:
                fetched_urls.add(safe_url)
                self.seen.add(safe_url)
                self.fetched.add(safe_url)
                candidate_class = str(item.get("candidate_class") or self._candidate_class(reference))
                self._fetched_classes.add(candidate_class)
                self._fetched_routes.add(self._route_bucket(reference))
                value = item.get("new_references")
                if value is not None:
                    totals = self._yield_by_class[candidate_class]
                    totals[0] += int(value)
                    totals[1] += 1
            elif (
                item.get("queue_decision") == "admitted"
                and allowed_origin(self.start_url, raw_url, self.aliases)
                and not urlsplit(raw_url).query
                and safe_url not in self.seen
            ):
                self.seen.add(safe_url)
                source_url = item.get("source_url")
                if isinstance(source_url, str):
                    self.queue.append((reference, source_url, max(1, int(item.get("depth", 0)) + 1)))
        self.budget.attempted = len(fetched_urls)
        self.budget.attempted_by_class.clear()
        class_urls: set[tuple[str, str]] = set()
        for item in items:
            if item.get("status") in {"fetched", "failed"} and isinstance(item.get("url"), str):
                candidate = ResourceReference(
                    url=str(item["url"]), kind=str(item.get("kind", "asset")),
                    source_type=str(item.get("source_type", "unknown")),
                    source=str(item.get("source", "")), relation=str(item.get("relation", "")),
                )
                class_urls.add((self._candidate_class(candidate), _safe_resource_url(candidate.url)))
        for candidate_class, _url in class_urls:
            self.budget.attempted_by_class[candidate_class] += 1

    @staticmethod
    def _route_bucket(reference: ResourceReference) -> str:
        parts = urlsplit(reference.url)
        segments = [segment for segment in parts.path.split("/") if segment]
        return "/" + segments[0] if segments else "/"

    @staticmethod
    def _candidate_class(reference: ResourceReference) -> str:
        path = urlsplit(reference.url).path.lower()
        suffix = path.rsplit("/", 1)[-1].rsplit(".", 1)[-1] if "." in path.rsplit("/", 1)[-1] else ""
        if reference.kind == "navigation" or not suffix:
            return "document"
        if suffix in {"html", "htm", "xhtml", "php", "asp", "aspx"}:
            return "document"
        if suffix in {"js", "mjs", "cjs"}:
            return "script"
        if suffix == "css":
            return "stylesheet"
        return "other_asset"

    def _marginal_value(self, queued: tuple[ResourceReference, str, int]) -> float:
        reference, _source_url, depth = queued
        candidate_class = self._candidate_class(reference)
        # Priors express only expected reference yield for a response class,
        # not benchmark relevance. They are updated from observed child refs.
        priors = {"document": 5.0, "script": 3.0, "stylesheet": 1.5, "other_asset": 0.15}
        total, count = self._yield_by_class[candidate_class]
        estimate = (priors[candidate_class] + total) / (1 + count)
        route_novelty = 1.5 if self._route_bucket(reference) not in self._fetched_routes else 1.0
        class_novelty = 1.2 if candidate_class not in self._fetched_classes else 1.0
        return estimate * route_novelty * class_novelty / (1 + max(0, depth - 1) * 0.1)

    def _pop_next(self) -> tuple[ResourceReference, str, int]:
        if self.frontier_policy == "fifo":
            return self.queue.pop(0)
        if self.frontier_policy == "random":
            return self.queue.pop(self._random.randrange(len(self.queue)))
        if self.frontier_policy == "route_diverse":
            index = max(
                range(len(self.queue)),
                key=lambda item: (
                    self._route_bucket(self.queue[item][0]) not in self._fetched_routes,
                    self._candidate_class(self.queue[item][0]) not in self._fetched_classes,
                    self.queue[item][2] == 1,
                    -item,
                ),
            )
            return self.queue.pop(index)
        index = max(
            range(len(self.queue)),
            key=lambda item: (self._marginal_value(self.queue[item]), -item),
        )
        return self.queue.pop(index)

    def _update_unattempted_status(
        self, reference: ResourceReference, source_url: str, depth: int, status: str
    ) -> None:
        safe_url = _safe_resource_url(reference.url)
        safe_source = _safe_resource_url(source_url)
        for item in reversed(self.evidence):
            if (
                item.get("url") == safe_url
                and item.get("source_url") == safe_source
                and item.get("status") == "discovered"
            ):
                item["depth"] = depth
                item["status"] = status
                item["queue_decision"] = status
                return
        self._record({
            "url": safe_url, "kind": reference.kind,
            "source_type": reference.source_type, "source_url": safe_source,
            "source": reference.source, "relation": reference.relation,
            "depth": depth, "status": status,
            "queue_decision": status, "confidence": reference.confidence,
        })

    def observe_response(self, text: str, url: str, content_type: str, headers: dict[str, str]) -> None:
        media = (content_type or "").lower()
        if self.javascript_parser == "ast" and (
            "javascript" in media or media in {"application/ecmascript", "text/ecmascript"}
        ):
            for candidate in extract_uncertain_script_candidates(text, url):
                self._record({
                    "url": None,
                    "kind": candidate["kind"],
                    "source_type": "script-ast",
                    "source_url": _safe_resource_url(url),
                    "source": candidate["source"],
                    "relation": "computed-target",
                    "depth": 0,
                    "status": "unresolved_candidate",
                    "queue_decision": "not_fetchable_without_runtime_value",
                    "confidence": "low",
                    "expression_fingerprint": candidate["expression_fingerprint"],
                    "candidate_prefix": candidate["candidate_prefix"],
                })
        for reference in extract_references(
            text, url, content_type, headers, self.javascript_parser
        ):
            safe_url = _safe_resource_url(reference.url)
            in_scope = allowed_origin(self.start_url, reference.url, self.aliases)
            sensitive = any(SENSITIVE_QUERY_KEYS.search(key) for key, _ in parse_qsl(urlsplit(reference.url).query))
            duplicate = safe_url in self.discovered_urls
            self.discovered_urls.add(safe_url)
            record: dict[str, object] = {
                "url": safe_url,
                "kind": reference.kind,
                "source_type": reference.source_type,
                "source_url": _safe_resource_url(url),
                "source": reference.source,
                "relation": reference.relation,
                "depth": 0,
                "status": "discovered",
                "confidence": reference.confidence,
            }
            if not in_scope:
                record["status"] = "out_of_scope"
                record["queue_decision"] = "rejected_scope"
            elif sensitive:
                record["status"] = "sensitive_reference"
                record["queue_decision"] = "rejected_sensitive"
            elif reference.kind == "api":
                record["queue_decision"] = "observed_only_api"
            elif duplicate or safe_url in self.seen:
                record["queue_decision"] = "duplicate_candidate"
            else:
                record["queue_decision"] = "admitted"
                self.seen.add(safe_url)
                self.queue.append((reference, url, 1))
            self._record(record)

    def fetch_pending(
        self, request_context: object, max_fetches: int | None = None
    ) -> list[dict[str, object]]:
        fetched: list[dict[str, object]] = []
        batch_attempts = 0
        while self.queue:
            if max_fetches is not None and batch_attempts >= max_fetches:
                break
            reference, source_url, depth = self._pop_next()
            candidate_class = self._candidate_class(reference)
            if depth > self.max_depth:
                self._update_unattempted_status(reference, source_url, depth, "depth_limited")
                continue
            if self.budget.attempted >= self.budget.limit:
                self._update_unattempted_status(reference, source_url, depth, "budget_limited")
                continue
            if not self.budget.remaining(candidate_class):
                self._update_unattempted_status(reference, source_url, depth, "class_budget_limited")
                continue
            if not allowed_origin(self.start_url, reference.url, self.aliases):
                continue
            if any(SENSITIVE_QUERY_KEYS.search(key) for key, _ in parse_qsl(urlsplit(reference.url).query)):
                continue
            self.budget.consume(candidate_class)
            batch_attempts += 1
            route_bucket = self._route_bucket(reference)
            self.fetched.add(_safe_resource_url(reference.url))
            self._fetched_routes.add(route_bucket)
            self._fetched_classes.add(candidate_class)
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
                    discovered = extract_references(
                        text, final_url, content_type, headers, self.javascript_parser
                    )
                    new_children = 0
                    queued_children = 0
                    excluded_children = 0
                    for child in discovered:
                        safe = _safe_resource_url(child.url)
                        in_scope = allowed_origin(self.start_url, child.url, self.aliases)
                        sensitive = any(SENSITIVE_QUERY_KEYS.search(key) for key, _ in parse_qsl(urlsplit(child.url).query))
                        duplicate = safe in self.discovered_urls
                        if not duplicate and in_scope:
                            new_children += 1
                            self.budget.new_references += 1
                        self.discovered_urls.add(safe)
                        queue_decision = "admitted"
                        evidence_status = "discovered"
                        if not in_scope:
                            queue_decision, evidence_status = "rejected_scope", "out_of_scope"
                            excluded_children += 1
                        elif sensitive:
                            queue_decision, evidence_status = "rejected_sensitive", "sensitive_reference"
                            excluded_children += 1
                        elif child.kind == "api":
                            queue_decision = "observed_only_api"
                            excluded_children += 1
                        elif duplicate or safe in self.seen:
                            queue_decision = "duplicate_candidate"
                        else:
                            self.seen.add(safe)
                            queued_children += 1
                        self._record({
                            "url": safe, "kind": child.kind,
                            "source_type": child.source_type,
                            "source_url": _safe_resource_url(final_url),
                            "source": child.source, "relation": child.relation,
                            "depth": depth, "status": evidence_status,
                            "queue_decision": queue_decision,
                            "confidence": child.confidence,
                        })
                        if queue_decision == "admitted" and depth < self.max_depth:
                            self.queue.append((child, final_url, depth + 1))
                    self.budget.responses += 1
                    class_yield = self._yield_by_class[candidate_class]
                    class_yield[0] += new_children
                    class_yield[1] += 1
                    record["new_references"] = new_children
                    record["candidate_class"] = candidate_class
                    record["response_reference_count"] = len(discovered)
                    record["queued_references"] = queued_children
                    record["excluded_references"] = excluded_children
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
