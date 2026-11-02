"""Structural URL abstraction: identifier positions become {id}.

Only formats are recognised (integers, UUIDs, long hexadecimal strings), never
application words. Query values are never kept, except dispatch values passed
in explicitly as pseudonymous tokens.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlsplit

IDENTIFIER = re.compile(r"^(?:\d+|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|(?=[0-9a-f]*\d)[0-9a-f]{16,})$", re.I)
STRONG_IDENTIFIER = re.compile(r"^(?:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|(?=[0-9a-f]*\d)[0-9a-f]{16,})$", re.I)
DISPATCH_VALUE = re.compile(r"^[A-Za-z][\w.\-/]{0,39}$")


def is_identifier(value: str) -> bool:
    return bool(IDENTIFIER.match(value))


def path_route(path: str) -> str:
    segments = [s for s in (path or "/").split("/") if s]
    return "/" + "/".join("{id}" if is_identifier(s) else s for s in segments)


def identifier_segments(path: str) -> list[tuple[str, int, str]]:
    """(route, segment index, value) for every identifier segment of a path."""
    route = path_route(path)
    segments = [s for s in (path or "/").split("/") if s]
    return [(route, i, s) for i, s in enumerate(segments) if is_identifier(s)]


def query_pairs(url: str) -> list[tuple[str, str]]:
    return parse_qsl(urlsplit(url).query, keep_blank_values=True)


def split(url: str) -> tuple[str, list[tuple[str, str]], str]:
    parts = urlsplit(url or "")
    return parts.path or "/", query_pairs(url or ""), parts.fragment


def strip_positions(locator: str) -> str:
    return re.sub(r":nth-(?:of-type|child)\(\d+\)", "", locator or "")
