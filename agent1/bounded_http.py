"""Memory-bounded passive GET for the typed-resource spider.

Playwright's APIRequestContext buffers a whole response body before Python can
inspect it, so a size check applied afterwards does not bound memory. This
reader streams with the standard library and stops reading once
`max_body_bytes` decoded bytes are held, closing the connection instead of
draining it. It never follows redirects (the caller enforces scope and charges
each hop) and never sends a body. It has no cookie jar: the caller supplies the
browser context's Cookie header and receives every Set-Cookie header, so the
browser's authorized session stays consistent with the server
(see agent1/cookies.py).

A total deadline bounds wall-clock time: reads use `read1`, which returns
whatever bytes are available instead of blocking until a full chunk arrives.
"""
from __future__ import annotations

import http.client
import ssl
import time
import zlib
from dataclasses import dataclass, field
from urllib.parse import urlsplit

READ_CHUNK = 64 * 1024
SUPPORTED_ENCODINGS = {"", "identity", "gzip", "x-gzip", "deflate"}


@dataclass
class BoundedResponse:
    url: str
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    # complete | empty | truncated | incomplete | timeout | invalid_framing |
    # unsupported_encoding | unsupported_transfer_coding | not_read
    body_status: str = "complete"
    wire_bytes: int = 0
    set_cookies: list[str] = field(default_factory=list)


def bounded_get(url: str, *, max_body_bytes: int, timeout_s: float = 5.0, cookie_header: str | None = None,
                read_body: bool = True, deadline_s: float | None = None) -> BoundedResponse:
    started = time.monotonic()
    deadline = started + (deadline_s if deadline_s is not None else max(timeout_s, 1.0) * 3)
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("bounded_get supports absolute http(s) URLs only")
    target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    connection_class = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    kwargs = {"timeout": timeout_s}
    if parts.scheme == "https":
        kwargs["context"] = ssl.create_default_context()
    connection = connection_class(parts.hostname, parts.port, **kwargs)  # type: ignore[arg-type]
    headers = {"Accept": "*/*", "Accept-Encoding": "gzip, deflate", "User-Agent": "EngramSec-Agent1/0.1 (passive)"}
    if cookie_header:
        headers["Cookie"] = cookie_header
    try:
        connection.request("GET", target, headers=headers)
        response = connection.getresponse()
        result = BoundedResponse(url=url, status=response.status,
                                 headers={k.lower(): v for k, v in response.getheaders()},
                                 set_cookies=list(response.msg.get_all("Set-Cookie") or []))
        transfer = result.headers.get("transfer-encoding", "").strip().lower()
        if transfer and transfer != "chunked":
            # http.client only decodes a lone "chunked"; any other transfer
            # coding would be read to close and parsed as garbage.
            result.body_status = "unsupported_transfer_coding"
            return result
        lengths = {v.strip() for v in (response.msg.get_all("Content-Length") or [])}
        if lengths and "transfer-encoding" not in result.headers and (
                len(lengths) > 1 or not all(v.isdigit() for v in lengths)):
            # RFC 9112 section 6.3: an invalid Content-Length without
            # Transfer-Encoding is unrecoverable framing; a user agent must
            # discard the response instead of guessing the body.
            result.body_status = "invalid_framing"
            return result
        if not read_body or response.status in {204, 304} or 100 <= response.status < 200:
            result.body_status = "not_read" if not read_body else "empty"
            return result
        encoding = result.headers.get("content-encoding", "").strip().lower()
        if encoding not in SUPPORTED_ENCODINGS:
            result.body_status = "unsupported_encoding"
            return result
        decoder = zlib.decompressobj(47) if encoding in {"gzip", "x-gzip", "deflate"} else None
        raw_deflate_tried = encoding != "deflate"
        buffer = bytearray()
        truncated = timed_out = False
        try:
            while True:
                if time.monotonic() >= deadline:
                    timed_out = True
                    break
                remaining = deadline - time.monotonic()
                if connection.sock is not None:
                    connection.sock.settimeout(max(0.05, min(timeout_s, remaining)))
                chunk = response.read1(READ_CHUNK)
                if not chunk:
                    break
                result.wire_bytes += len(chunk)
                room = max_body_bytes - len(buffer)
                if decoder is not None:
                    try:
                        data = decoder.decompress(chunk, room + 1)
                    except zlib.error:
                        if raw_deflate_tried or result.wire_bytes != len(chunk):
                            raise
                        # Some servers send raw DEFLATE for "deflate"; browsers accept it.
                        raw_deflate_tried = True
                        decoder = zlib.decompressobj(-15)
                        data = decoder.decompress(chunk, room + 1)
                    if decoder.unconsumed_tail:
                        truncated = True
                else:
                    data = chunk
                if len(data) > room:
                    buffer.extend(data[:room])
                    truncated = True
                else:
                    buffer.extend(data)
                if truncated or result.wire_bytes > max_body_bytes:
                    truncated = True
                    break
        except http.client.IncompleteRead as exc:
            buffer.extend(exc.partial[: max(0, max_body_bytes - len(buffer))])
            result.body_status = "incomplete"
        except TimeoutError:
            timed_out = True
        except zlib.error:
            result.body_status = "unsupported_encoding"
            buffer.clear()
        if result.body_status == "complete":
            if timed_out:
                result.body_status = "timeout"
            elif decoder is not None and not truncated and not decoder.eof:
                # A compressed stream that ends without its end marker / trailer.
                result.body_status = "incomplete"
        result.body = bytes(buffer)
        if result.body_status == "complete":
            result.body_status = "truncated" if truncated else ("empty" if not buffer else "complete")
        return result
    finally:
        connection.close()
