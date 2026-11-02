"""Pseudonymous tokens for identifier and dispatch values.

Offline materialization must be deterministic, so the key is derived from a
caller-supplied namespace (by default the evidence-log digest). These tokens
are pseudonymous, not secret: low-entropy values can be recovered by guessing.
A live engine must use a random in-memory key (design §4.2); exports produced
from private archives stay local.
"""
from __future__ import annotations

import hashlib
import hmac


def token(namespace: str, value: str) -> str:
    return hmac.new(namespace.encode(), value.encode(), hashlib.sha256).hexdigest()[:12]
