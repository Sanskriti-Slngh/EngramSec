"""Comprehensive Agent 1 benchmark evaluation: driver (see AGENT1_COMPREHENSIVE_EVALUATION_PREREGISTRATION.md).

Evaluation-only infrastructure. It does not modify or tune Agent 1: every trial runs the
frozen agent (`Explorer` + `write_outputs`, exactly the `agent1.cli map` path) with the
frozen configuration in evaluation/comprehensive_config.py. Each trial runs in a child
process with a hard wall-clock limit; a killed or failed trial is recorded, never dropped.

Raw run directories (agent1/experiments/comprehensive_eval/) are git-ignored. For
WebExploitBench targets only aggregate counts leave them; nothing from those runs is
read back into Agent 1.

  .venv/bin/python -m evaluation.comprehensive_eval run --envs all --trials 3
  .venv/bin/python -m evaluation.comprehensive_eval summarize
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from statistics import median
from typing import Any, Callable

from evaluation.comprehensive_config import FROZEN, INSTRUMENTATION, ROOT, git_revision, tree_clean

BASE = ROOT / "agent1" / "experiments" / "comprehensive_eval"
RESULTS = ROOT / "evaluation" / "results"
TARGETS = Path.home() / "engramsec_targets"
BENCH = Path.home() / "WebExploitBench"
CHILD_TIMEOUT_S = 600            # hard wall limit per trial (exploration ceiling is 180 s)
SETUP_TIMEOUT_S = 900            # hard limit for bringing one environment up
ENV_WALL_LIMIT_S = 3 * 3600      # hard limit for all trials of one environment

# ------------------------------------------------------------------ environment matrix
ENVS: dict[str, dict[str, Any]] = {
    # Track A: development, white-box (failure analysis permitted)
    "stateful_lab": dict(track="A", kind="inproc", category="server-rendered CRUD with destructive control", gt="capability",
                         exposure="development (designed and tuned against)"),
    "js_heavy_lab": dict(track="A", kind="inproc", category="client-rendered SPA, two roles", gt="capability",
                         exposure="development (designed and tuned against)"),
    "replay_lab": dict(track="A", kind="inproc", category="catalog/search/records with equivalent interfaces", gt="capability",
                       exposure="development (designed and tuned against)"),
    "phase2_lab": dict(track="A", kind="inproc", category="prerequisite workflow + WebSocket diagnostic", gt="server_state",
                       exposure="development"),
    "coverage_lab": dict(track="A", kind="inproc", category="multi-area server-rendered site", gt="surface",
                         exposure="development"),
    "heldout_shop": dict(track="A", kind="inproc", category="small e-commerce", gt="surface",
                         exposure="development (formerly validation; not held out)"),
    "transfer_library": dict(track="A", kind="inproc", category="resource/link discovery with boundary traps", gt="transfer",
                             exposure="development"),
    "restoration_lab": dict(track="A", kind="inproc", category="restoration contract fixture", gt=None,
                            exposure="development"),
    "hybrid_lab": dict(track="A", kind="inproc", category="catalog + setup chain contract fixture", gt=None,
                       exposure="development"),
    "crawl_maze": dict(track="A", kind="crawl_maze", category="crawler testbed (link/JS/HTML discovery)", gt="crawl_maze",
                       exposure="development (repeatedly used)"),
    "crawlground": dict(track="A", kind="crawlground", category="crawler testbed (interaction-gated markers)", gt="crawlground",
                        exposure="development (transfer-checked before)"),
    "whiteboard": dict(track="A", kind="whiteboard", category="authenticated collaborative whiteboard (anonymous only)",
                       gt="identity", exposure="development (user's own application)"),
    # Track B: WebExploitBench public targets (evaluation-only)
    "prestashop": dict(track="B", kind="targetctl", category="e-commerce CMS (PHP)", gt=None,
                       exposure="evaluation-only; mapped blind once on 2026-10-28 (not completely blind)"),
    "comfyui": dict(track="B", kind="targetctl", category="canvas/graph ML UI (Python, WebSocket)", gt=None,
                    exposure="evaluation-only; mapped blind once on 2026-10-28 (not completely blind)"),
    "siyucms": dict(track="B", kind="targetctl", category="CMS (PHP/ThinkPHP)", gt=None,
                    exposure="development/validation (search validation); NOT held out"),
    "jetlinks": dict(track="B", kind="targetctl", category="IoT platform (Java, SPA)", gt=None,
                     exposure="evaluation-only; never built or run before this evaluation"),
    "white-jotter": dict(track="B", kind="targetctl", category="library management (Java/Vue)", gt=None,
                         exposure="evaluation-only; never built or run before this evaluation"),
}
GATED = 10  # WebExploitBench full-dataset targets: NOT EVALUATED — ACCESS RESTRICTED


# ------------------------------------------------------------------ child: one frozen-agent run
def _inproc_start(env: str):
    """Returns (url, stop, server_log) for an in-process fixture; server_log() -> list[(method, path)]."""
    import tempfile
    if env in {"stateful_lab", "js_heavy_lab", "replay_lab", "phase2_lab"}:
        from evaluation.active_ab import start
        server, url, requests, state = start(env)
        return url, server.shutdown, requests, state
    if env == "coverage_lab":
        from development_apps.coverage_lab import start_coverage_lab
        server, _, url = start_coverage_lab()
        return url, server.shutdown, lambda: [], lambda: {}
    if env == "heldout_shop":
        from development_apps.heldout_shop import start_heldout_shop
        server, _, url = start_heldout_shop()
        return url, server.shutdown, lambda: [], lambda: {}
    if env == "transfer_library":
        from development_apps.transfer_library import STATE, start_transfer_library
        servers, _, url = start_transfer_library()
        return url, lambda: [s.shutdown() for s in servers], \
            lambda: [(e["method"], e["path"]) for e in STATE.log], lambda: {"snapshot": STATE.snapshot()}
    if env == "restoration_lab":
        from development_apps.restoration_lab import start_restoration_lab
        server, url, log, state = start_restoration_lab()
        return url, server.shutdown, lambda: list(log), lambda: dict(state)
    if env == "hybrid_lab":
        from development_apps.hybrid_lab import start_hybrid_lab
        server, url, log, state = start_hybrid_lab()
        return url, server.shutdown, lambda: list(log), lambda: dict(state)
    raise KeyError(env)


def child(env: str, out: Path, url: str | None, instrumented: bool) -> None:
    from agent1.explorer import Explorer
    from agent1.exporter import write_outputs
    from agent1.live.acg import LiveACG
    from agent1.schema import RunConfig
    stop, server_log, state = (lambda: None), (lambda: []), (lambda: {})
    if ENVS[env]["kind"] == "inproc":
        url, stop, server_log, state = _inproc_start(env)
    try:
        extra = dict(INSTRUMENTATION) if instrumented else {}
        config = RunConfig(start_url=url, output_dir=out, context_label=f"comprehensive:{env}:anonymous",
                           **FROZEN, **extra)
        t0 = time.monotonic()
        explorer = Explorer(config, ROOT)
        artifact = explorer.run()
        write_outputs(artifact, out)
        wall = time.monotonic() - t0
        meta: dict[str, Any] = {"wall_seconds": round(wall, 2)}
        budget = explorer.http_budget
        meta["http_scope"] = {"blocked_out_of_scope": getattr(budget, "blocked", None) if budget else None,
                              "redirect_scope_violations": getattr(budget, "redirect_scope_violations", None) if budget else None}
        if explorer.evidence_sink is not None:
            live = LiveACG(application=env, sink=explorer.evidence_sink)
            live.sync(artifact)
            (out / "live_acg.json").write_text(live.export().model_dump_json())
            meta["sink_counters"] = dict(getattr(explorer.evidence_sink, "counters", {}) or {})
        if ENVS[env]["kind"] == "inproc":
            (out / "server_requests.json").write_text(json.dumps([list(x) for x in server_log()]))
            meta["server_state"] = {k: v for k, v in state().items() if k != "snapshot"}
            if env == "transfer_library":
                (out / "server_log.json").write_text(json.dumps(state()["snapshot"], default=str))
        (out / "child_meta.json").write_text(json.dumps(meta, default=str))
    finally:
        stop()


# ------------------------------------------------------------------ external environments (driver side)
def _wait_http(url: str, limit: float) -> float:
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status < 500:
                    return time.monotonic() - t0
        except urllib.error.HTTPError as e:
            if e.code < 500:
                return time.monotonic() - t0
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError(f"not ready within {limit:.0f}s")


MODERN_BASH = Path("/opt/homebrew/opt/bash/bin")   # keg path; not linked into the user's PATH


def _sh(cmd: list[str], timeout: float = 120, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    env = None
    if cmd and cmd[0].endswith("targetctl"):
        # Infrastructure-only: benchmark tooling and post-up hooks require bash >= 4.4.
        env = dict(os.environ, PATH=f"{MODERN_BASH}:{os.environ.get('PATH', '')}")
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    if check and r.returncode:
        raise RuntimeError(f"{cmd[0]} {cmd[1] if len(cmd) > 1 else ''} failed (exit {r.returncode}): {r.stderr[-300:]}")
    return r


def _port_free(port: int) -> None:
    import socket
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"port {port} already in use: refusing to evaluate an unknown server")


def _loopback_only(ports: str) -> bool:
    published = [p for p in ports.split(", ") if "->" in p]
    return bool(published) and all(p.startswith("127.0.0.1:") for p in published)


class External:
    """setup() -> url; teardown(); score(out) -> dict; containers() -> names for memory sampling."""
    def __init__(self, env: str):
        self.env = env
        self.proc: subprocess.Popen | None = None
        self.names: list[str] = []
        self.secret: str | None = None

    # -- crawl maze (Flask on loopback)
    def _crawl_maze(self) -> str:
        _port_free(3460)
        cmd = [str(TARGETS / "crawlmaze-venv/bin/flask"), "--app", "app", "run", "--host", "127.0.0.1", "--port", "3460"]
        self.proc = subprocess.Popen(cmd, cwd=TARGETS / "crawl-maze", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        url = "http://127.0.0.1:3460/"
        _wait_http(url, 60)
        if self.proc.poll() is not None:
            raise RuntimeError("crawl maze server exited")
        return url

    # -- crawlground (official image, fresh container per trial, loopback publish)
    def _crawlground(self) -> str:
        name = "engramsec-eval-crawlground"
        _sh(["docker", "rm", "-f", "-v", name], check=False)
        _port_free(3456)
        _sh(["docker", "run", "-d", "--name", name, "-p", "127.0.0.1:3456:3456", "engramsec-crawlground:ba52303"])
        self.names = [name]
        url = "http://127.0.0.1:3456/"
        _wait_http(url, 60)
        return url

    # -- whiteboard (disposable stack, fresh schema, anonymous)
    def _whiteboard(self) -> str:
        prefix = "engramsec-eval-wb"
        schema = Path.home() / "takehome-sanskriti-singh/server/schema.sql"
        for n in (prefix + "-client", prefix + "-server", prefix + "-db"):
            _sh(["docker", "rm", "-f", n], check=False)
        _sh(["docker", "network", "rm", prefix], check=False)
        _port_free(45173)
        password, secret = secrets.token_urlsafe(24), secrets.token_urlsafe(32)
        _sh(["docker", "network", "create", prefix])
        _sh(["docker", "run", "-d", "--name", prefix + "-db", "--network", prefix, "--network-alias", "db",
             "-e", "POSTGRES_USER=lab", "-e", "POSTGRES_DB=lab", "-e", "POSTGRES_PASSWORD=" + password, "postgres:16-alpine"])
        self.names = [prefix + "-db"]
        for _ in range(120):
            if _sh(["docker", "exec", prefix + "-db", "pg_isready", "-U", "lab"], check=False).returncode == 0:
                break
            time.sleep(0.5)
        for _ in range(20):   # postgres's first start reports ready during initdb, then restarts
            r = subprocess.run(["docker", "exec", "-i", prefix + "-db", "psql", "-U", "lab", "-d", "lab", "-v",
                                "ON_ERROR_STOP=1"], input=schema.read_bytes(), capture_output=True, timeout=60)
            if r.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("whiteboard schema load failed")
        _sh(["docker", "run", "-d", "--name", prefix + "-server", "--network", prefix, "-p", "127.0.0.1:45173:45173",
             "-e", f"DATABASE_URL=postgresql://lab:{password}@db:5432/lab", "-e", "SECRET_KEY=" + secret,
             "takehome-sanskriti-singh-server"])
        _sh(["docker", "run", "-d", "--name", prefix + "-client", "--network", "container:" + prefix + "-server",
             "takehome-sanskriti-singh-client", "npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "45173"])
        self.names = [prefix + "-client", prefix + "-server", prefix + "-db"]
        url = "http://127.0.0.1:45173/"
        _wait_http(url, 120)
        return url

    # -- WebExploitBench via the official targetctl (fresh `up` per trial)
    def _targetctl(self) -> str:
        _sh([str(BENCH / "scripts/targetctl"), "down", self.env], timeout=300, cwd=BENCH, check=False)
        r = _sh([str(BENCH / "scripts/targetctl"), "up", self.env], timeout=SETUP_TIMEOUT_S, cwd=BENCH)
        urls = [u.replace("\\/", "/") for u in re.findall(r"http:\\?/\\?/127\.0\.0\.1:\d+", r.stdout)]
        if not urls:
            raise RuntimeError("targetctl printed no loopback URL")
        project = "web_" + self.env.replace("-", "_")
        ps = _sh(["docker", "ps", "--filter", f"label=com.docker.compose.project={project}",
                  "--format", "{{.Names}}\t{{.Ports}}"]).stdout.strip().splitlines()
        self.names = [line.split("\t")[0] for line in ps]
        published = [line.split("\t")[1] for line in ps if "->" in line.split("\t")[-1]]
        if not published or not all(_loopback_only(p) for p in published):
            raise RuntimeError("isolation not established: a published port is not loopback-only")
        url = urls[0].rstrip("/") + "/"
        _wait_http(url, SETUP_TIMEOUT_S)
        return url

    def setup(self) -> str:
        kind = ENVS[self.env]["kind"]
        return {"crawl_maze": self._crawl_maze, "crawlground": self._crawlground, "whiteboard": self._whiteboard,
                "targetctl": self._targetctl}[kind]()

    def teardown(self) -> None:
        kind = ENVS[self.env]["kind"]
        if self.proc:
            self.proc.terminate(); self.proc.wait(timeout=30); self.proc = None
        if kind == "targetctl":
            _sh([str(BENCH / "scripts/targetctl"), "down", self.env], timeout=300, cwd=BENCH, check=False)
        elif kind in {"crawlground", "whiteboard"}:
            for n in self.names:
                _sh(["docker", "rm", "-f", "-v", n], check=False)
            if kind == "whiteboard":
                _sh(["docker", "network", "rm", "engramsec-eval-wb"], check=False)
        self.names = []

    def score(self, out: Path, url: str) -> dict[str, Any]:
        kind = ENVS[self.env]["kind"]
        if kind == "crawlground":
            with urllib.request.urlopen(url + "results.json", timeout=10) as r:
                rep = json.loads(r.read())
            by_cat: dict[str, list[int]] = {}
            for t in rep["tests"]:
                hit = any(v["scored"] for v in t["tools"].values())
                by_cat.setdefault(t["category"], [0, 0])
                by_cat[t["category"]][0] += hit; by_cat[t["category"]][1] += 1
            return {"markers_scored": rep["summary"]["scored"], "denominator": rep["summary"]["total"],
                    "recall": round(rep["summary"]["scored"] / rep["summary"]["total"], 4),
                    "by_category": {k: f"{a}/{b}" for k, (a, b) in sorted(by_cat.items())}}
        if kind == "crawl_maze":
            import importlib.util
            spec = importlib.util.spec_from_file_location("cm", ROOT / "experiments" / "score_crawlmaze_posthoc.py")
            mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
            cats = mod.expected_paths(url, ["css", "headers", "html", "javascript", "misc"])
            graph = json.loads((out / "graph_a.json").read_text())
            s = mod.score(graph, cats)
            return {"denominator": sum(len(v) for v in cats.values()), "score": s}
        return {}

    def mem_mb(self) -> float | None:
        if not self.names:
            return None
        r = _sh(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", *self.names], check=False, timeout=30)
        total = 0.0
        for line in r.stdout.splitlines():
            used = line.split("/")[0].strip()
            m = re.match(r"([\d.]+)\s*([KMG]i?B)", used)
            if m:
                v, unit = float(m.group(1)), m.group(2)
                total += v * {"KiB": 1 / 1024, "KB": 1 / 1000, "MiB": 1, "MB": 1, "GiB": 1024, "GB": 1000}[unit]
        return round(total, 1)


# ------------------------------------------------------------------ metrics for one finished trial
def trial_metrics(env: str, out: Path) -> dict[str, Any]:
    from agent1.model.importer import import_run_artifact
    from agent1.model.materialize import materialize
    from evaluation import comprehensive_metrics as M
    from evaluation.comprehensive_config import FROZEN as cfg
    run = json.loads((out / "run.json").read_text())
    graph = json.loads((out / "graph_a.json").read_text())
    ledger = json.loads((out / "action_ledger.json").read_text()) if (out / "action_ledger.json").exists() else {}
    meta = json.loads((out / "child_meta.json").read_text()) if (out / "child_meta.json").exists() else {}
    records = import_run_artifact(run, "run.json", env)
    offline = materialize(records).model_dump(mode="json")
    live = json.loads((out / "live_acg.json").read_text()) if (out / "live_acg.json").exists() else None
    ops = {o["id"]: o for o in offline["operations"]}
    row: dict[str, Any] = {
        "first_state_group": (run.get("observations") or [{}])[0].get("group_signature"),
        "first_state_controls": len((run.get("observations") or [{}])[0].get("controls", [])),
        "config_digest": __import__("hashlib").sha256(json.dumps({k: v for k, v in run["config"].items()
                         if k not in {"start_url", "output_dir", "run_id", "context_label"}}, sort_keys=True).encode()).hexdigest()[:12],
        "code_revision": run.get("code_revision"),
        "model_calls": run["metrics"].get("model_calls"),
        "discovery": M.discovery(run, graph, offline),
        "capabilities": M.capabilities(offline, graph),
        "efficiency": M.efficiency(run, meta.get("http_scope", {}), cfg),
        "discovery_curves": M.discovery_curves(run, ledger, env, cfg) if ledger else None,
        "acg_comparison": M.acg_comparison(graph, offline, live),
        "capability_keys": sorted({M.cap_key(c, ops) for c in offline["capabilities"] if c["status"] in
                                   ("observed", "reproduced", "verified")}),
        "action_sequence_digest": __import__("hashlib").sha256(json.dumps(
            [(t["action"].get("kind"), t["action"].get("label"), t["action"].get("css_path")) for t in run["transitions"]]
        ).encode()).hexdigest()[:12],
        "wall_seconds": meta.get("wall_seconds"), "sink_counters": meta.get("sink_counters"),
        "server_state": meta.get("server_state"),
    }
    ex = row["efficiency"]
    n_caps = row["capabilities"]["distinct_capabilities_observed_or_better"]
    row["efficiency"]["capabilities_per_100_actions"] = round(100 * n_caps / max(1, ex["browser_actions"]), 2)
    row["efficiency"]["capabilities_per_minute"] = round(60 * n_caps / max(1e-9, ex["elapsed_seconds"]), 2) if ex["elapsed_seconds"] else None
    # safety: state-changing requests issued by the browser; scope enforcement
    writes = [e for t in run["transitions"] for e in t.get("network", []) if e.get("method", "GET").upper() not in
              {"GET", "HEAD", "OPTIONS"} and not e.get("failure")]
    row["safety"] = {"state_changing_requests_issued": len(writes),
                     "state_changing_requests_in_replay": sum(1 for r in run["replays"] for e in r.get("network", [])
                                                              if e.get("method", "GET").upper() not in {"GET", "HEAD", "OPTIONS"}),
                     "dangerous_controls_skipped": row["capabilities"]["evidence_status"]["advertised_by_skip_reason"]
                     .get("dangerous_label_or_target", 0),
                     **meta.get("http_scope", {}),
                     "ws_out_of_scope_refused": (meta.get("sink_counters") or {}).get("ws_out_of_scope_refused", 0)}
    gt_kind = ENVS[env]["gt"]
    if gt_kind == "capability":
        from evaluation.active_ab import _gt, safety
        gt = _gt(env)
        row["gt"] = M.gt_capability(gt, run, ledger, env, cfg, offline, live, graph)
        reqs = json.loads((out / "server_requests.json").read_text()) if (out / "server_requests.json").exists() else []
        from agent1.model.schema import Status  # noqa: F401  (export model for safety())
        export_model = materialize(records)
        row["safety"].update({k: v for k, v in safety(env, [tuple(x) for x in reqs], records, export_model).items()
                              if k != "write_endpoint_hits"})
    elif gt_kind == "surface":
        truth = json.loads((ROOT / "development_apps" / f"{env}_ground_truth.json").read_text())
        row["gt"] = M.gt_surface(graph, truth)
    elif gt_kind == "transfer":
        import importlib.util
        spec = importlib.util.spec_from_file_location("etl", ROOT / "experiments" / "evaluate_transfer_library.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        full = mod.evaluate(out)
        row["gt"] = {k: full[k] for k in ("documents_reached_2xx", "static_fetched_2xx", "functionality_executed",
                                          "functionality_replay_validated", "sentinel_hits", "redirect_trap_requests",
                                          "replays")}
        row["gt"]["functionality"] = {k: {"executed": v["executed"], "replay_validated": v["replay_validated"]}
                                      for k, v in full["functionality"].items()}
    elif gt_kind == "identity":
        from evaluation.active_ab import _gt
        from evaluation.score_acg import observation_paths, score_identity
        gt = _gt(env)
        ident = score_identity(gt, offline, observation_paths(records))
        row["gt"] = {"capabilities_annotated": False, "identity": {k: v for k, v in ident.items()
                                                                  if isinstance(v, (int, float, type(None)))}}
    elif gt_kind == "server_state":
        row["gt"] = {"server_state": meta.get("server_state")}
    if (out / "external_score.json").exists():
        row["gt"] = json.loads((out / "external_score.json").read_text())
    return row


# ------------------------------------------------------------------ driver
def run_env(env: str, trials: int, base: Path, instrumented: bool, log: Callable[[str], None]) -> list[dict]:
    rows = []
    ext = External(env) if ENVS[env]["kind"] != "inproc" else None
    env_t0 = time.monotonic()
    for trial in range(trials):
        out = base / env / f"trial_{trial}"
        if out.exists():
            done = out / "trial.json"
            if done.exists():
                rows.append(json.loads(done.read_text())); continue
        out.mkdir(parents=True, exist_ok=True)
        row: dict[str, Any] = {"env": env, "trial": trial, "track": ENVS[env]["track"], "status": "ok"}
        if time.monotonic() - env_t0 > ENV_WALL_LIMIT_S:
            row.update(status="not_run_env_wall_limit"); rows.append(row)
            (out / "trial.json").write_text(json.dumps(row)); continue
        url = None
        mem_peak: list[float] = []
        stop_sampling = threading.Event()
        try:
            if ext:
                t0 = time.monotonic()
                try:
                    url = ext.setup()
                except Exception as first:        # preregistered: one setup retry, both attempts recorded
                    row["setup_first_attempt_error"] = str(first)[:300]
                    ext.teardown()
                    try:
                        url = ext.setup()
                    except Exception as exc:      # recorded, not hidden
                        row.update(status="setup_failure", setup_error=str(exc)[:300],
                                   setup_seconds=round(time.monotonic() - t0, 1))
                        raise
                row["setup_seconds"] = round(time.monotonic() - t0, 1)
                row["mem_mb_after_setup"] = ext.mem_mb()

                def sample():
                    while not stop_sampling.wait(5):
                        m = ext.mem_mb()
                        if m is not None:
                            mem_peak.append(m)
                threading.Thread(target=sample, daemon=True).start()
            cmd = [sys.executable, "-m", "evaluation.comprehensive_eval", "child", "--env", env, "--out", str(out)]
            if url:
                cmd += ["--url", url]
            if not instrumented:
                cmd += ["--no-instrumentation"]
            t0 = time.monotonic()
            try:
                proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=CHILD_TIMEOUT_S)
                row["child_seconds"] = round(time.monotonic() - t0, 1)
                if proc.returncode:
                    row.update(status="agent_error", error_tail=proc.stderr.strip().splitlines()[-1][:300]
                               if proc.stderr.strip() else f"exit {proc.returncode}")
            except subprocess.TimeoutExpired:
                row.update(status="hard_timeout", child_seconds=CHILD_TIMEOUT_S)
            stop_sampling.set()
            if mem_peak:
                row["mem_mb_peak_during_run"] = max(mem_peak)
            if ext and row["status"] == "ok":
                sc = ext.score(out, url)
                if sc:
                    (out / "external_score.json").write_text(json.dumps(sc))
            if row["status"] == "ok" or (out / "run.json").exists():
                try:
                    row.update(trial_metrics(env, out))
                except Exception as exc:
                    row.setdefault("metric_errors", []).append(f"{type(exc).__name__}: {str(exc)[:200]}")
        except Exception:
            pass
        finally:
            stop_sampling.set()
            if ext:
                t0 = time.monotonic()
                ext.teardown()
                row["teardown_seconds"] = round(time.monotonic() - t0, 1)
        (out / "trial.json").write_text(json.dumps(row, default=str))
        rows.append(row)
        g = row.get("gt") or {}
        log(f"{env} t{trial} {row['status']} actions={row.get('efficiency', {}).get('browser_actions')} "
            f"caps={row.get('capabilities', {}).get('distinct_capabilities_observed_or_better')} "
            f"recall={g.get('final_recall', g.get('recall'))} setup={row.get('setup_seconds')} child={row.get('child_seconds')}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("child")
    c.add_argument("--env", required=True); c.add_argument("--out", type=Path, required=True)
    c.add_argument("--url"); c.add_argument("--no-instrumentation", action="store_true")
    r = sub.add_parser("run")
    r.add_argument("--envs", default="all"); r.add_argument("--trials", type=int, default=3)
    r.add_argument("--base", type=Path, default=BASE); r.add_argument("--no-instrumentation", action="store_true")
    s = sub.add_parser("summarize")
    s.add_argument("--base", type=Path, default=BASE)
    args = ap.parse_args()
    if args.cmd == "child":
        child(args.env, args.out, args.url, not args.no_instrumentation)
        return
    if args.cmd == "run":
        if not tree_clean(("agent1",)):
            raise SystemExit("agent1/ has uncommitted changes: the evaluated agent is not frozen")
        envs = list(ENVS) if args.envs == "all" else args.envs.split(",")
        args.base.mkdir(parents=True, exist_ok=True)
        logf = (args.base / "run_log.txt").open("a")

        def log(msg: str) -> None:
            line = f"{time.strftime('%H:%M:%S')} {msg}"
            print(line, flush=True); logf.write(line + "\n"); logf.flush()
        log(f"revision {git_revision()} envs {envs}")
        for env in envs:
            run_env(env, args.trials, args.base, not args.no_instrumentation, log)
        return
    from evaluation.comprehensive_summary import summarize
    summarize(args.base)


if __name__ == "__main__":
    main()
