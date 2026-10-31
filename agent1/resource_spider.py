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

from .bounded_http import bounded_get
from .state import SENSITIVE_QUERY_KEYS, allowed_origin, compact_text, digest


def _safe_resource_url(value: str) -> str:
    parts = urlsplit(value)
    safe_query = urlencode([(key, "<redacted>") for key, _ in parse_qsl(parts.query, keep_blank_values=True)])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, safe_query, ""))


MAX_REFERENCES_PER_RESPONSE = 250
MAX_REDIRECT_HOPS = 20
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
    method: str | None = None


# Confidence labels that are recorded but never fetched through the explicit
# reference channels; they need an explicitly configured speculative budget.
SPECULATIVE_CONFIDENCE = {"speculative", "conditional_comment"}
# Request surfaces that are observed only: never fetched by the passive spider,
# and never re-issued with a substitute method.
OBSERVED_ONLY_KINDS = {"api", "form_action", "ping", "security_report"}


def _normalized(raw: str, base: str, *, kind: str, source_type: str, source: str, relation: str = "",
                confidence: str = "observed_literal", method: str | None = None) -> ResourceReference | None:
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
    return ResourceReference(normalized, kind, source_type, source[:200], relation[:80], confidence, method)


# Conservative URL-like token: absolute/protocol-relative URLs, or root/dot
# relative paths. Path-like tokens must end in a file extension or "/" so that
# ordinary prose ("and/or", "1/2") is not treated as a URL.
_URL_TOKEN = re.compile(r"""(?<![\w@.:/-])((?:https?:)?//[A-Za-z0-9.-]+(?::\d+)?(?:/[^\s"'<>()\[\]{}`,;]*)?|\.{0,2}/[A-Za-z0-9_~%-][^\s"'<>()\[\]{}`,;]*)""")
_PATH_SHAPE = re.compile(r"^(?:\.{0,2}/)(?:[A-Za-z0-9_~%.-]+/)*(?:[A-Za-z0-9_~%-][A-Za-z0-9_~%.-]*\.[A-Za-z0-9]{1,6}|[A-Za-z0-9_~%.-]*/)$")
MAX_SPECULATIVE_PER_SOURCE = 32


def _url_like(token: str) -> bool:
    token = token.rstrip(".")
    if not 2 < len(token) <= 300 or any(ch.isspace() for ch in token):
        return False
    if token.startswith(("http://", "https://", "//")):
        return True
    return bool(_PATH_SHAPE.match(token)) and token not in {"./", "../", "/"}


def speculative_text_candidates(text: str, base: str, *, source_type: str, source: str) -> list[ResourceReference]:
    """Low-confidence URL-like tokens from prose, comments or non-URL values.

    They are evidence of a possible reference, not a reference: callers record
    them and fetch them only under an explicit speculative budget."""
    result: list[ResourceReference] = []
    for match in _URL_TOKEN.finditer((text or "")[:200_000]):
        token = match.group(1).rstrip(".")
        if _url_like(token):
            item = _normalized(token, base, kind="asset", source_type=source_type, source=source,
                               relation="url-like-text", confidence="speculative")
            if item:
                result.append(item)
        if len(result) >= MAX_SPECULATIVE_PER_SOURCE:
            break
    return result


_CONDITIONAL_COMMENT = re.compile(r"^\s*\[if [^\]]{1,80}\]>(.*)<!\[endif\]\s*$", re.S | re.I)
_CSP_REPORT_URI = re.compile(r"(?:^|;)\s*report-uri\s+([^;]+)", re.I)
_DOCTYPE_SYSTEM = re.compile(r"""^doctype\s+\S+\s+(?:public\s+(["'])[^"']*\1\s+|system\s+)(["'])([^"']{1,500})\2""", re.I)
# meta name/property values that are defined to carry a URL.
URL_META_NAMES = {
    "og:url", "og:image", "og:image:url", "og:image:secure_url", "og:video", "og:video:url", "og:audio",
    "twitter:image", "twitter:image:src", "twitter:player", "msapplication-tileimage", "msapplication-config",
    "msapplication-square70x70logo", "msapplication-square150x150logo", "msapplication-wide310x150logo",
    "msapplication-square310x310logo", "msapplication-badge", "msapplication-notification",
}
# Additional standard or long-standing URL-bearing attributes (HTML Living
# Standard, HTML 4.01 and widely implemented legacy attributes).
EXTENDED_URL_ATTRIBUTES: dict[str, tuple[tuple[str, str], ...]] = {
    "body": (("background", "asset"),),
    "td": (("background", "asset"),), "th": (("background", "asset"),), "tr": (("background", "asset"),),
    "img": (("lowsrc", "asset"), ("dynsrc", "asset"), ("longdesc", "navigation")),
    "iframe": (("longdesc", "navigation"),), "frame": (("longdesc", "navigation"),),
    "object": (("codebase", "asset"), ("archive", "asset"), ("classid", "asset")),
    "html": (("manifest", "asset"),),
    "script": (("xlink:href", "asset"), ("href", "asset")),
    "import": (("implementation", "asset"),),
    "head": (("profile", "asset"),),
    "command": (("icon", "asset"),), "menuitem": (("icon", "asset"),),
    "input": (("lowsrc", "asset"), ("dynsrc", "asset")),
    "a": (("xlink:href", "navigation"),),
    "video": (("src", "asset"),),
}
MAX_NESTED_DOCUMENT_DEPTH = 2


class _DocumentReferences(HTMLParser):
    # Hyperlink-type attributes are resolved when used (activation or
    # submission), i.e. against the document's final base URL; subresources are
    # resolved when the element is inserted, i.e. against the base at that point.
    LAZY_ATTRIBUTES = {"href", "ping", "cite", "longdesc", "action", "formaction"}
    EAGER_HREF_TAGS = {"link", "image", "use", "script"}

    def __init__(self, response_url: str, *, extended: bool = False, nesting: int = 0,
                 base_url: str | None = None, source_prefix: str = "", confidence: str = "observed_literal",
                 lazy_base: bool = False):
        super().__init__(convert_charrefs=True)
        self.response_url = response_url
        self.base_url = base_url or response_url
        self.references: list[ResourceReference] = []
        self._base_seen = False
        self.extended = extended
        self.nesting = nesting
        self.source_prefix = source_prefix
        self.confidence = confidence
        self._form_method = "GET"
        self._speculative = 0
        self.lazy_base = lazy_base
        self._lazy: list[tuple[int, str, str, str, str, str, str | None]] = []
        self._raw_script = False
        self._raw_style = False

    def _add(self, raw: str, kind: str, tag: str, attr: str, relation: str = "", method: str | None = None) -> None:
        if len(self.references) >= MAX_REFERENCES_PER_RESPONSE:
            return
        if self.lazy_base and attr in self.LAZY_ATTRIBUTES and not (attr == "href" and tag in self.EAGER_HREF_TAGS) \
                and tag != "base":
            self._lazy.append((len(self.references), raw, kind, tag, attr, relation, method))
            return
        item = _normalized(raw, self.base_url, kind=kind, source_type="html", source=f"{self.source_prefix}<{tag}>[{attr}]",
                           relation=relation, confidence=self.confidence, method=method)
        if item:
            self.references.append(item)

    def close(self) -> None:
        super().close()
        # Re-insert lazily resolved references at their document positions.
        for offset, (position, raw, kind, tag, attr, relation, method) in enumerate(self._lazy):
            item = _normalized(raw, self.base_url, kind=kind, source_type="html",
                               source=f"{self.source_prefix}<{tag}>[{attr}]", relation=relation,
                               confidence=self.confidence, method=method)
            if item:
                self.references.insert(min(position + offset, len(self.references)), item)
        self._lazy = []

    def _speculate(self, text: str, source: str) -> None:
        if not self.extended or self._speculative >= MAX_SPECULATIVE_PER_SOURCE:
            return
        for item in speculative_text_candidates(text, self.base_url, source_type="html-text", source=self.source_prefix + source):
            if len(self.references) >= MAX_REFERENCES_PER_RESPONSE or self._speculative >= MAX_SPECULATIVE_PER_SOURCE:
                return
            self._speculative += 1
            self.references.append(item)

    def _nested(self, markup: str, source: str, confidence: str) -> None:
        if self.nesting >= MAX_NESTED_DOCUMENT_DEPTH:
            return
        parser = _DocumentReferences(self.response_url, extended=True, nesting=self.nesting + 1,
                                     base_url=self.base_url, source_prefix=f"{self.source_prefix}{source}>",
                                     confidence=confidence, lazy_base=self.lazy_base)
        parser.feed(markup[:MAX_TEXT_BYTES])
        parser.close()
        for item in parser.references:
            if len(self.references) >= MAX_REFERENCES_PER_RESPONSE:
                return
            self.references.append(item)

    def _extended_starttag(self, tag: str, values: dict[str, str], rels: set[str]) -> bool:
        """Standards-based additions. Returns True when the tag's default
        attribute handling must be skipped (re-typed request surfaces)."""
        for attr, kind in EXTENDED_URL_ATTRIBUTES.get(tag, ()):
            value = values.get(attr)
            if value and not (tag == "video" and attr == "src"):
                for raw in (value.split() if attr in {"archive"} else [value]):
                    self._add(raw, kind, tag, attr, "extended")
        if tag in {"a", "area"} and values.get("ping"):
            for raw in values["ping"].split()[:8]:
                # Hyperlink-auditing beacons are POSTed by the browser.
                self._add(raw, "ping", tag, "ping", "hyperlink-auditing", method="POST")
        if tag == "base" and values.get("href"):
            self._add(values["href"], "navigation", tag, "href", "base")
        if tag == "form":
            self._form_method = (values.get("method") or "GET").upper()
            if values.get("action"):
                self._add(values["action"], "form_action", tag, "action", "form", method=self._form_method)
            return True
        if tag in {"input", "button"} and values.get("formaction"):
            method = (values.get("formmethod") or self._form_method or "GET").upper()
            self._add(values["formaction"], "form_action", tag, "formaction", "form", method=method)
            if tag == "input" and values.get("src"):
                self._add(values["src"], "asset", tag, "src", "")
            return True
        if tag == "isindex" and values.get("action"):
            self._add(values["action"], "form_action", tag, "action", "isindex", method="GET")
        if tag == "iframe" and values.get("srcdoc"):
            # Per HTML, an iframe srcdoc document resolves URLs against the
            # parent document's base URL.
            self._nested(values["srcdoc"], "<iframe>[srcdoc]", self.confidence)
        if tag == "meta":
            name = (values.get("name") or values.get("property") or "").lower()
            equiv = values.get("http-equiv", "").lower()
            content = values.get("content", "")
            if equiv in {"content-security-policy", "content-security-policy-report-only"}:
                for match in _CSP_REPORT_URI.finditer(content):
                    for raw in match.group(1).split()[:4]:
                        self._add(raw, "security_report", tag, "content", "csp-report-uri", method="POST")
            elif name in URL_META_NAMES and name != "msapplication-config" and content:
                self._add(content, "asset", tag, "content", name)
            elif content and equiv != "refresh" and name != "msapplication-config":
                self._speculate(content, f"<meta>[content]")
        for key, value in values.items():
            if key.startswith("data-") and value:
                self._speculate(value, f"<{tag}>[{key}]")
        return False

    def handle_comment(self, data: str) -> None:
        if not self.extended:
            return
        match = _CONDITIONAL_COMMENT.match(data or "")
        if match:
            # Downlevel-hidden conditional comment: markup only legacy IE parses.
            self._nested(match.group(1), "<!--[if]-->", "conditional_comment")
        else:
            self._speculate(data, "<!--comment-->")

    def handle_decl(self, decl: str) -> None:
        if not self.extended:
            return
        match = _DOCTYPE_SYSTEM.match(decl or "")
        if match:
            self._add(match.group(3), "asset", "!doctype", "system", "dtd")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "base" and not self._base_seen and values.get("href"):
            self.base_url = urljoin(self.response_url, values["href"])
            self._base_seen = True
        rels = set(values.get("rel", "").lower().split())
        if self.extended and self._extended_starttag(tag, values, rels):
            return
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
            for item in extract_script_references(data[:MAX_TEXT_BYTES], self.base_url, extended=self.extended):
                if len(self.references) < MAX_REFERENCES_PER_RESPONSE:
                    self.references.append(item)
        elif self._raw_style:
            for item in extract_css_references(data[:MAX_TEXT_BYTES], self.base_url):
                if len(self.references) < MAX_REFERENCES_PER_RESPONSE:
                    self.references.append(item)
        elif data and data.strip():
            self._speculate(data, "text")


def extract_html_references(text: str, response_url: str, *, extended: bool = False,
                            lazy_base: bool = False) -> list[ResourceReference]:
    parser = _DocumentReferences(response_url, extended=extended, lazy_base=lazy_base)
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


def extract_script_references(text: str, response_url: str, *, limit: int = 128, extended: bool = False) -> list[ResourceReference]:
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

    methods: dict[tuple[str, str], list[str]] = {}

    def request_method(options: object | None) -> str:
        """HTTP method from a fetch()/Request() init object; GET when absent."""
        if options is None:
            return "GET"
        if getattr(options, "type", "") != "object":
            return "UNKNOWN"
        for pair in children(options):
            if getattr(pair, "type", "") != "pair":
                continue
            key = node_text(getattr(pair, "child_by_field_name")("key")).strip("'\"")
            if key == "method":
                value = literal(getattr(pair, "child_by_field_name")("value"))
                return value.upper() if value else "UNKNOWN"
        return "GET"

    candidates: list[tuple[str, str, str]] = []
    # Byte spans of request-sink URL arguments (fetch, Request, XHR open). A
    # literal inside one, e.g. the prefix of fetch('/api/x/' + id, {method:
    # 'POST'}), is part of a request whose method and full target are runtime
    # values; it is never re-emitted as a speculative GET.
    request_target_spans: list[tuple[int, int]] = []
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
                if name in {"fetch", "Request"}:
                    request_target_spans.append((arg_nodes[0].start_byte, arg_nodes[0].end_byte))
                raw = literal(arg_nodes[0])
                if raw:
                    candidate_kind = "navigation" if name in {"window.open", "open", "location.assign", "location.replace"} else "api"
                    candidates.append((raw, candidate_kind, f"call:{name}"))
                    if candidate_kind == "api":
                        methods.setdefault((raw, f"call:{name}"), []).append(request_method(arg_nodes[1] if len(arg_nodes) > 1 else None))
            elif name.endswith(".open") and len(arg_nodes) >= 2:
                request_target_spans.append((arg_nodes[1].start_byte, arg_nodes[1].end_byte))
                raw = literal(arg_nodes[1])
                if raw:
                    candidates.append((raw, "api", "call:xhr.open"))
                    verb = literal(arg_nodes[0])
                    methods.setdefault((raw, "call:xhr.open"), []).append(verb.upper() if verb else "UNKNOWN")
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
                request_target_spans.append((arg_nodes[0].start_byte, arg_nodes[0].end_byte))
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
        # One method per sink occurrence, in source order.
        queued_methods = methods.get((raw, evidence))
        method = queued_methods.pop(0) if queued_methods else None
        item = _normalized(raw, response_url, kind=ref_kind, source_type="script-ast", source=evidence,
                           method=method if extended else None)
        if item:
            result.append(item)
    if extended:
        # Uncertain references beyond recognized sinks. A literal that is an
        # argument of a request/navigation sink is never re-emitted here, so a
        # POST endpoint cannot become a GET candidate.
        sink_values = {raw for raw, _kind, _evidence in candidates}
        speculative: list[tuple[str, str]] = []
        for node in walk(root):
            node_kind = getattr(node, "type", "")
            if node_kind in {"string", "template_string"}:
                value = literal(node)
                inside_request_target = any(start <= node.start_byte and node.end_byte <= end
                                            for start, end in request_target_spans)
                if value and value not in sink_values and not inside_request_target and _url_like(value.strip()):
                    speculative.append((value.strip(), "script-literal"))
            elif node_kind == "comment":
                for item in speculative_text_candidates(node_text(node), response_url, source_type="script-ast", source="script-comment"):
                    result.append(item)
        for name, value in constants.items():
            if value not in sink_values and _url_like(value.strip()):
                speculative.append((value.strip(), "script-constant"))
        for raw, evidence in speculative[:MAX_SPECULATIVE_PER_SOURCE]:
            item = _normalized(raw, response_url, kind="asset", source_type="script-ast", source=evidence,
                               relation="url-like-literal", confidence="speculative")
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


def extract_header_references(headers: dict[str, str], response_url: str, *, extended: bool = False,
                              corrections: bool = False) -> list[ResourceReference]:
    values: list[ResourceReference] = []
    for key, header_value in headers.items():
        key = key.lower()
        if corrections and key == "content-location":
            # RFC 9110 8.7: identifies a resource corresponding to the enclosed
            # representation; a GET-able reference, resolved against the request URL.
            item = _normalized(header_value, response_url, kind="asset", source_type="header", source="Content-Location")
            if item:
                values.append(item)
            continue
        if extended and key in {"content-security-policy", "content-security-policy-report-only"}:
            for match in _CSP_REPORT_URI.finditer(header_value[:16_000]):
                for raw in match.group(1).split()[:4]:
                    item = _normalized(raw, response_url, kind="security_report", source_type="header",
                                       source="Content-Security-Policy", relation="csp-report-uri", method="POST")
                    if item:
                        values.append(item)
            continue
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


_HTML_SNIFF = re.compile(
    rb"^\s*<(?:!doctype\s+html|html|head|script|iframe|h1|div|font|table|a|style|title|b|body|br|p|!--)[\s>]", re.I)


def _sniffs_as_html(text: str) -> bool:
    return bool(_HTML_SNIFF.match((text or "")[:512].encode("utf-8", errors="ignore")))


def extract_references(
    text: str,
    response_url: str,
    content_type: str,
    headers: dict[str, str] | None = None,
    javascript_parser: str = "ast",
    extraction: str = "baseline",
) -> list[ResourceReference]:
    media = (content_type or "").lower().split(";", 1)[0].strip()
    extended = extraction in {"extended", "standards"}
    corrections = extraction == "standards"
    if corrections and not media and _sniffs_as_html(text):
        # WHATWG MIME Sniffing: only a response with no Content-Type is
        # sniffed; an explicit type (even text/plain) is honored.
        media = "text/html"
    result = extract_header_references(headers or {}, response_url, extended=extended, corrections=corrections)
    if media in {"text/html", "application/xhtml+xml", "image/svg+xml"}:
        result.extend(extract_html_references(text, response_url, extended=extended, lazy_base=corrections))
    elif media == "text/css":
        result.extend(extract_css_references(text, response_url))
    elif "javascript" in media or media in {"application/ecmascript", "text/ecmascript"}:
        result.extend(
            _extract_script_references_regex(text, response_url)
            if javascript_parser == "legacy_regex"
            else extract_script_references(text, response_url, extended=extended)
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
    seen: set[tuple[str, str, str, str | None]] = set()
    for item in items:
        key = (item.url, item.kind, item.source_type, item.method)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result[:MAX_REFERENCES_PER_RESPONSE]


class ResourceBudget:
    """Run-scoped budget shared by browser contexts and replay sessions."""

    def __init__(self, limit: int, per_class_limits: dict[str, int | None] | None = None, http_budget: object | None = None):
        self.limit = limit
        self.per_class_limits = per_class_limits or {}
        self.attempted = 0
        self.attempted_by_class: defaultdict[str, int] = defaultdict(int)
        self.new_references = 0
        self.responses = 0
        self.http_budget = http_budget

    def remaining(self, candidate_class: str) -> bool:
        class_limit = self.per_class_limits.get(candidate_class)
        return (
            self.attempted < self.limit
            and (class_limit is None or self.attempted_by_class[candidate_class] < class_limit)
            and (self.http_budget is None or self.http_budget.remaining())
        )

    def consume(self, candidate_class: str, ignore_class_cap: bool = False) -> bool:
        if ignore_class_cap:
            if self.attempted >= self.limit or (self.http_budget is not None and not self.http_budget.remaining()):
                return False
        elif not self.remaining(candidate_class):
            return False
        if self.http_budget is not None and not self.http_budget.consume("resource_spider"):  # type: ignore[attr-defined]
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
        *,
        extraction: str = "baseline",
        allocation: str = "class_caps",
        passive_document_limit: int | None = None,
        passive_http_reserve: int = 0,
        max_speculative_fetches: int = 0,
        speculative_per_batch: int = 2,
        dangerous_pattern: re.Pattern[str] | None = None,
        body_reader: str = "content_length",
        frontier_model: str = "legacy",
        passive_document_max_depth: int | None = None,
        budget_aware_deepening: bool = False,
        hard_max_depth: int = 8,
    ):
        if frontier_model not in {"legacy", "persistent"}:
            raise ValueError(f"unknown frontier model: {frontier_model}")
        if (budget_aware_deepening or passive_document_max_depth is not None) and frontier_model != "persistent":
            raise ValueError("depth alternatives require the persistent frontier")
        self.frontier_model = frontier_model
        self.persistent = frontier_model == "persistent"
        self.passive_document_max_depth = passive_document_max_depth
        self.budget_aware_deepening = budget_aware_deepening
        self.hard_max_depth = hard_max_depth
        # Persistent frontier: explicit per-URL state instead of one "seen" set.
        # pending_main | pending_spec | fetched | rejected | observed_only |
        # deferred_depth | deferred_class | deferred_budget
        self.url_state: dict[str, str] = {}
        self.deferred_class: dict[str, str] = {}
        self._deepened: set[str] = set()
        # Shortest known queue depth per URL and the extracted-child edges of
        # fetched responses, for shortest-path relaxation when a page is later
        # reached by a shorter route.
        self.best_depth: dict[str, int] = {}
        self.children_of: dict[str, set[str]] = defaultdict(set)
        self._class_deferred: dict[str, tuple[ResourceReference, str, int]] = {}
        self._reclaimed: set[str] = set()
        if body_reader not in {"content_length", "bounded_stream"}:
            raise ValueError(f"unknown response body reader: {body_reader}")
        self.body_reader = body_reader
        # Set per drain by the caller (agent1.cookies.context_cookie_bridge):
        # source(url) -> (Cookie header, names); sink(url, set_cookie_headers).
        self.cookie_source = None
        self.cookie_sink = None
        self._redirect_hops: dict[str, int] = {}
        if extraction not in {"baseline", "extended", "standards"}:
            raise ValueError(f"unknown extraction mode: {extraction}")
        if allocation not in {"class_caps", "shared_http"}:
            raise ValueError(f"unknown resource allocation: {allocation}")
        if allocation == "shared_http" and budget.http_budget is None:
            raise ValueError("shared_http allocation requires a shared HTTP budget")
        self.extraction = extraction
        self.allocation = allocation
        self.passive_document_limit = passive_document_limit
        self.passive_http_reserve = passive_http_reserve
        self.max_speculative_fetches = max_speculative_fetches
        self.speculative_per_batch = speculative_per_batch
        # Only the new, opt-in channels apply the path filter, so the frozen
        # class-caps baseline keeps its historical behavior.
        self.dangerous_pattern = dangerous_pattern if (allocation != "class_caps" or extraction != "baseline") else None
        self.passive_attempted = 0
        self.speculative_attempted = 0
        self.speculative_queue: list[tuple[ResourceReference, str, int]] = []
        # Under shared_http, depth is the minimum over discovery paths: a
        # reference first seen on a long chain (and capped or queued deep) is
        # re-admitted when it is rediscovered closer to the observed browser state.
        self.track_min_depth = allocation == "shared_http" or frontier_model == "persistent"
        self._capped: dict[str, tuple[ResourceReference, str, int]] = {}
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

    def seed_external(self, url: str) -> bool:
        """Queue a validated external GET candidate for an Agent 1-owned fetch."""
        safe = _safe_resource_url(url)
        if (safe in self.seen or not allowed_origin(self.start_url, url, self.aliases)
                or urlsplit(url).query):
            return False
        self.seen.add(safe)
        self.discovered_urls.add(safe)
        reference = ResourceReference(url, "asset", "zap_seed", "ZAP observed GET", "external_seed")
        self._record({
            "url": safe, "kind": "asset", "source_type": "zap_seed", "source_url": safe,
            "source": "ZAP observed GET", "relation": "external_seed", "depth": 0,
            "status": "discovered", "queue_decision": "admitted",
        })
        self.queue.append((reference, url, 1))
        return True

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

    REQUEUE_DECISIONS = {"admitted", "readmitted_shallower", "readmitted_class", "promoted_explicit",
                         "upgraded_kind", "budget_deepened", "speculative_admitted", "readmitted_propagated",
                         "budget_reclaimed"}

    def _restore_persistent(self, items: list[dict[str, object]]) -> None:
        """Lossless rebuild of the persistent frontier from evidence records.

        Record depth is the parent's depth for extracted children (queued one
        level deeper) but the item's own depth for redirect hops and deepened
        re-admissions."""
        pending: dict[str, tuple[ResourceReference, str, int, str]] = {}
        for item in items:
            raw_url = item.get("url")
            if not isinstance(raw_url, str) or not raw_url:
                continue
            safe = _safe_resource_url(raw_url)
            self.discovered_urls.add(safe)
            reference = ResourceReference(
                url=raw_url, kind=str(item.get("kind", "asset")), source_type=str(item.get("source_type", "unknown")),
                source=str(item.get("source", "")), relation=str(item.get("relation", "")),
                confidence=str(item.get("confidence") or "observed_literal"), method=item.get("method"),  # type: ignore[arg-type]
            )
            status, decision = item.get("status"), str(item.get("queue_decision") or "")
            depth = int(item.get("depth") or 0)
            parent = item.get("source_url")
            if isinstance(parent, str) and depth > 0 and status not in {"fetched", "failed"}:
                self.children_of[_safe_resource_url(parent)].add(safe)
            if status in {"fetched", "failed"}:
                self.best_depth[safe] = min(depth, self.best_depth.get(safe, depth))
                pending.pop(safe, None)
                self._capped.pop(safe, None)
                self.url_state[safe] = "fetched"
                self.seen.add(safe)
                self.fetched.add(safe)
                channel = item.get("channel") or "typed_resource"
                if channel == "passive_document":
                    self.passive_attempted += 1
                elif channel == "speculative":
                    self.speculative_attempted += 1
                else:
                    candidate_class = str(item.get("candidate_class") or self._candidate_class(reference))
                    self.budget.attempted += 1
                    self.budget.attempted_by_class[candidate_class] += 1
                continue
            if self.url_state.get(safe) == "fetched":
                continue
            if decision.startswith("rejected_") or status in {"out_of_scope", "sensitive_reference"}:
                self.url_state[safe] = "rejected"
                pending.pop(safe, None)
            elif decision.startswith("observed_only_"):
                self.url_state.setdefault(safe, "observed_only")
            elif status in {"depth_limited", "class_budget_limited", "budget_limited"}:
                pending.pop(safe, None)
                if status == "depth_limited":
                    self.url_state[safe] = "deferred_depth"
                    self._capped[safe] = (reference, str(item.get("source_url") or ""), depth)
                elif status == "class_budget_limited":
                    self.url_state[safe] = "deferred_class"
                    self.deferred_class[safe] = self._candidate_class(reference)
                    self._class_deferred[safe] = (reference, str(item.get("source_url") or ""), depth)
                else:
                    self.url_state[safe] = "deferred_budget"
            elif decision in self.REQUEUE_DECISIONS and status == "discovered":
                own_depth = item.get("relation") == "redirect" or decision in {"budget_deepened", "readmitted_propagated", "budget_reclaimed"}
                queued_depth = depth if own_depth else depth + 1
                lane = "spec" if decision == "speculative_admitted" else "main"
                previous = pending.get(safe)
                if previous is None or queued_depth < previous[2] or (lane == "main" and previous[3] == "spec"):
                    pending[safe] = (reference, str(item.get("source_url") or ""), queued_depth, lane)
                if decision == "budget_deepened":
                    self._deepened.add(safe)
                if decision == "budget_reclaimed":
                    self._reclaimed.add(safe)
                    self._class_deferred.pop(safe, None)
        for safe, (reference, source_url, depth, lane) in pending.items():
            if depth > self._depth_limit(reference) and safe not in self._deepened:
                self.url_state[safe] = "deferred_depth"
                self._capped[safe] = (reference, source_url, depth)
                continue
            self.url_state[safe] = "pending_spec" if lane == "spec" else "pending_main"
            (self.speculative_queue if lane == "spec" else self.queue).append((reference, source_url, depth))

    def restore_from_evidence(self, items: list[dict[str, object]]) -> None:
        """Rebuild the frontier after checkpoint resume from evidence only."""
        if self.persistent:
            self._restore_persistent(items)
            return
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
            channel = item.get("channel") or "typed_resource"
            if status in {"fetched", "failed"} and channel != "typed_resource":
                self.seen.add(safe_url)
                self.fetched.add(safe_url)
                if channel == "passive_document":
                    self.passive_attempted += 1
                elif channel == "speculative":
                    self.speculative_attempted += 1
                continue
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
        self.queue = [item for item in self.queue if _safe_resource_url(item[0].url) not in fetched_urls]
        self.budget.attempted_by_class.clear()
        class_urls: set[tuple[str, str]] = set()
        for item in items:
            if (item.get("channel") or "typed_resource") != "typed_resource":
                continue
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

    def _decide(self, reference: ResourceReference, safe_url: str, duplicate: bool) -> tuple[str, str]:
        """Evidence status and queue decision for a newly extracted reference."""
        if self.persistent:
            return self._decide_persistent(reference, safe_url)
        in_scope = allowed_origin(self.start_url, reference.url, self.aliases)
        sensitive = any(SENSITIVE_QUERY_KEYS.search(key) for key, _ in parse_qsl(urlsplit(reference.url).query))
        if not in_scope:
            return "out_of_scope", "rejected_scope"
        if sensitive:
            return "sensitive_reference", "rejected_sensitive"
        if reference.kind == "api":
            return "discovered", "observed_only_api"
        if reference.kind in OBSERVED_ONLY_KINDS:
            return "discovered", f"observed_only_{reference.kind}"
        if self.dangerous_pattern is not None and self.dangerous_pattern.search(urlsplit(reference.url).path):
            return "discovered", "rejected_dangerous"
        if duplicate or safe_url in self.seen:
            return "discovered", "duplicate_candidate"
        if reference.confidence in SPECULATIVE_CONFIDENCE:
            return "discovered", "speculative_admitted" if self.max_speculative_fetches > 0 else "observed_only_speculative"
        return "discovered", "admitted"

    def _depth_limit(self, reference: ResourceReference) -> int:
        """Maximum queue depth for a candidate. With a separately bounded passive
        depth, documents may chain to that depth and their leaf resources one
        level further; everything else keeps the typed-resource depth."""
        if self.passive_document_max_depth is not None and self.allocation == "shared_http" \
                and reference.confidence not in SPECULATIVE_CONFIDENCE:
            return self.passive_document_max_depth + (0 if self._candidate_class(reference) == "document" else 1)
        return self.max_depth

    def _readmit_shallower(self, reference: ResourceReference, safe_url: str, source_url: str, depth: int) -> bool:
        """Lower the depth of a known, never-attempted reference. Returns True if changed."""
        if not (self.track_min_depth or self.persistent) or safe_url in self.fetched or depth > self._depth_limit(reference):
            return False
        capped = self._capped.get(safe_url)
        if capped is not None and depth < capped[2]:
            del self._capped[safe_url]
            if self.persistent:
                self._requeue(safe_url, capped[0], source_url, depth)
            else:
                self.queue.append((capped[0], source_url, depth))
            return True
        for index, (queued, queued_source, queued_depth) in enumerate(self.queue):
            if queued_depth > depth and _safe_resource_url(queued.url) == safe_url:
                self.queue[index] = (queued, queued_source, depth)
                return True
        return False

    def _decide_persistent(self, reference: ResourceReference, safe_url: str) -> tuple[str, str]:
        """State-machine admission. Rejections that depend on the URL itself
        (scope, sensitive query, dangerous path) are permanent; a reference's
        *kind* (observed-only, speculative) does not make the URL ineligible
        for later explicit evidence."""
        state = self.url_state.get(safe_url)
        if not allowed_origin(self.start_url, reference.url, self.aliases):
            self.url_state.setdefault(safe_url, "rejected")
            return "out_of_scope", "rejected_scope"
        if any(SENSITIVE_QUERY_KEYS.search(key) for key, _ in parse_qsl(urlsplit(reference.url).query)):
            self.url_state[safe_url] = "rejected"
            return "sensitive_reference", "rejected_sensitive"
        if reference.kind in OBSERVED_ONLY_KINDS:
            self.url_state.setdefault(safe_url, "observed_only")
            return "discovered", "observed_only_api" if reference.kind == "api" else f"observed_only_{reference.kind}"
        if self.dangerous_pattern is not None and self.dangerous_pattern.search(urlsplit(reference.url).path):
            self.url_state[safe_url] = "rejected"
            return "discovered", "rejected_dangerous"
        if state in {"fetched", "rejected"}:
            return "discovered", "duplicate_candidate"
        if reference.confidence in SPECULATIVE_CONFIDENCE:
            if state in {None, "observed_only"}:
                return "discovered", "speculative_admitted" if self.max_speculative_fetches > 0 else "observed_only_speculative"
            return "discovered", "duplicate_candidate"
        if state in {None, "observed_only", "speculative_exhausted"}:
            return "discovered", "admitted"
        if state == "pending_spec":
            return "discovered", "promoted_explicit"
        if state == "pending_main":
            queued = next((ref for ref, _src, _d in self.queue if _safe_resource_url(ref.url) == safe_url), None)
            if queued is not None and self._candidate_class(queued) != "document" and self._candidate_class(reference) == "document":
                return "discovered", "upgraded_kind"
            return "discovered", "duplicate_candidate"
        if state == "deferred_class":
            new_class = self._candidate_class(reference)
            if new_class != self.deferred_class.get(safe_url) and (
                    self._channel(reference, new_class) == "passive_document" or self.budget.remaining(new_class)):
                return "discovered", "readmitted_class"
        return "discovered", "duplicate_candidate"

    def _requeue(self, safe_url: str, reference: ResourceReference, source_url: str, depth: int) -> None:
        """Return a deferred candidate to the lane its evidence allows."""
        if reference.confidence in SPECULATIVE_CONFIDENCE:
            self.url_state[safe_url] = "pending_spec"
            self.speculative_queue.append((reference, source_url, depth))
        else:
            self.url_state[safe_url] = "pending_main"
            self.queue.append((reference, source_url, depth))

    def _relax(self, safe_url: str, depth: int) -> int:
        """Propagate a shorter depth for an already-fetched URL to its known
        descendants (BFS edge relaxation). Returns the number of re-admissions."""
        readmitted = 0
        stack = [(safe_url, depth)]
        while stack:
            url, d = stack.pop()
            if self.best_depth.get(url, 1 << 30) <= d:
                continue
            self.best_depth[url] = d
            for child in self.children_of.get(url, ()):
                child_depth = d + 1
                state = self.url_state.get(child)
                if state == "fetched":
                    stack.append((child, child_depth))
                elif child in self._capped and child_depth < self._capped[child][2]:
                    reference, source_url, _old = self._capped[child]
                    if child_depth <= self._depth_limit(reference):
                        del self._capped[child]
                        self.best_depth[child] = child_depth
                        self._requeue(child, reference, source_url, child_depth)
                        self._record({
                            "url": child, "kind": reference.kind, "source_type": reference.source_type,
                            "source_url": _safe_resource_url(source_url), "source": reference.source,
                            "relation": reference.relation, "depth": child_depth, "status": "discovered",
                            "queue_decision": "readmitted_propagated", "confidence": reference.confidence,
                        })
                        readmitted += 1
                    else:
                        self._capped[child] = (reference, source_url, child_depth)
                elif state == "pending_main":
                    for index, (queued, queued_source, queued_depth) in enumerate(self.queue):
                        if queued_depth > child_depth and _safe_resource_url(queued.url) == child:
                            self.queue[index] = (queued, queued_source, child_depth)
                            self.best_depth[child] = child_depth
        return readmitted

    def _shorter_route(self, reference: ResourceReference, safe_url: str, source_url: str, depth: int) -> str | None:
        """Handle a duplicate reference seen at `depth`; returns a decision label if it helped."""
        if self._readmit_shallower(reference, safe_url, source_url, depth):
            if self.persistent:
                self.best_depth[safe_url] = min(depth, self.best_depth.get(safe_url, depth))
            return "readmitted_shallower"
        if self.persistent and self.url_state.get(safe_url) == "fetched" and depth < self.best_depth.get(safe_url, 1 << 30):
            self._relax(safe_url, depth)
            return "relaxed_shallower"
        return None

    def _admit(self, reference: ResourceReference, safe_url: str, decision: str, source_url: str, depth: int) -> None:
        if self.persistent:
            if decision in {"admitted", "readmitted_class", "speculative_admitted", "promoted_explicit"}:
                self.best_depth[safe_url] = min(depth, self.best_depth.get(safe_url, depth))
            if decision in {"admitted", "readmitted_class"}:
                self.url_state[safe_url] = "pending_main"
                self.queue.append((reference, source_url, depth))
            elif decision == "speculative_admitted":
                self.url_state[safe_url] = "pending_spec"
                self.speculative_queue.append((reference, source_url, depth))
            elif decision == "promoted_explicit":
                previous = [item for item in self.speculative_queue if _safe_resource_url(item[0].url) == safe_url]
                self.speculative_queue = [item for item in self.speculative_queue if _safe_resource_url(item[0].url) != safe_url]
                best = min([depth] + [item[2] for item in previous])
                self.url_state[safe_url] = "pending_main"
                self.queue.append((reference, source_url, best))
            elif decision == "upgraded_kind":
                for index, (queued, queued_source, queued_depth) in enumerate(self.queue):
                    if _safe_resource_url(queued.url) == safe_url:
                        self.queue[index] = (reference, source_url, min(depth, queued_depth))
                        break
            return
        if decision == "admitted":
            self.seen.add(safe_url)
            self.queue.append((reference, source_url, depth))
        elif decision == "speculative_admitted":
            self.seen.add(safe_url)
            self.speculative_queue.append((reference, source_url, depth))

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
            text, url, content_type, headers, self.javascript_parser, self.extraction
        ):
            safe_url = _safe_resource_url(reference.url)
            duplicate = safe_url in self.discovered_urls
            self.discovered_urls.add(safe_url)
            status, decision = self._decide(reference, safe_url, duplicate)
            if decision == "duplicate_candidate":
                decision = self._shorter_route(reference, safe_url, url, 1) or decision
            record: dict[str, object] = {
                "url": safe_url,
                "kind": reference.kind,
                "source_type": reference.source_type,
                "source_url": _safe_resource_url(url),
                "source": reference.source,
                "relation": reference.relation,
                "depth": 0,
                "status": status,
                "confidence": reference.confidence,
                "queue_decision": decision,
            }
            if reference.method:
                record["method"] = reference.method
            self._admit(reference, safe_url, decision, url, 1)
            self._record(record)

    def _defer(self, safe_url: str, state: str) -> None:
        if self.persistent:
            self.url_state[safe_url] = state

    def _channel(self, reference: ResourceReference, candidate_class: str) -> str:
        if (self.allocation == "shared_http" and candidate_class == "document"
                and reference.kind in {"navigation", "asset"} and reference.confidence not in SPECULATIVE_CONFIDENCE):
            return "passive_document"
        return "typed_resource"

    def _shared_http_available(self) -> bool:
        """Passive channels together may use at most (limit - reserve) requests,
        so browser, redirect, replay and typed-resource traffic always keep at
        least `passive_http_reserve` of the shared budget."""
        http = self.budget.http_budget
        if http is None or not http.remaining():  # type: ignore[attr-defined]
            return False
        passive_used = http.by_source["passive_document"] + http.by_source["speculative_candidate"]  # type: ignore[attr-defined]
        return passive_used < http.limit - self.passive_http_reserve  # type: ignore[attr-defined]

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
            safe_url = _safe_resource_url(reference.url)
            if depth > self._depth_limit(reference) and safe_url not in self._deepened:
                self._update_unattempted_status(reference, source_url, depth, "depth_limited")
                if self.persistent:
                    self.url_state[safe_url] = "deferred_depth"
                    self._capped.setdefault(safe_url, (reference, source_url, depth))
                continue
            if self.persistent and self.url_state.get(safe_url) == "fetched":
                continue
            channel = self._channel(reference, candidate_class)
            if channel == "passive_document":
                # Safe, input-free same-origin GET documents draw on the shared
                # HTTP budget (minus a reserve for browser and replay traffic)
                # instead of the fixed document class cap.
                if not allowed_origin(self.start_url, reference.url, self.aliases):
                    continue
                if (self.passive_document_limit is not None and self.passive_attempted >= self.passive_document_limit) \
                        or not self._shared_http_available():
                    self._update_unattempted_status(reference, source_url, depth, "budget_limited")
                    self._defer(safe_url, "deferred_budget")
                    continue
                if not self.budget.http_budget.consume("passive_document"):  # type: ignore[union-attr]
                    self._update_unattempted_status(reference, source_url, depth, "budget_limited")
                    self._defer(safe_url, "deferred_budget")
                    continue
                self.passive_attempted += 1
            else:
                if self.budget.attempted >= self.budget.limit:
                    self._update_unattempted_status(reference, source_url, depth, "budget_limited")
                    self._defer(safe_url, "deferred_budget")
                    continue
                if self.budget.http_budget is not None and not self.budget.http_budget.remaining():
                    self._update_unattempted_status(reference, source_url, depth, "budget_limited")
                    self._defer(safe_url, "deferred_budget")
                    continue
                reclaimed = safe_url in self._reclaimed
                if not reclaimed and not self.budget.remaining(candidate_class):
                    self._update_unattempted_status(reference, source_url, depth, "class_budget_limited")
                    self._defer(safe_url, "deferred_class")
                    self.deferred_class[safe_url] = candidate_class
                    if self.persistent:
                        self._class_deferred[safe_url] = (reference, source_url, depth)
                    continue
                if not allowed_origin(self.start_url, reference.url, self.aliases):
                    continue
                if any(SENSITIVE_QUERY_KEYS.search(key) for key, _ in parse_qsl(urlsplit(reference.url).query)):
                    continue
                if not self.budget.consume(candidate_class, ignore_class_cap=reclaimed):
                    self._update_unattempted_status(reference, source_url, depth, "budget_limited")
                    self._defer(safe_url, "deferred_budget")
                    continue
            batch_attempts += 1
            fetched.append(self._fetch(request_context, reference, source_url, depth, candidate_class, channel))
        if self.budget_aware_deepening and not self.queue and (self._class_deferred or self._capped) \
                and (max_fetches is None or batch_attempts < max_fetches):
            # Budget-aware frontier: only when nothing better is pending, spend
            # remaining capacity on deferred work, shallowest first. Class-deferred
            # candidates may exceed their class cap but never the typed-resource
            # total or the shared HTTP budget; depth-deferred candidates are
            # deepened up to hard_max_depth. Safety rejections are never revisited.
            room = (max_fetches or 10) - batch_attempts
            pool = [("budget_reclaimed", k, v) for k, v in self._class_deferred.items()] + \
                   [("budget_deepened", k, v) for k, v in self._capped.items() if v[2] <= self.hard_max_depth]
            for decision, safe_url, (reference, source_url, depth) in sorted(pool, key=lambda x: (x[2][2], x[0], x[1]))[:room]:
                (self._class_deferred if decision == "budget_reclaimed" else self._capped).pop(safe_url, None)
                self._record({
                    "url": safe_url, "kind": reference.kind, "source_type": reference.source_type,
                    "source_url": _safe_resource_url(source_url), "source": reference.source,
                    "relation": reference.relation, "depth": depth, "status": "discovered",
                    "queue_decision": decision, "confidence": reference.confidence,
                })
                (self._reclaimed if decision == "budget_reclaimed" else self._deepened).add(safe_url)
                self._requeue(safe_url, reference, source_url, depth)
        speculative_batch = 0
        while self.speculative_queue and speculative_batch < self.speculative_per_batch:
            reference, source_url, depth = self.speculative_queue.pop(0)
            safe_spec = _safe_resource_url(reference.url)
            if depth > self._depth_limit(reference) and safe_spec not in self._deepened:
                self._update_unattempted_status(reference, source_url, depth, "depth_limited")
                if self.persistent:
                    # Defer rather than drop: shorter routes or budget-aware
                    # deepening may re-admit it.
                    self.url_state[safe_spec] = "deferred_depth"
                    self._capped.setdefault(safe_spec, (reference, source_url, depth))
                continue
            if self.speculative_attempted >= self.max_speculative_fetches or not self._shared_http_available() \
                    or self.budget.http_budget is None or not self.budget.http_budget.consume("speculative_candidate"):
                self._update_unattempted_status(reference, source_url, depth, "budget_limited")
                # Exhausting the speculative lane says nothing about the URL;
                # later explicit evidence may still admit it.
                self._defer(_safe_resource_url(reference.url), "speculative_exhausted")
                continue
            self.speculative_attempted += 1
            speculative_batch += 1
            fetched.append(self._fetch(request_context, reference, source_url, depth,
                                       self._candidate_class(reference), "speculative"))
        drained = self.evidence
        self.evidence = []
        return drained

    def _fetch(self, request_context: object, reference: ResourceReference, source_url: str, depth: int,
               candidate_class: str, channel: str) -> dict[str, object]:
        route_bucket = self._route_bucket(reference)
        self.fetched.add(_safe_resource_url(reference.url))
        if self.persistent:
            self.url_state[_safe_resource_url(reference.url)] = "fetched"
            self.best_depth[_safe_resource_url(reference.url)] = min(depth, self.best_depth.get(_safe_resource_url(reference.url), depth))
        self._fetched_routes.add(route_bucket)
        self._fetched_classes.add(candidate_class)
        try:
            cookie_evidence: dict[str, object] = {}
            if self.body_reader == "bounded_stream":
                cookie, cookie_names = self.cookie_source(reference.url) if self.cookie_source else (None, [])
                streamed = bounded_get(reference.url, max_body_bytes=self.max_body_bytes, timeout_s=5.0,
                                       cookie_header=cookie, deadline_s=5.0)
                headers, body, body_status = streamed.headers, streamed.body, streamed.body_status
                final_url, status = streamed.url, streamed.status
                cookie_evidence = {"session_cookie_names": cookie_names, "wire_bytes": streamed.wire_bytes}
                if streamed.set_cookies:
                    if self.cookie_sink is not None:
                        outcome = self.cookie_sink(final_url, streamed.set_cookies)
                        cookie_evidence["set_cookie_names"] = outcome["names"]
                        cookie_evidence["cookie_updates"] = {key: value for key, value in (
                            ("applied", outcome["applied"]), ("deleted", outcome["deleted"]),
                            *((f"rejected_{reason}", n) for reason, n in outcome["rejected"].items())) if value}
                    else:
                        cookie_evidence["set_cookie_names"] = sorted({h.split("=", 1)[0].strip() for h in streamed.set_cookies})
                        cookie_evidence["cookie_updates"] = {"dropped_no_session": len(streamed.set_cookies)}
            else:
                response = request_context.get(reference.url, timeout=5_000, max_redirects=0)  # type: ignore[attr-defined]
                headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
                # Legacy reader: Playwright buffers the body before Python sees
                # it, so only bodies with a declared, in-bound Content-Length are
                # copied. Bodies without one (chunked, close-delimited) are
                # skipped; the skip is now recorded instead of silent.
                try:
                    body_size = int(headers.get("content-length", "") or -1)
                except ValueError:
                    body_size = -1
                if body_size < 0:
                    body, body_status = b"", "skipped_unknown_length"
                elif body_size == 0:
                    body, body_status = b"", "empty"
                elif body_size > self.max_body_bytes:
                    body, body_status = b"", "skipped_oversized"
                else:
                    body, body_status = response.body(), "complete"
                final_url, status = response.url, int(response.status)
            content_type = headers.get("content-type", "")
            charset_match = re.search(r"charset\s*=\s*['\"]?([^;\s'\"]+)", content_type, re.I)
            encoding = charset_match.group(1) if charset_match else "utf-8"
            try:
                text = body.decode(encoding, errors="replace")
            except LookupError:
                text = body.decode("utf-8", errors="replace")
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
                "channel": channel, "confidence": reference.confidence,
                "body_status": body_status, "body_bytes": len(body), **cookie_evidence,
            }
            if channel == "passive_document" and redirect_target and 300 <= status < 400:
                # A redirect hop is the same logical document, not a deeper
                # reference: follow it at the same depth after a scope check.
                safe_target = _safe_resource_url(redirect_target)
                hops = self._redirect_hops.get(_safe_resource_url(reference.url), 0) + 1
                if hops > MAX_REDIRECT_HOPS and safe_target not in self.seen:
                    # Same limit as Chromium/Fetch: a chain longer than 20 is a network error.
                    self.seen.add(safe_target)
                    self._record({
                        "url": safe_target, "kind": reference.kind, "source_type": "header",
                        "source_url": _safe_resource_url(final_url), "source": "Location", "relation": "redirect",
                        "depth": depth, "status": "discovered", "queue_decision": "rejected_redirect_limit",
                        "confidence": reference.confidence,
                    })
                elif allowed_origin(self.start_url, redirect_target, self.aliases) and safe_target not in self.seen:
                    self._redirect_hops[safe_target] = hops
                    hop = ResourceReference(redirect_target, reference.kind, "header", "Location", "redirect",
                                            reference.confidence)
                    status_, decision = self._decide(hop, safe_target, False)
                    self.discovered_urls.add(safe_target)
                    self._admit(hop, safe_target, decision, final_url, depth)
                    self._record({
                        "url": safe_target, "kind": hop.kind, "source_type": "header",
                        "source_url": _safe_resource_url(final_url), "source": "Location", "relation": "redirect",
                        "depth": depth, "status": status_, "queue_decision": decision, "confidence": hop.confidence,
                    })
            if status < 400:
                discovered = extract_references(
                    text, final_url, content_type, headers, self.javascript_parser, self.extraction
                )
                if channel == "passive_document" and 300 <= status < 400:
                    # The redirect target was handled above as a same-depth hop
                    # (scope, loop and chain-length checks); re-extracting the
                    # Location header as a deeper link would bypass those checks.
                    discovered = [c for c in discovered if not (c.source_type == "header" and c.source == "Location")]
                new_children = 0
                queued_children = 0
                excluded_children = 0
                for child in discovered:
                    safe = _safe_resource_url(child.url)
                    in_scope = allowed_origin(self.start_url, child.url, self.aliases)
                    duplicate = safe in self.discovered_urls
                    if not duplicate and in_scope:
                        new_children += 1
                        self.budget.new_references += 1
                    self.discovered_urls.add(safe)
                    evidence_status, queue_decision = self._decide(child, safe, duplicate)
                    if self.persistent:
                        self.children_of[_safe_resource_url(reference.url)].add(safe)
                    if queue_decision == "duplicate_candidate":
                        queue_decision = self._shorter_route(child, safe, final_url, depth + 1) or queue_decision
                    if queue_decision.startswith(("rejected_", "observed_only_")):
                        excluded_children += 1
                    elif queue_decision in {"admitted", "speculative_admitted"}:
                        queued_children += 1
                    child_record = {
                        "url": safe, "kind": child.kind,
                        "source_type": child.source_type,
                        "source_url": _safe_resource_url(final_url),
                        "source": child.source, "relation": child.relation,
                        "depth": depth, "status": evidence_status,
                        "queue_decision": queue_decision,
                        "confidence": child.confidence,
                    }
                    if child.method:
                        child_record["method"] = child.method
                    self._record(child_record)
                    if depth + 1 <= self._depth_limit(child):
                        self._admit(child, safe, queue_decision, final_url, depth + 1)
                    elif queue_decision in {"admitted", "speculative_admitted", "readmitted_class", "promoted_explicit"}:
                        self.seen.add(safe)
                        if self.persistent:
                            self.url_state[safe] = "deferred_depth"
                            self._capped.setdefault(safe, (child, final_url, depth + 1))
                        elif self.track_min_depth and queue_decision == "admitted":
                            self._capped[safe] = (child, final_url, depth + 1)
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
            return record
        except Exception as exc:
            record = {
                "url": _safe_resource_url(reference.url), "kind": reference.kind,
                "source_type": reference.source_type, "source_url": _safe_resource_url(source_url),
                "source": reference.source, "relation": reference.relation,
                "depth": depth, "status": "failed",
                "error": type(exc).__name__, "channel": channel, "confidence": reference.confidence,
            }
            self._record(record)
            return record
