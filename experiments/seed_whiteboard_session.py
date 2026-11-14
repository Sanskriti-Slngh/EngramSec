#!/usr/bin/env python3
"""Operator setup for the whiteboard generalization run (not part of Agent 1).

Creates a throwaway account and two (empty) canvases on an isolated
local whiteboard stack, then saves the authenticated browser storage state for
`--storage-state`. The password is random and never written to disk; the
storage state file holds a session cookie and must stay outside the repository.
"""
from __future__ import annotations

import argparse
import secrets
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:45173")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    user = "engram" + secrets.token_hex(3)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        api = context.request
        response = api.post(f"{args.url}/api/signup", data={
            "username": user, "email": f"{user}@engramsec-eval.org", "password": secrets.token_urlsafe(18)})
        assert response.ok, (response.status, response.text()[:200])
        canvases = []
        for name in ("Design review", "Sprint retro"):
            created = api.post(f"{args.url}/api/canvases", data={"name": name})
            assert created.ok, (created.status, created.text()[:200])
            canvases.append(created.json()["id"])
        context.storage_state(path=str(args.out))
        browser.close()
    print({"user": user, "canvases": len(canvases), "storage_state": str(args.out)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
