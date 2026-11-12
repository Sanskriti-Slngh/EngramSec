"""Measurable-SPA benchmark: spa_router_lab, baseline vs general-web config.

Proves (independently of js_heavy_lab) that the general-web config recovers client-rendered,
pushState-routed SPA functionality. Capability recall is read from the fixture's own server-side
request oracle (each client view fires a tracking GET). Run with -I from the repo root:

    .venv/bin/python -I evaluation/spa_router_benchmark.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from urllib.parse import urlsplit  # noqa: E402

from agent1.explorer import Explorer  # noqa: E402
from agent1.schema import RunConfig  # noqa: E402
from development_apps.spa_router_lab import (  # noqa: E402
    MEMBER_COOKIE, ground_truth, start_spa_router_lab,
)


def _member_storage_state(url: str, out_dir: Path) -> Path:
    """An operator-provided pre-authenticated Playwright session (the member cookie). Agent 1 never
    types credentials; it just starts from this session identity (the storage_state_path mechanism)."""
    name, value = MEMBER_COOKIE.split("=", 1)
    host = urlsplit(url).hostname
    state = {"cookies": [{"name": name, "value": value, "domain": host, "path": "/",
                          "httpOnly": False, "secure": False, "sameSite": "Lax", "expires": -1}],
             "origins": []}
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "member_storage_state.json"
    p.write_text(json.dumps(state))
    return p

BASE = dict(
    policy="coverage", max_transitions=100, max_browser_actions=500, model_provider="none",
    allow_post_forms=False, state_aware_exploration=True, record_aware_graph=True,
    exploration_mode="fresh", replay_policy="shallow",
)
GENERAL_WEB = dict(
    robust_readiness=True, readiness_any_enabled=True, readiness_strategy="adaptive",
    loopback_origin_equivalence=True,
)
ARMS = {
    "A_frozen": {},
    "B_general_web": dict(GENERAL_WEB),
    # C uses the same general-web config PLUS an operator-provided member session (storage_state),
    # which should additionally unlock the member-only admin surface (roadblock #2 demo).
    "C_general_web_authenticated": {**GENERAL_WEB, "_authenticated": True},
}


def _recall(seen_paths: set[str], role: str) -> tuple[int, int, list[str]]:
    gt = ground_truth()
    caps = [c for c in gt["capabilities"] if c["role"] == role]
    hit = [c["id"] for c in caps if c["route"].lstrip("/") in {p.lstrip("/") for p in seen_paths}
           or c["route"] in seen_paths]
    missed = [c["id"] for c in caps if c["id"] not in hit]
    return len(hit), len(caps), missed


def run_arm(name: str, overrides: dict, seconds: float, storage_state: Path | None = None) -> dict:
    server, _thread, url = start_spa_router_lab()
    try:
        out = Path(tempfile.mkdtemp()) / "out"
        fields = dict(BASE)
        overrides = dict(overrides)
        authenticated = overrides.pop("_authenticated", False)
        fields.update(overrides)
        if authenticated:
            storage_state = _member_storage_state(url, out)
        if storage_state:
            fields["storage_state_path"] = storage_state
        cfg = RunConfig(start_url=url, output_dir=out, context_label=f"spa:{name}",
                        max_seconds=seconds, **fields)
        t0 = time.monotonic()
        art = Explorer(cfg, ROOT).run()
        wall = round(time.monotonic() - t0, 1)
        import urllib.request
        with urllib.request.urlopen(url + "__eval__/stats", timeout=5) as r:
            stats = json.load(r)
        seen = {k.split(" ", 1)[1] for k in stats}  # "GET /x" -> "/x"
        anon_hit, anon_tot, anon_missed = _recall(seen, "anonymous")
        result = {
            "arm": name, "wall_s": wall, "grouped_states": art.metrics.grouped_states,
            "anon_recall": f"{anon_hit}/{anon_tot}", "anon_missed": anon_missed,
            "boot_fired": "/api/boot" in seen,
            "paths": sorted(seen),
        }
        if storage_state:
            m_hit, m_tot, m_missed = _recall(seen, "member")
            result["member_recall"] = f"{m_hit}/{m_tot}"
            result["member_missed"] = m_missed
        return result
    finally:
        server.shutdown()


def main() -> None:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 90.0
    results = []
    for name, ov in ARMS.items():
        res = run_arm(name, ov, seconds)
        results.append(res)
        print(f"\n== {name}  wall={res['wall_s']}s  states={res['grouped_states']}  "
              f"boot={res['boot_fired']} ==")
        print(f"   anonymous recall: {res['anon_recall']}   missed: {res['anon_missed']}")
        if "member_recall" in res:
            print(f"   member recall:    {res['member_recall']}   missed: {res['member_missed']}")
        print(f"   server paths: {res['paths']}")
    (ROOT / "evaluation" / "results" / "spa_router_benchmark.json").write_text(
        json.dumps(results, indent=1))
    print("\nwrote evaluation/results/spa_router_benchmark.json")


if __name__ == "__main__":
    main()
