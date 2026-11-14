"""Matched baseline vs fix comparison (recovery milestone).

Baseline: the reproduced integrated configurations (crawlground_integrated_readonly_600,
crawlmaze_integrated_180). Fix: identical settings plus restoration_policy="contract",
restoration_shortcut="direct_url", well_known_discovery=True. Everything is computed post-run
from the agent's own outputs and the testbeds' own post-run scores.

  .venv/bin/python -m evaluation.fix_comparison
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any

from evaluation.comprehensive_config import ROOT

BASE = ROOT / "agent1" / "experiments" / "recovery_transfer" / "current"
PAIRS = {"crawlground": ("crawlground_integrated_readonly_600", "crawlground_integrated_readonly_600_fix"),
         "crawl_maze": ("crawlmaze_integrated_180", "crawlmaze_integrated_180_fix")}
EXTRA = {"crawlground_historical_39": "crawlground_serious_600"}


def run_metrics(out: Path, env: str) -> dict[str, Any]:
    from agent1.model.importer import import_run_artifact
    from agent1.model.materialize import materialize
    trial = json.loads((out / "trial.json").read_text())
    run = json.loads((out / "run.json").read_text())
    m = run["metrics"]
    export = materialize(import_run_artifact(run, "run.json", env)).model_dump(mode="json")
    caps = [c for c in export["capabilities"] if c["status"] in ("observed", "reproduced", "verified")]
    reproduced = [c for c in caps if c["status"] in ("reproduced", "verified")]
    trans = run["transitions"]
    executed_with_requests = sum(1 for t in trans if t.get("status") in ("observed", "replay_validated")
                                 and any(e.get("method") and (e.get("resource_type") in ("xhr", "fetch")
                                                              or e["method"].upper() != "GET") for e in t.get("network", [])))
    score = trial.get("score") or {}
    if env == "crawlground":
        reference = score.get("markers_scored")
    else:
        reference = ((score.get("score") or {}).get("coverage_total") or {}).get("any_fetch")
    well_known = sum(1 for r in run.get("resource_evidence", []) if r.get("source_type") in ("robots", "well_known")
                     and r.get("status") == "fetched")
    actions = m["browser_actions"]
    rc = m.get("restoration_contract") or {}
    writes = sum(1 for t in trans for e in t.get("network", [])
                 if e.get("method", "GET").upper() not in {"GET", "HEAD", "OPTIONS"} and not e.get("failure"))
    out_scope = sum(1 for t in trans for e in t.get("network", [])
                    if e.get("url", "").startswith("http") and not e["url"].startswith(run["config"]["start_url"].rstrip("/"))
                    and not e.get("failure"))
    return {
        "reference": reference, "browser_actions": actions, "elapsed_s": m.get("elapsed_seconds"),
        "driver_monotonic_s": trial.get("driver_monotonic_s"),
        "capabilities": len(caps), "capabilities_reproduced": len(reproduced),
        "transitions_observed": m.get("transitions_observed"),
        "replay_validated": sum(1 for t in trans if t.get("status") == "replay_validated"),
        "request_structures_verified": m.get("replay_structures_verified"),
        "executed_application_requests": executed_with_requests,
        "restoration_actions": m.get("restoration_actions"), "root_reloads": m.get("root_reloads"),
        "shape_tolerance_acceptances": sum("interaction shape remained usable" in n for n in run.get("notes", [])),
        "contract_accepted": rc.get("accepted", 0), "contract_refused": rc.get("refused", 0),
        "contract_refused_by_reason": rc.get("refused_by_reason"),
        "direct_url": rc.get("direct_url"),
        "contract_overhead_ms": round((rc.get("evaluation_ms") or 0) + ((rc.get("region_capture") or {}).get("ms") or 0), 1),
        "well_known_fetched": well_known,
        "state_changing_requests": writes, "completed_requests_off_start_origin": out_scope,
        "failed_transitions": m.get("transitions_failed"),
        "per_100_actions": {"reference": round(100 * (reference or 0) / actions, 2),
                            "capabilities": round(100 * len(caps) / actions, 2),
                            "reproduced_capabilities": round(100 * len(reproduced) / actions, 2),
                            "replay_validated": round(100 * sum(1 for t in trans if t.get("status") == "replay_validated")
                                                      / actions, 2)},
    }


def collect(variant: str, env: str) -> list[dict[str, Any]]:
    rows = []
    for out in sorted((BASE / variant).glob("trial_*")):
        if (out / "trial.json").exists() and (out / "run.json").exists():
            rows.append({"trial": out.name, **run_metrics(out, env)})
    return rows


def med(rows: list[dict], key: str):
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    return median(vals) if vals else None


def main() -> None:
    result: dict[str, Any] = {"pairs": {}}
    for env, (base, fix) in PAIRS.items():
        b, f = collect(base, env), collect(fix, env)
        result["pairs"][env] = {"baseline_variant": base, "fix_variant": fix, "baseline": b, "fix": f,
                                "medians": {k: {"baseline": med(b, k), "fix": med(f, k)} for k in (
                                    "reference", "browser_actions", "elapsed_s", "capabilities",
                                    "capabilities_reproduced", "replay_validated", "request_structures_verified",
                                    "executed_application_requests", "restoration_actions", "root_reloads",
                                    "shape_tolerance_acceptances", "contract_overhead_ms", "state_changing_requests")}}
    for name, variant in EXTRA.items():
        result[name] = collect(variant, "crawlground")
    path = ROOT / "evaluation" / "results" / "recovery_fix_comparison.json"
    path.write_text(json.dumps(result, indent=1, default=str) + "\n")
    for env, p in result["pairs"].items():
        print(env)
        for k, v in p["medians"].items():
            print(f"  {k:32s} baseline={v['baseline']}  fix={v['fix']}")


if __name__ == "__main__":
    main()
