"""Preflight: does opt-in ACG evidence capture (+ action ledger) change the frozen legacy agent?

Runs the frozen comprehensive-evaluation configuration (evaluation/comprehensive_config.py,
policy=coverage, CLI defaults) on representative local fixtures with instrumentation off and
on, twice each, interleaved (off, on, off, on). The off-vs-off pair measures the agent's own
run-to-run variation; capture is behavior-preserving only if on-vs-off differences are not
larger than that and none are attributable to capture.

Compared per run: executed browser-action sequence, HTTP request sequence (server log where
the fixture keeps one, otherwise the artifact's recorded network), legacy transition records,
exploration decisions (ordered transitions incl. source/result groups and errors), replays,
and the final legacy Graph A (canonicalized: per-run ids/timestamps/ports removed).

Run: .venv/bin/python -m evaluation.comprehensive_preflight [out_dir]
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from evaluation.comprehensive_config import FROZEN, INSTRUMENTATION, ROOT, git_revision

FIXTURES = ["stateful_lab", "js_heavy_lab", "replay_lab", "phase2_lab", "coverage_lab"]
HOST = re.compile(r"(?:127\.0\.0\.1|localhost):\d+")
RUN_ID = re.compile(r"\b(?:obs|tr|action_tr|replay|workflow|advertised_obs|robs|agent1)[-_][0-9A-Za-z_T]+")
VOLATILE_KEYS = {"recorded_at", "started_at", "finished_at", "run_id", "duration_ms", "elapsed_ms", "elapsed_seconds",
                 "wall_seconds", "timing", "latency_ms", "output_dir", "timestamp", "ended_at", "acg_evidence", "action_ledger"}


def _start(env: str):
    if env == "coverage_lab":
        from development_apps.coverage_lab import start_coverage_lab
        server, _, url = start_coverage_lab()
        return server, url, lambda: None
    from evaluation.active_ab import start
    server, url, requests, _ = start(env)
    return server, url, requests


# Per-run identifiers and hashes that embed the fixture's random port (control ids, raw state
# signatures, record ids) differ between any two runs; group signatures do not and are kept.
PORT_HASHED = {"control_id", "raw_state_signatures", "source_state_signature", "result_state_signature", "id", "elapsed_ms"}


def _volatile(key: str) -> bool:
    return key in VOLATILE_KEYS or key in PORT_HASHED or key.endswith(("_observation_id", "_transition_id", "replay_id",
                                                                        "replay_ids", "transition_ids", "observation_ids"))


def _norm(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _norm(v) for k, v in sorted(value.items()) if not _volatile(k)}
    if isinstance(value, list):
        return [_norm(v) for v in value]
    if isinstance(value, str):
        return RUN_ID.sub("ID", HOST.sub("H", value))
    if isinstance(value, float):
        return None                                     # timings/scores derived from wall clock
    return value


def _graph_canon(graph: dict) -> dict:
    out = {}
    for kind, nodes in graph["nodes"].items():
        out[kind] = sorted(json.dumps(_norm(n), sort_keys=True) for n in nodes)
    out["edges"] = sorted(json.dumps(_norm(e), sort_keys=True) for e in graph["edges"])
    out["advertised_unexecuted"] = sorted(json.dumps(_norm(a), sort_keys=True) for a in graph.get("advertised_unexecuted", []))
    return out


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def run_one(env: str, instrumented: bool, out: Path) -> dict[str, Any]:
    from agent1.explorer import Explorer
    from agent1.exporter import write_outputs
    from agent1.schema import RunConfig
    server, url, requests = _start(env)
    try:
        t0 = time.monotonic()
        extra = dict(INSTRUMENTATION) if instrumented else {}
        artifact = Explorer(RunConfig(start_url=url, output_dir=out, context_label=f"preflight:{env}",
                                      **FROZEN, **extra), ROOT).run()
        write_outputs(artifact, out)
        wall = time.monotonic() - t0
        server_log = requests()
    finally:
        server.shutdown()
    norm = lambda s: HOST.sub("H", s or "")
    actions = [(t.action.kind, t.action.label, t.action.css_path, norm(t.action.target)) for t in artifact.transitions]
    decisions = [(t.source_group_signature, t.action.kind, t.action.label, norm(t.action.target),
                  t.result_group_signature, str(getattr(t.status, "value", t.status)), (t.error or "")[:60])
                 for t in artifact.transitions]
    transitions = [_norm(t.model_dump(mode="json")) for t in artifact.transitions]
    http_art = [(e.method, norm(e.url)) for o in artifact.observations for e in getattr(o, "network", [])] + \
               [(e.method, norm(e.url)) for t in artifact.transitions for e in t.network]
    replays = [_norm(r.model_dump(mode="json")) for r in artifact.replays]
    graph = _graph_canon(json.loads((out / "graph_a.json").read_text()))
    return {
        "env": env, "instrumented": instrumented, "wall_seconds": round(wall, 1),
        "browser_actions": artifact.metrics.browser_actions, "n_transitions": len(artifact.transitions),
        "n_replays": len(replays), "stopped": None,
        "actions": actions, "decisions": decisions,
        "transitions_digest": _digest(transitions), "replays_digest": _digest(replays),
        "http_server": [tuple(x) for x in server_log] if server_log is not None else None,
        "http_artifact": http_art, "graph": graph, "graph_digest": _digest(graph),
        "config_keys_present": sorted(json.loads((out / "run.json").read_text())["config"].keys()),
    }


def _diff(a: dict, b: dict) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for key in ("browser_actions", "n_transitions", "n_replays"):
        if a[key] != b[key]:
            d[key] = [a[key], b[key]]
    for key in ("actions", "decisions", "http_artifact"):
        if a[key] != b[key]:
            first = next((i for i, (x, y) in enumerate(zip(a[key], b[key])) if x != y), min(len(a[key]), len(b[key])))
            d[key] = {"first_divergence_index": first, "len": [len(a[key]), len(b[key])],
                      "a": a[key][first] if first < len(a[key]) else None,
                      "b": b[key][first] if first < len(b[key]) else None}
    if a["http_server"] is not None and a["http_server"] != b["http_server"]:
        sa, sb = a["http_server"], b["http_server"]
        first = next((i for i, (x, y) in enumerate(zip(sa, sb)) if x != y), min(len(sa), len(sb)))
        d["http_server"] = {"first_divergence_index": first, "len": [len(sa), len(sb)],
                            "multiset_equal": sorted(sa) == sorted(sb),
                            "a": sa[first] if first < len(sa) else None, "b": sb[first] if first < len(sb) else None}
    for key in ("transitions_digest", "replays_digest"):
        if a[key] != b[key]:
            d[key] = "differs"
    if a["graph_digest"] != b["graph_digest"]:
        d["graph"] = {k: {"only_a": len(set(a["graph"][k]) - set(b["graph"][k])),
                          "only_b": len(set(b["graph"][k]) - set(a["graph"][k]))}
                      for k in a["graph"] if a["graph"][k] != b["graph"].get(k)}
    return d


def recompare(base: Path) -> dict[str, Any]:
    """Recompute graph/transition/replay comparisons from saved run directories (canonicalization refined
    after the first off-vs-off pair showed port-hashed identifiers; behaviour comparisons are unaffected)."""
    out: dict[str, Any] = {}
    for env in FIXTURES:
        canon = {}
        for inst in ("off", "on"):
            for rep in (0, 1):
                d = base / f"{env}_{inst}_{rep}"
                run = json.loads((d / "run.json").read_text())
                canon[(inst, rep)] = {
                    "graph": _graph_canon(json.loads((d / "graph_a.json").read_text())),
                    "transitions": [_norm(t) for t in run["transitions"]],
                    "replays": sorted(json.dumps(_norm(r), sort_keys=True) for r in run["replays"]),
                    "browser_actions": run["metrics"]["browser_actions"],
                }
        def cmp(a, b):
            ga, gb = canon[a]["graph"], canon[b]["graph"]
            return {"graph_identical": ga == gb,
                    "graph_kinds_differing": {k: {"only_a": len(set(ga[k]) - set(gb[k])), "only_b": len(set(gb[k]) - set(ga[k]))}
                                              for k in ga if ga[k] != gb.get(k)},
                    "transitions_identical": canon[a]["transitions"] == canon[b]["transitions"],
                    "replays_identical": canon[a]["replays"] == canon[b]["replays"]}
        out[env] = {"off0_vs_off1": cmp(("off", 0), ("off", 1)), "on0_vs_on1": cmp(("on", 0), ("on", 1)),
                    "off0_vs_on0": cmp(("off", 0), ("on", 0)), "off1_vs_on1": cmp(("off", 1), ("on", 1))}
    return out


def main() -> None:
    if len(sys.argv) > 2 and sys.argv[1] == "recompare":
        base = Path(sys.argv[2])
        res = recompare(base)
        (base / "preflight_recompare.json").write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
        return
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="comp_preflight_"))
    rows: list[dict] = []
    for rep in range(2):
        for env in FIXTURES:
            for inst in (False, True):
                row = run_one(env, inst, base / f"{env}_{'on' if inst else 'off'}_{rep}")
                row["rep"] = rep
                rows.append(row)
                print(env, "on" if inst else "off", rep, row["browser_actions"], row["n_transitions"],
                      row["n_replays"], row["graph_digest"], f"{row['wall_seconds']}s", flush=True)
    summary: dict[str, Any] = {"revision": git_revision(), "frozen_config": FROZEN, "instrumentation": INSTRUMENTATION,
                               "fixtures": {}}
    for env in FIXTURES:
        r = {(x["instrumented"], x["rep"]): x for x in rows if x["env"] == env}
        comps = {"off0_vs_off1 (natural variation)": _diff(r[(False, 0)], r[(False, 1)]),
                 "on0_vs_on1 (natural variation)": _diff(r[(True, 0)], r[(True, 1)]),
                 "off0_vs_on0": _diff(r[(False, 0)], r[(True, 0)]),
                 "off1_vs_on1": _diff(r[(False, 1)], r[(True, 1)])}
        summary["fixtures"][env] = {
            "runs": [{k: x[k] for k in ("instrumented", "rep", "browser_actions", "n_transitions", "n_replays",
                                         "graph_digest", "wall_seconds", "stopped")} for x in r.values()],
            "comparisons": comps,
            "identical_off_vs_on": not comps["off0_vs_on0"] and not comps["off1_vs_on1"],
            "deterministic_off": not comps["off0_vs_off1 (natural variation)"],
        }
    (base / "preflight_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps({e: {k: v for k, v in s.items() if k in ("identical_off_vs_on", "deterministic_off")}
                      for e, s in summary["fixtures"].items()}, indent=1))
    print("SUMMARY", base / "preflight_summary.json")


if __name__ == "__main__":
    main()
