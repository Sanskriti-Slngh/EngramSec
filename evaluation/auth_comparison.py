"""Anonymous vs authenticated exploration comparison (matched budget; only the login differs).

For each target with an auth pair under agent1/experiments/recovery_transfer/wxb_auth/, compares the
anonymous control against the authenticated run on new functional areas, executed and reproduced
capabilities, authentication outcome, and the documented vulnerability locations each one mapped.

  .venv/bin/python -m evaluation.auth_comparison
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaluation.comprehensive_config import ROOT
from evaluation.wxb_functional_reachability import FUNCTIONAL_TRIAL, assess
from evaluation.wxb_reachability import ground_truth

BASE = ROOT / "agent1" / "experiments" / "recovery_transfer" / "wxb_auth"
OUT = ROOT / "evaluation" / "results" / "auth_comparison.json"


def _load(variant: str, trial: int = 0) -> tuple[dict, dict] | None:
    d = BASE / variant / f"trial_{trial}"
    if not (d / "run.json").exists():
        return None
    return json.loads((d / "run.json").read_text()), (
        json.loads((d / "trial.json").read_text()) if (d / "trial.json").exists() else {})


def _caps(run: dict, env: str) -> dict[str, int]:
    from agent1.model.importer import import_run_artifact
    from agent1.model.materialize import materialize
    export = materialize(import_run_artifact(run, "run.json", env)).model_dump(mode="json")
    caps = [c for c in export["capabilities"] if c["status"] in ("observed", "reproduced", "verified")]
    return {"observed_or_better": len(caps),
            "reproduced": sum(1 for c in caps if c["status"] in ("reproduced", "verified"))}


def main() -> None:
    gt = ground_truth()
    out: dict[str, Any] = {"targets": {}}
    for target in sorted({d.name.split("_auth_")[0].replace("wxb_", "") for d in BASE.glob("wxb_*_auth_*")}
                         if BASE.exists() else []):
        anon = _load(f"wxb_{target}_auth_anon")
        auth = _load(f"wxb_{target}_auth_login")
        if not anon or not auth:
            continue
        (anon_run, _), (auth_run, auth_trial) = anon, auth
        routes = lambda r: {o["route_pattern"] for o in r.get("observations", [])}
        anon_routes, auth_routes = routes(anon_run), routes(auth_run)
        locs = [g for g in gt if g["target"] == target]
        loc_cmp = []
        for g in locs:
            a = assess(g["location_path"], anon_run, {})["status"]
            b = assess(g["location_path"], auth_run, {})["status"]
            if a != b:
                loc_cmp.append({"vuln_id": g["vuln_id"], "location": g["location_path"], "anon": a, "auth": b})
        out["targets"][target] = {
            "auth": auth_trial.get("auth"),
            "actions": {"anon": anon_run["metrics"]["browser_actions"], "auth": auth_run["metrics"]["browser_actions"]},
            "routes": {"anon": len(anon_routes), "auth": len(auth_routes),
                       "new_under_auth": sorted(auth_routes - anon_routes)[:40],
                       "new_under_auth_count": len(auth_routes - anon_routes)},
            "capabilities": {"anon": _caps(anon_run, target), "auth": _caps(auth_run, target)},
            "vuln_locations_changed": loc_cmp,
            "host_sleep": {"anon": _load(f"wxb_{target}_auth_anon")[1].get("host_sleep_affected"),
                           "auth": auth_trial.get("host_sleep_affected")},
        }
        t = out["targets"][target]
        print(f"{target}: auth={(t['auth'] or {}).get('status')} routes {t['routes']['anon']}->{t['routes']['auth']} "
              f"(+{t['routes']['new_under_auth_count']}) caps {t['capabilities']['anon']}->{t['capabilities']['auth']} "
              f"loc_changes={len(loc_cmp)}")
    OUT.write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
