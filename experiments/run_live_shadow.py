"""Phase 2 step 6: limited live shadow comparison on authorized local development labs.

Each lab runs twice at its established baseline configuration: legacy only, and
legacy with the shadow Capability Tour Scheduler. The legacy frontier executes
every action in both runs. Writes an aggregate summary (no raw evidence) to
agent1/experiments/live_shadow_<date>/summary.json; raw artifacts stay in ignored
per-run directories.

Run: .venv/bin/python experiments/run_live_shadow.py
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent1.explorer import Explorer  # noqa: E402
from agent1.model.importer import import_run_artifact  # noqa: E402
from agent1.model.materialize import materialize  # noqa: E402
from agent1.schema import RunConfig  # noqa: E402
from evaluation.ground_truth import load_ground_truth  # noqa: E402
from evaluation.score_acg import score_capabilities  # noqa: E402

LABS = {
    # CRUD with existing records (configuration of tests/test_state_aware_lab.py)
    "stateful_lab": dict(policy="multidimensional", exploration_mode="persistent", max_seconds=35, max_transitions=30,
                         max_browser_actions=100, settle_ms=60, action_timeout_ms=1500, allow_post_forms=True,
                         replay_policy="structure", state_aware_exploration=True),
    # Dynamic JavaScript-heavy lab (configuration of the archived p2 baseline runs)
    "js_heavy_lab": dict(policy="coverage", exploration_mode="persistent", max_seconds=60, max_transitions=30,
                         max_browser_actions=140, settle_ms=30, action_timeout_ms=5000, allow_post_forms=True,
                         replay_reserve_fraction=0.35),
    # Replay lab with runtime handler revisions (configuration of the archived structure-replay probe)
    "replay_lab": dict(policy="multidimensional", exploration_mode="persistent", max_seconds=90, max_transitions=80,
                       max_browser_actions=90, settle_ms=150, action_timeout_ms=5000, allow_post_forms=False,
                       max_total_http_requests=1000, replay_policy="structure", runtime_listener_observation="revisit"),
}
HOST = re.compile(r"127\.0\.0\.1:\d+")


def _start(name: str):
    if name == "stateful_lab":
        from development_apps.stateful_lab import start_stateful_lab
        server, url, _, log = start_stateful_lab(Path(tempfile.mkdtemp()) / "lab.sqlite")
        return server, url
    if name == "js_heavy_lab":
        from development_apps.js_heavy_lab import start_js_heavy_lab
        server, _, url = start_js_heavy_lab()
        return server, url
    from development_apps.replay_lab import start_replay_lab
    server, _, url = start_replay_lab()
    return server, url


def _config(name: str) -> dict:
    """The lab's archived baseline configuration in full when available (all budgets and flags)."""
    from evaluation.datasets import archive_paths
    archived = [p for p in archive_paths(name) if p.exists()]
    if not archived:
        return dict(LABS[name])
    data = json.loads(archived[0].read_text())
    if "config" not in (data.get("artifact") or data):
        return dict(LABS[name])                 # Graph A archive: no stored configuration
    config = dict((data.get("artifact") or data)["config"])
    for key in ("start_url", "output_dir", "run_id", "resume_from", "acg_evidence", "shadow_tours"):
        config.pop(key, None)
    return config


def run(name: str, shadow: bool, out: Path) -> dict:
    server, url = _start(name)
    try:
        start = time.monotonic()
        explorer = Explorer(RunConfig(start_url=url, output_dir=out, shadow_tours=shadow, **_config(name)), ROOT)
        artifact = explorer.run()
        seconds = time.monotonic() - start
    finally:
        server.shutdown()
    records = import_run_artifact(artifact.model_dump(mode="json"), "run.json", name)
    gt = load_ground_truth(ROOT / "evaluation" / "annotations" / f"{name}.json")
    caps = score_capabilities(gt, materialize(records).model_dump(mode="json"), records)
    exploration = [(t.action.kind, t.action.css_path, HOST.sub("H", t.action.target or "")) for t in artifact.transitions]
    return {"seconds": round(seconds, 1), "browser_actions": artifact.metrics.browser_actions,
            "transitions": len(artifact.transitions), "replays": len(artifact.replays),
            "legacy_m1a_recall": caps["m1a_recall"], "exploration": exploration,
            "shadow": explorer.shadow_summary}


def main() -> None:
    stamp = time.strftime("%Y%m%d")
    base = ROOT / "agent1" / "experiments" / f"live_shadow_{stamp}"
    results = {}
    for name in LABS:
        off = run(name, False, base / name / "off")
        on = run(name, True, base / name / "on")
        results[name] = {
            "config": {k: v for k, v in _config(name).items() if "budget" in k or k.startswith("max_") or k in ("policy", "exploration_mode", "replay_policy")},
            "legacy_off": {k: v for k, v in off.items() if k not in {"exploration", "shadow"}},
            "legacy_with_shadow": {k: v for k, v in on.items() if k not in {"exploration", "shadow"}},
            "exploration_identical": off["exploration"] == on["exploration"],
            "shadow": on["shadow"],
        }
        print(name, json.dumps({k: results[name][k] for k in ("legacy_off", "legacy_with_shadow", "exploration_identical")}))
    (base / "summary.json").write_text(json.dumps(results, indent=1, default=str))
    print("written", base / "summary.json")


if __name__ == "__main__":
    main()
