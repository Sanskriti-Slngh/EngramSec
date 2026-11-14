"""Validate sanitized ZAP traditional-spider observations as external evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from .schema import ExternalDiscoveryEvidence
from .state import digest

NAME = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
METHOD = re.compile(r"^[A-Z]{1,12}$")


def _origin(value: str) -> str:
    parts = urlsplit(value)
    if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username
            or parts.password or parts.path not in {"", "/"} or parts.query or parts.fragment):
        raise ValueError("invalid explicit ZAP source origin")
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("invalid explicit ZAP source origin") from exc
    host = parts.hostname.lower()
    netloc = f"[{host}]" if ":" in host else host
    return urlunsplit((parts.scheme, netloc + (f":{port}" if port else ""), "", "", ""))


def load_zap_evidence(path: Path, source_origin: str, target_url: str):
    if path.stat().st_size > 4_000_000:
        raise ValueError("ZAP evidence file exceeds size limit")
    content = path.read_bytes()
    payload = json.loads(content)
    if not isinstance(payload, dict) or payload.get("schema") != "zap-http-history-1":
        raise ValueError("unsupported ZAP evidence format")
    approved = _origin(source_origin)
    if _origin(str(payload.get("source_origin", ""))) != approved:
        raise ValueError("ZAP source origin does not match explicit mapping")
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not NAME.fullmatch(run_id):
        raise ValueError("invalid ZAP run identity")
    records = payload.get("records")
    if not isinstance(records, list) or len(records) > 10_000:
        raise ValueError("invalid ZAP history records")
    requests, elapsed = payload.get("request_upper_bound"), payload.get("elapsed_seconds")
    if isinstance(requests, bool) or not isinstance(requests, int) or not 0 <= requests <= 1_000_000:
        raise ValueError("invalid external request upper bound")
    if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not 0 <= elapsed <= 86_400:
        raise ValueError("invalid external elapsed time")
    target = urlsplit(target_url)
    target_origin = urlunsplit((target.scheme, target.netloc, "", "", ""))
    file_digest = hashlib.sha256(content).hexdigest()
    output, seen, rejected = [], set(), 0
    for index, row in enumerate(records):
        if not isinstance(row, dict):
            rejected += 1
            continue
        raw, method, status = row.get("path"), row.get("method"), row.get("status")
        names = row.get("parameter_names", [])
        if not isinstance(raw, str) or not isinstance(method, str) or not METHOD.fullmatch(method):
            rejected += 1
            continue
        decoded = unquote(raw)
        if (not decoded.startswith("/") or decoded.startswith("//") or "\\" in decoded
                or any(ord(c) < 32 for c in decoded) or any(c in decoded for c in "?#%")
                or any(part in {".", ".."} for part in decoded.split("/"))):
            rejected += 1
            continue
        if (not isinstance(names, list) or len(names) > 100
                or any(not isinstance(n, str) or not NAME.fullmatch(n) for n in names)):
            rejected += 1
            continue
        if isinstance(status, bool) or (status not in (None, 0) and (not isinstance(status, int) or not 100 <= status <= 599)):
            rejected += 1
            continue
        mapped = target_origin + quote(decoded, safe="/!$&'()*+,-.:;=@_~")
        key = (mapped, method, status, tuple(sorted(set(names))))
        if key in seen:
            continue
        seen.add(key)
        output.append(ExternalDiscoveryEvidence(
            id="zap_" + digest([run_id, index, key], 20), engine="zap-traditional",
            run_id=run_id, source_origin=approved, source_record_id=f"record-{index}",
            export_digest=file_digest, mapped_url=mapped, method=method,
            http_status=status or None, parameter_names=sorted(set(names)),
            status="external_response" if status else "external_candidate",
        ))
    return output, rejected, requests, float(elapsed)
