"""Phase 5 evidence tracer for missed annotated capabilities (Track A development labs only).

For each missed annotated capability it lists, from the frozen agent's own outputs, how far
the capability got along the causal chain:
  source page reached -> control observed -> control executed -> request observed -> ACG capability.
The earliest stage that was not reached is the *candidate* earliest causal failure. The
final category and root cause are assigned in the report by inspecting this evidence (and,
for development fixtures, the fixture source); this module never decides root causes alone.

Never run on WebExploitBench outputs.

  .venv/bin/python -m evaluation.comprehensive_failures [base]
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.comprehensive_eval import BASE, ENVS
from evaluation.comprehensive_metrics import _control_matches, _route_template

ANNOTATED = [e for e, s in ENVS.items() if s["gt"] == "capability"]


def _ops_seen(run: dict, cap) -> dict[str, int]:
    """Requests matching an annotated operation, by where they were recorded."""
    want = {(op.method.upper(), op.route) for op in cap.operations if op.channel == "http"}
    seen: Counter = Counter()

    def scan(events, where):
        for e in events or []:
            if (e.get("method", "GET").upper(), _route_template(e.get("url", ""))) in want:
                seen[where] += 1
    for t in run.get("transitions", []):
        scan(t.get("network"), "transition")
        scan(t.get("prerequisite_network"), "prerequisite")
    for n in run.get("navigation_evidence", []) or []:
        scan(n.get("network"), "navigation")
    for r in run.get("replays", []):
        scan(r.get("network"), "replay")
    for r in run.get("resource_evidence", []) or []:
        scan([r] if "url" in r else r.get("network"), "resource")
    return dict(seen)


def trace(env: str, out: Path) -> dict[str, Any]:
    from evaluation.active_ab import _gt
    gt = _gt(env)
    run = json.loads((out / "run.json").read_text())
    row = json.loads((out / "trial.json").read_text())
    missed = set(row["reference"]["unmatched_annotated"])
    obs = run.get("observations", []) + run.get("replay_observations", [])
    routes_reached = {_route_template(o.get("url", "")) for o in obs}
    result: dict[str, Any] = {}
    for cap in gt.capabilities:
        if cap.id not in missed:
            continue
        sources = sorted({ep.source_route for ep in cap.entry_points if ep.source_route})
        observed = [(o, c) for o in obs for c in o.get("controls", [])
                    if _control_matches(cap, c, _route_template(o.get("url", "")))]
        executed = [t for t in run.get("transitions", []) if _control_matches(
            cap, {**t["action"], "skip_reason": None},
            _route_template(next((o.get("url", "") for o in obs if o["id"] == t.get("source_observation_id")), "")))]
        ops = _ops_seen(run, cap)
        target_routes = sorted({op.route for op in cap.operations})
        stage = ("source_page_not_reached" if sources and not (set(sources) & routes_reached) else
                 "control_not_observed" if not observed else
                 "control_not_executed" if not executed else
                 "execution_failed_or_refused" if not any(t["status"] in ("observed", "replay_validated") for t in executed) else
                 "no_matching_request" if cap.operations and not ops else
                 "evidence_present_capability_unmatched")
        result[cap.id] = {
            "effect_risk": cap.effect_risk,
            "annotated_entry_points": [ep.model_dump(exclude_none=True) for ep in cap.entry_points],
            "annotated_operations": [f"{op.method} {op.route}" for op in cap.operations],
            "source_routes_required": sources, "source_routes_reached": sorted(set(sources) & routes_reached),
            "target_routes_reached": sorted(set(target_routes) & routes_reached),
            "controls_observed": len(observed),
            "control_skip_reasons": dict(Counter(c.get("skip_reason") or "none" for _, c in observed)),
            "transitions_matching": len(executed),
            "transition_outcomes": dict(Counter(f"{t['status']}:{(t.get('error') or '').split(':', 1)[0]}" for t in executed)),
            "requests_matching_operation": ops,
            "furthest_stage_failed": stage,
        }
    return {"env": env, "missed": result,
            "run_context": {"terminated_by": row["efficiency"]["terminated_by"],
                            "failed_action_error_classes": row["efficiency"]["failed_action_error_classes"],
                            "routes_reached": sorted(routes_reached)}}


def main() -> None:
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE
    report = {}
    for env in ANNOTATED:
        trials = sorted((base / env).glob("trial_*/trial.json"))
        report[env] = [trace(env, p.parent) for p in trials if json.loads(p.read_text())["status"] == "ok"]
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
