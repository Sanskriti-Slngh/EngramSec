"""Functional reachability on public WebExploitBench targets (post-run; Agent 1 is a mapper).

Not a vulnerability-detection score. For each officially documented vulnerability location
(metadata.json "Location", path only), this asks whether Agent 1 mapped the *functionality* there,
and if not, exactly why. Evidence is the agent's own records only.

Mapping status (highest that holds):
  exercised      an executed or replay-validated agent action sent an unblocked request to the
                 location, or landed on it (function exercised)
  observed       the browser or spider received a response from the location (page/endpoint seen)
  referenced     the location appears in a link, form, script reference or a policy-blocked request
  area_only      nothing at the location itself, but the agent mapped pages/requests in the same
                 route family (the parent path) - the surrounding feature area
  not_mapped     none of the above

Cause for anything below "exercised" (first applicable, evidence-based):
  blocked_by_policy        an attempt existed but the write policy blocked it
  discovered_not_chosen    referenced but never selected by the frontier before the run ended
  authentication_required  the location or its area answered 401/403 or redirected to a login page
  budget_exhausted         the run stopped on the HTTP/time/action budget
  not_referenced           the application's own pages and scripts never referenced it (reachable
                           only by guessing paths, which Agent 1 does not do)

  .venv/bin/python -m evaluation.wxb_functional_reachability
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from evaluation.comprehensive_config import ROOT
from evaluation.wxb_reachability import TARGETS, ground_truth

RUNS = {
    "frozen (5dfee96), 600 s": "agent1/experiments/recovery_transfer/wxb/wxb_{t}/trial_0",
    "functional (ea16b4f), generous budgets + deployment fixes + disposable":
        "agent1/experiments/recovery_transfer/wxb_functional/wxb_{t}_functional/trial_{trial}",
}
# SiyuCMS trial_0 failed (host sleep interrupted its start navigation); its clean rerun is trial_1.
FUNCTIONAL_TRIAL = {"siyucms": 1}
LOGIN = re.compile(r"log[-_]?in|sign[-_]?in|auth", re.I)


def _rx(loc: str) -> re.Pattern:
    loc = loc.rstrip("/") or "/"
    return re.compile("^" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(loc)) + r"(/|$)", re.I)


def assess(loc: str, run: dict[str, Any], trial: dict[str, Any]) -> dict[str, Any]:
    at = _rx(loc)
    parent = "/".join(loc.rstrip("/").split("/")[:-1]) or "/"
    in_area = (lambda p: p.lower().startswith(parent.lower().rstrip("/") + "/")) if parent != "/" else (lambda p: False)
    path = lambda u: urlsplit(u or "").path or "/"
    trans = run.get("transitions", [])
    obs = {o["id"]: o for o in run.get("observations", [])}
    ev: dict[str, Any] = {}

    exercised = [t["id"] for t in trans if t.get("status") in ("observed", "replay_validated") and (
        any(at.match(path(e.get("url"))) and not e.get("failure") for e in t.get("network", []))
        or at.match(path((obs.get(t.get("result_observation_id")) or {}).get("url"))))]
    responses = [e for t in trans for e in t.get("network", []) if at.match(path(e.get("url"))) and e.get("status")]
    responses += [e for n in run.get("navigation_evidence", []) for e in n.get("network", [])
                  if at.match(path(e.get("url"))) and e.get("status")]
    spider_ok = [r for r in run.get("resource_evidence", []) if at.match(path(r.get("url"))) and r.get("http_status")]
    blocked = [e for t in trans for e in t.get("network", []) if at.match(path(e.get("url")))
               and e.get("failure") == "net::ERR_ACCESS_DENIED"]
    refs = [c for o in run.get("observations", []) for c in o.get("controls", []) if at.match(path(c.get("target")))]
    refs += [f for o in run.get("observations", []) for f in o.get("forms", []) if at.match(path(f.get("action")))]
    refs += [r for r in run.get("resource_evidence", []) if at.match(path(r.get("url")))]
    area = sorted({path(u) for u in (
        [o["url"] for o in run.get("observations", [])]
        + [e.get("url") for t in trans for e in t.get("network", []) if not e.get("failure")]
        + [r.get("url") for r in run.get("resource_evidence", []) if r.get("status") == "fetched"]) if u and in_area(path(u))})
    statuses = sorted({int(e["status"]) for e in responses if e.get("status")} |
                      {int(r["http_status"]) for r in spider_ok if r.get("http_status")})

    if exercised:
        status = "exercised"
    elif responses or spider_ok:
        status = "observed"
    elif refs or blocked:
        status = "referenced"
    elif area:
        status = "area_only"
    else:
        status = "not_mapped"
    ev.update(exercised_actions=len(exercised), responses=len(responses) + len(spider_ok), statuses=statuses,
              references=len(refs), blocked_attempts=len(blocked), area_paths=len(area), area_examples=area[:5])

    cause = None
    if status != "exercised":
        auth = any(s in (401, 403) for s in statuses) or any(
            e.get("status") in (301, 302, 303, 307, 308) and LOGIN.search(json.dumps(e)) for e in responses)
        notes = " ".join(run.get("notes", [])).lower()
        budget = ("budget exhausted" in notes or run["metrics"].get("browser_actions", 0)
                  >= run["config"].get("max_browser_actions", 1) - 2)
        if blocked:
            cause = "blocked_by_policy"
        elif auth:                     # explicit 401/403 or login redirect only
            cause = "authentication_required"
        elif refs or status == "observed":
            cause = "discovered_not_chosen" + (" (budget exhausted)" if budget else "")
        elif budget and status in ("area_only",):
            cause = "budget_exhausted"
        else:
            cause = "not_referenced" + (" (run also budget-limited)" if budget else "")
    return {"status": status, "cause": cause, "evidence": ev}


def main() -> None:
    gt = ground_truth()
    out: dict[str, Any] = {"what_this_measures": "functional mapping of documented vulnerability locations; "
                                                 "not vulnerability detection",
                           "ground_truth": "official metadata.json Location (path only)", "runs": {}}
    for label, pattern in RUNS.items():
        rows = []
        for t in TARGETS:
            d = ROOT / pattern.format(t=t, trial=FUNCTIONAL_TRIAL.get(t, 0))
            if not (d / "run.json").exists():
                continue
            run = json.loads((d / "run.json").read_text())
            trial = json.loads((d / "trial.json").read_text()) if (d / "trial.json").exists() else {}
            m = run["metrics"]
            for g in (x for x in gt if x["target"] == t):
                rows.append({**g, **assess(g["location_path"], run, trial),
                             "run": {"actions": m.get("browser_actions"), "elapsed_s": m.get("elapsed_seconds"),
                                     "http": m.get("observed_http_requests"),
                                     "deployment_fixes": trial.get("deployment_fixes")}})
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        causes: dict[str, int] = {}
        for r in rows:
            if r["cause"]:
                causes[r["cause"]] = causes.get(r["cause"], 0) + 1
        out["runs"][label] = {"locations": len(rows), "by_status": counts, "by_cause": causes, "detail": rows}
        print(label, len(rows), counts, causes)
    (ROOT / "evaluation" / "results" / "wxb_functional_reachability.json").write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
