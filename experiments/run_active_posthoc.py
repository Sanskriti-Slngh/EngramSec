"""Exploratory (NOT preregistered) post-hoc diagnostic for Phase 3.

After the frozen A/B, two executor-scheduler feedback defects were fixed
(executor refusals become blocked questions; role identity compared by session
context). One tour trial (seed 101) per environment tests whether those defects
explain the losses. Results never change the preregistered verdict.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation import active_ab  # noqa: E402

if __name__ == "__main__":
    base = ROOT / "agent1" / "experiments" / f"active_posthoc_{time.strftime('%Y%m%d')}"
    rows, t0 = [], time.monotonic()
    envs = sys.argv[1:] or active_ab.ENVIRONMENTS + [active_ab.DIAGNOSTIC]
    label = "_v2" if len(sys.argv) > 1 else ""
    for env in envs:
        row = active_ab.run_one(env, "tour", 0, base / (env + label))
        rows.append(row)
        print(env, row["auc_actions"], row["final_recall"], row["browser_actions"], row["transitions"],
              row["restoration_share"], row["safety"], (row.get("tour") or {}).get("executor"),
              {k: v for k, v in (row["server_state"] or {}).items() if k != "notes"}, flush=True)
    out = {"label": "exploratory post-hoc diagnostic; not preregistered; does not change the A/B verdict",
           "fixes": ["executor refusals are fed back as blocked questions",
                     "role identity compared by session context (cookie-name suffix ignored)"]
                     + (["verification actions counted in the scheduler's share (active runner)"] if label else []),
           "live_seconds": round(time.monotonic() - t0, 1), "rows": rows}
    (ROOT / "evaluation" / "results" / f"active_ab_posthoc{label}.json").write_text(json.dumps(out, indent=1, default=str))
