"""Comprehensive Agent 1 benchmark evaluation: driver (see AGENT1_COMPREHENSIVE_EVALUATION_PREREGISTRATION.md).

Evaluation-only infrastructure. It does not modify or tune Agent 1: every trial runs the
frozen agent (`Explorer` + `write_outputs`, exactly the `agent1.cli map` path) with the
frozen configuration in evaluation/comprehensive_config.py. Each trial runs in a child
process with a hard wall-clock limit; a killed or failed trial is recorded, never dropped.

Raw run directories (agent1/experiments/comprehensive_eval/) are git-ignored. For
WebExploitBench targets only aggregate counts leave them; nothing from those runs is
read back into Agent 1.

  .venv/bin/python -m evaluation.comprehensive_eval reset-verify --envs siyucms,prestashop,...   (no mapping)
  .venv/bin/python -m evaluation.comprehensive_eval run --envs all --trials 3
  .venv/bin/python -m evaluation.comprehensive_eval summarize
  .venv/bin/python -m evaluation.comprehensive_eval run --post-diagnostic --envs auto --trials 3   (supplementary)

Trial-reset integrity (preregistration revision 1): before every Docker-backed trial the
previous project containers must be gone and no named project volume may exist; after
startup the container IDs, mount profile and volume names are recorded and checked against
the frozen profile from `reset-verify` and against every earlier trial of the same
environment. Any violation is a `reset_failure`: the trial is not mapped.
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
BASE_POST = ROOT / "agent1" / "experiments" / "comprehensive_post_diagnostic"
RESET_PROFILES = ROOT / "agent1" / "experiments" / "comprehensive_reset" / "profiles.json"   # git-ignored
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

# Supplementary safe-isolated write diagnostic (Track S). Never part of the primary evaluation:
# the only change is POST form submission, and only for in-process development fixtures whose
# state lives inside the trial's own child process. Scope, the dangerous-label filter and the
# protected-input filter are unchanged.
POST_DIAGNOSTIC_OVERRIDE = {"allow_post_forms": True}


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


def child(env: str, out: Path, url: str | None, instrumented: bool, post_diagnostic: bool = False) -> None:
    from agent1.explorer import Explorer
    from agent1.exporter import write_outputs
    from agent1.live.acg import LiveACG
    from agent1.schema import RunConfig
    import hashlib
    from urllib.parse import urlsplit
    stop, server_log, state = (lambda: None), (lambda: []), (lambda: {})
    initial: dict[str, Any] = {}
    if post_diagnostic and ENVS[env]["kind"] != "inproc":
        raise SystemExit("the POST diagnostic runs only on in-process development fixtures")
    if ENVS[env]["kind"] == "inproc":
        url, stop, server_log, state = _inproc_start(env)
        # Reset by process isolation: a new interpreter per trial, fixture state created from code.
        snap = state()
        initial = {"mechanism": "fresh child process; fixture state created from code",
                   "initial_server_log_len": len(server_log()),
                   "initial_state_digest": hashlib.sha256(json.dumps(snap, sort_keys=True, default=str).encode()).hexdigest()[:16],
                   "fixture_port": urlsplit(url).port}
    try:
        extra = dict(INSTRUMENTATION) if instrumented else {}
        if post_diagnostic:
            extra.update(POST_DIAGNOSTIC_OVERRIDE)
        label = "comprehensive-postdiag" if post_diagnostic else "comprehensive"
        config = RunConfig(start_url=url, output_dir=out, context_label=f"{label}:{env}:anonymous",
                           **FROZEN, **extra)
        t0 = time.monotonic()
        explorer = Explorer(config, ROOT)
        artifact = explorer.run()
        write_outputs(artifact, out)
        wall = time.monotonic() - t0
        meta: dict[str, Any] = {"wall_seconds": round(wall, 2), "post_diagnostic": post_diagnostic}
        if initial:
            meta["inproc_reset"] = initial
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


class ResetFailure(RuntimeError):
    """The environment could not be shown to start from a fresh, equivalent state."""


def _mount_profile(inspected: list[dict]) -> tuple[dict[str, dict[str, list]], list[str]]:
    """(per-service comparable mount profile, volume names) from `docker inspect` output."""
    profile: dict[str, dict[str, list]] = {}
    volumes: list[str] = []
    for c in inspected:
        labels = (c.get("Config") or {}).get("Labels") or {}
        service = labels.get("com.docker.compose.service") or c.get("Name", "").lstrip("/")
        entry = {"tmpfs": set((c.get("HostConfig") or {}).get("Tmpfs") or {}), "volume": set(), "bind": set()}
        for m in c.get("Mounts") or []:
            kind = m.get("Type")
            if kind == "tmpfs":
                entry["tmpfs"].add(m.get("Destination"))
            elif kind in ("volume", "bind"):
                entry[kind].add(f"{m.get('Destination')}:{'rw' if m.get('RW') else 'ro'}")
                if kind == "volume" and m.get("Name"):
                    volumes.append(m["Name"])
        profile[service] = {k: sorted(v) for k, v in entry.items()}
    return dict(sorted(profile.items())), sorted(volumes)


def _load_profiles() -> dict[str, Any]:
    return json.loads(RESET_PROFILES.read_text()) if RESET_PROFILES.exists() else {}


class External:
    """setup() -> url; teardown(); score(out) -> dict; containers() -> names for memory sampling.

    Docker-backed kinds also keep `self.reset`: the per-trial reset-integrity record.
    """
    def __init__(self, env: str, require_profile: bool = True):
        self.env = env
        self.proc: subprocess.Popen | None = None
        self.names: list[str] = []
        self.secret: str | None = None
        self.require_profile = require_profile
        self.seen_ids: set[str] = set()          # container IDs of earlier trials of this environment
        self.seen_volumes: set[str] = set()      # volume names of earlier trials of this environment
        self.reset: dict[str, Any] = {}
        self.profile: dict[str, Any] | None = None

    # -- reset integrity (Docker-backed kinds)
    @property
    def project(self) -> str:
        return "web_" + self.env.replace("-", "_")

    def _filters(self) -> list[str]:
        kind = ENVS[self.env]["kind"]
        if kind == "targetctl":
            return ["--filter", f"label=com.docker.compose.project={self.project}"]
        if kind == "crawlground":
            return ["--filter", "name=^/?engramsec-eval-crawlground$"]
        if kind == "whiteboard":
            return ["--filter", "name=^/?engramsec-eval-wb-"]
        return []

    def containers(self) -> list[str]:
        """IDs of every container (any state) belonging to this environment."""
        if not self._filters():
            return []
        r = _sh(["docker", "ps", "-a", "--no-trunc", *self._filters(), "--format", "{{.ID}}"])
        return sorted(r.stdout.split())

    def named_volumes(self) -> list[str]:
        """Named (compose-declared) volumes of the project; they would survive `down` and be reattached."""
        if ENVS[self.env]["kind"] != "targetctl":
            return []
        r = _sh(["docker", "volume", "ls", "--filter", f"label=com.docker.compose.project={self.project}",
                 "--format", "{{.Name}}\t{{.Label \"com.docker.compose.volume\"}}"])
        return sorted(line.split("\t")[0] for line in r.stdout.splitlines() if line.strip() and line.split("\t")[-1])

    def _pre_start(self, down_exit: int | None) -> None:
        self.reset = {"pre_start_down_exit": down_exit}
        left = self.containers()
        self.reset["residual_containers_before_start"] = len(left)
        if left:
            raise ResetFailure(f"{len(left)} containers of the previous run remain before startup "
                               f"(teardown exit {down_exit})")
        named = self.named_volumes()
        self.reset["named_volumes_before_start"] = len(named)
        if named:
            raise ResetFailure(f"{len(named)} named project volumes exist before startup: state could persist")

    def _post_start(self) -> None:
        ids = self.containers()
        if not ids:
            raise ResetFailure("no containers found after startup")
        inspected = json.loads(_sh(["docker", "inspect", *ids]).stdout)
        profile, volumes = _mount_profile(inspected)
        self.reset.update({"container_ids": ids, "volume_names": volumes, "mount_profile": profile,
                           "tmpfs_mounts": sum(len(v["tmpfs"]) for v in profile.values()),
                           "volume_mounts": sum(len(v["volume"]) for v in profile.values()),
                           "writable_bind_mounts": sum(1 for v in profile.values() for b in v["bind"] if b.endswith(":rw"))})
        reused_ids = set(ids) & self.seen_ids
        reused_volumes = set(volumes) & self.seen_volumes
        self.seen_ids |= set(ids); self.seen_volumes |= set(volumes)
        if reused_ids:
            raise ResetFailure(f"{len(reused_ids)} container IDs reused from an earlier trial")
        if reused_volumes:
            raise ResetFailure(f"{len(reused_volumes)} volumes reused from an earlier trial: state could persist")
        expected = _load_profiles().get(self.env)
        if expected is None:
            self.reset["mount_profile_matches_frozen"] = None
            if self.require_profile:
                raise ResetFailure("no frozen mount profile for this environment (run reset-verify first)")
        else:
            self.reset["mount_profile_matches_frozen"] = expected["mount_profile"] == profile
            if expected["mount_profile"] != profile:
                raise ResetFailure("mount profile differs from the frozen profile recorded by reset-verify")

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
        r = _sh(["docker", "rm", "-f", "-v", name], check=False)
        self._pre_start(0 if r.returncode == 0 or "No such container" in r.stderr else r.returncode)
        _port_free(3456)
        _sh(["docker", "run", "-d", "--name", name, "-p", "127.0.0.1:3456:3456", "engramsec-crawlground:ba52303"])
        self.names = [name]
        self._post_start()
        url = "http://127.0.0.1:3456/"
        _wait_http(url, 60)
        return url

    # -- whiteboard (disposable stack, fresh schema, anonymous)
    def _whiteboard(self) -> str:
        prefix = "engramsec-eval-wb"
        schema = Path.home() / "takehome-sanskriti-singh/server/schema.sql"
        exits = [_sh(["docker", "rm", "-f", "-v", n], check=False) for n in (prefix + "-client", prefix + "-server", prefix + "-db")]
        _sh(["docker", "network", "rm", prefix], check=False)
        bad = [r.returncode for r in exits if r.returncode and "No such container" not in r.stderr]
        self._pre_start(bad[0] if bad else 0)
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
        self._post_start()
        url = "http://127.0.0.1:45173/"
        _wait_http(url, 120)
        return url

    # -- WebExploitBench via the official targetctl (fresh `up` per trial)
    def _targetctl(self) -> str:
        down = _sh([str(BENCH / "scripts/targetctl"), "down", self.env], timeout=300, cwd=BENCH, check=False)
        self._pre_start(down.returncode)
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
        self._post_start()
        url = urls[0].rstrip("/") + "/"
        _wait_http(url, SETUP_TIMEOUT_S)
        return url

    def setup(self) -> str:
        kind = ENVS[self.env]["kind"]
        return {"crawl_maze": self._crawl_maze, "crawlground": self._crawlground, "whiteboard": self._whiteboard,
                "targetctl": self._targetctl}[kind]()

    def teardown(self) -> None:
        """Stop the environment and record the teardown exit status and anything left behind."""
        kind = ENVS[self.env]["kind"]
        if self.proc:
            self.proc.terminate(); self.proc.wait(timeout=30); self.proc = None
        exit_code = 0
        if kind == "targetctl":
            exit_code = _sh([str(BENCH / "scripts/targetctl"), "down", self.env], timeout=300, cwd=BENCH,
                            check=False).returncode
        elif kind in {"crawlground", "whiteboard"}:
            for n in self.names:
                rc = _sh(["docker", "rm", "-f", "-v", n], check=False).returncode
                exit_code = exit_code or rc
            if kind == "whiteboard":
                _sh(["docker", "network", "rm", "engramsec-eval-wb"], check=False)
        if self._filters():
            used = self.reset.get("volume_names") or []
            remaining = set(_sh(["docker", "volume", "ls", "-q"], check=False).stdout.split()) & set(used)
            self.reset.update({"teardown_exit": exit_code,
                               "residual_containers_after_teardown": len(self.containers()),
                               "trial_volumes_remaining_after_teardown": len(remaining)})
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
    # Reference data, never "ground truth" unless independent: annotations and surface truth are author-written.
    if gt_kind == "capability":
        from evaluation.active_ab import _gt, safety
        gt = _gt(env)
        row["reference"] = M.gt_capability(gt, run, ledger, env, cfg, offline, live, graph)
        reqs = json.loads((out / "server_requests.json").read_text()) if (out / "server_requests.json").exists() else []
        from agent1.model.schema import Status  # noqa: F401  (export model for safety())
        export_model = materialize(records)
        row["safety"].update({k: v for k, v in safety(env, [tuple(x) for x in reqs], records, export_model).items()
                              if k != "write_endpoint_hits"})
    elif gt_kind == "surface":
        truth = json.loads((ROOT / "development_apps" / f"{env}_ground_truth.json").read_text())
        row["reference"] = M.gt_surface(graph, truth)
    elif gt_kind == "transfer":
        import importlib.util
        spec = importlib.util.spec_from_file_location("etl", ROOT / "experiments" / "evaluate_transfer_library.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        full = mod.evaluate(out)
        row["reference"] = {k: full[k] for k in ("documents_reached_2xx", "static_fetched_2xx", "functionality_executed",
                                          "functionality_replay_validated", "sentinel_hits", "redirect_trap_requests",
                                          "replays")}
        row["reference"]["functionality"] = {k: {"executed": v["executed"], "replay_validated": v["replay_validated"]}
                                      for k, v in full["functionality"].items()}
    elif gt_kind == "identity":
        from evaluation.active_ab import _gt
        from evaluation.score_acg import observation_paths, score_identity
        gt = _gt(env)
        ident = score_identity(gt, offline, observation_paths(records))
        row["reference"] = {"capabilities_annotated": False, "identity": {k: v for k, v in ident.items()
                                                                  if isinstance(v, (int, float, type(None)))}}
    elif gt_kind == "server_state":
        row["reference"] = {"server_state": meta.get("server_state")}
    if (out / "external_score.json").exists():
        row["reference"] = json.loads((out / "external_score.json").read_text())
    if gt_kind:
        row["reference_basis"] = REFERENCE_BASIS[gt_kind]
    return row


REFERENCE_BASIS = {
    "capability": "frozen author-curated development capability annotation (annotation-based recall/precision; "
                  "not independently established ground truth)",
    "surface": "author-written surface truth (areas/controls/requests) for a development fixture",
    "transfer": "author-written evaluator for a development fixture",
    "crawl_maze": "the testbed's own expected-path endpoint (third-party testbed, queried post-run)",
    "crawlground": "the testbed's own server-side marker scoring (third-party testbed, queried post-run)",
    "identity": "author annotation of templates/entities only (capabilities not annotated)",
    "server_state": "fixture server-state diagnostic only",
}


# ------------------------------------------------------------------ driver
def run_env(env: str, trials: int, base: Path, instrumented: bool, log: Callable[[str], None],
            post_diagnostic: bool = False) -> list[dict]:
    rows = []
    ext = External(env) if ENVS[env]["kind"] != "inproc" else None
    env_t0 = time.monotonic()
    for trial in range(trials):
        out = base / env / f"trial_{trial}"
        if out.exists():
            done = out / "trial.json"
            if done.exists():
                rows.append(json.loads(done.read_text()))
                if ext:                                   # a resumed run still checks against earlier trials
                    ext.seen_ids |= set((rows[-1].get("reset") or {}).get("container_ids") or [])
                    ext.seen_volumes |= set((rows[-1].get("reset") or {}).get("volume_names") or [])
                continue
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
                    row["setup_first_attempt_error"] = f"{type(first).__name__}: {str(first)[:300]}"
                    if ext.reset:
                        row["reset_first_attempt"] = {k: v for k, v in ext.reset.items() if k != "mount_profile"}
                    ext.teardown()
                    try:
                        url = ext.setup()
                    except Exception as exc:      # recorded, not hidden; the trial is not mapped
                        row.update(status="reset_failure" if isinstance(exc, ResetFailure) else "setup_failure",
                                   setup_error=str(exc)[:300], setup_seconds=round(time.monotonic() - t0, 1))
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
            if post_diagnostic:
                cmd += ["--post-diagnostic"]
                row["track"] = "S"
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
            meta_path = out / "child_meta.json"
            if not ext and meta_path.exists():
                reset = json.loads(meta_path.read_text()).get("inproc_reset") or {}
                port = reset.pop("fixture_port", None)
                if port:
                    import socket
                    with socket.socket() as sock:     # rollback: the fixture died with the child process
                        reset["fixture_server_gone_after_trial"] = sock.connect_ex(("127.0.0.1", port)) != 0
                row["reset"] = reset
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
                if ext.reset:
                    row["reset"] = dict(ext.reset)
        (out / "trial.json").write_text(json.dumps(row, default=str))
        rows.append(row)
        g = row.get("reference") or {}
        ref = g.get("annotation_recall", g.get("recall")) if row.get("track") != "B" else "n/a"
        log(f"{env} t{trial} {row['status']} actions={row.get('efficiency', {}).get('browser_actions')} "
            f"caps={row.get('capabilities', {}).get('distinct_capabilities_observed_or_better')} "
            f"reference={ref} setup={row.get('setup_seconds')} child={row.get('child_seconds')}")
    return rows


# ------------------------------------------------------------------ reset verification (no mapping)
def reset_verify(envs: list[str], log: Callable[[str], None]) -> dict[str, Any]:
    """Two fresh start/stop cycles per Docker-backed environment, sequentially, without mapping.

    Freezes each environment's mount profile (git-ignored, used by every scored trial) and writes
    aggregate facts to evaluation/results/comprehensive_reset_verification.json.
    """
    import hashlib
    profiles = _load_profiles()
    agg_path = RESULTS / "comprehensive_reset_verification.json"
    agg = json.loads(agg_path.read_text()) if agg_path.exists() else {}
    for env in envs:
        if ENVS[env]["kind"] not in {"targetctl", "crawlground", "whiteboard"}:
            continue
        ext = External(env, require_profile=False)
        cycles: list[dict[str, Any]] = []
        status = "ok"
        for cycle in range(2):
            t0 = time.monotonic()
            try:
                ext.setup()
                rec = dict(ext.reset, up_seconds=round(time.monotonic() - t0, 1))
            except Exception as exc:
                rec = dict(ext.reset, error=f"{type(exc).__name__}: {str(exc)[:300]}")
                status = "reset_failure" if isinstance(exc, ResetFailure) else "setup_failure"
            ext.teardown()
            rec.update({k: ext.reset.get(k) for k in ("teardown_exit", "residual_containers_after_teardown",
                                                      "trial_volumes_remaining_after_teardown")})
            cycles.append(rec)
            log(f"reset-verify {env} cycle {cycle}: {rec.get('error') or 'ok'} "
                f"tmpfs={rec.get('tmpfs_mounts')} volumes={rec.get('volume_mounts')} "
                f"rw_binds={rec.get('writable_bind_mounts')} teardown_exit={rec.get('teardown_exit')} "
                f"residual={rec.get('residual_containers_after_teardown')}")
            if status != "ok":
                break
        same_profile = len(cycles) == 2 and cycles[0].get("mount_profile") == cycles[1].get("mount_profile")
        if status == "ok" and not same_profile:
            status = "reset_failure: mount profile differs between cycles"
        if status == "ok":
            profiles[env] = {"mount_profile": cycles[0]["mount_profile"], "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        profile = cycles[0].get("mount_profile") or {}
        agg[env] = {
            "status": status, "cycles": len(cycles),
            "containers_per_cycle": [len(c.get("container_ids") or []) for c in cycles],
            "container_ids_disjoint_between_cycles": len(cycles) == 2 and not (
                set(cycles[0].get("container_ids") or []) & set(cycles[1].get("container_ids") or [])),
            "volume_names_disjoint_between_cycles": len(cycles) == 2 and not (
                set(cycles[0].get("volume_names") or []) & set(cycles[1].get("volume_names") or [])),
            "mount_profile_identical_between_cycles": same_profile,
            "mount_profile_digest": hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()[:16],
            "services": len(profile),
            "services_with_tmpfs": sum(1 for v in profile.values() if v["tmpfs"]),
            "tmpfs_mounts": cycles[0].get("tmpfs_mounts"), "volume_mounts": cycles[0].get("volume_mounts"),
            "writable_bind_mounts": cycles[0].get("writable_bind_mounts"),
            "named_volumes_before_start": [c.get("named_volumes_before_start") for c in cycles],
            "pre_start_down_exit": [c.get("pre_start_down_exit") for c in cycles],
            "teardown_exit": [c.get("teardown_exit") for c in cycles],
            "residual_containers_after_teardown": [c.get("residual_containers_after_teardown") for c in cycles],
            "trial_volumes_remaining_after_teardown": [c.get("trial_volumes_remaining_after_teardown") for c in cycles],
            "up_seconds": [c.get("up_seconds") for c in cycles],
            **({"errors": [c["error"] for c in cycles if c.get("error")]} if any(c.get("error") for c in cycles) else {}),
        }
        RESET_PROFILES.parent.mkdir(parents=True, exist_ok=True)
        RESET_PROFILES.write_text(json.dumps(profiles, indent=1))
        agg_path.write_text(json.dumps(agg, indent=1) + "\n")
    return agg


def select_post_diagnostic_envs(primary_base: Path) -> list[str]:
    """Preregistered rule: in-process fixtures where any primary trial recorded a post_forms_disabled skip."""
    chosen = []
    for env, spec in ENVS.items():
        if spec["kind"] != "inproc":
            continue
        for path in sorted((primary_base / env).glob("trial_*/trial.json")):
            row = json.loads(path.read_text())
            skips = ((row.get("capabilities") or {}).get("evidence_status") or {}).get("advertised_by_skip_reason") or {}
            if skips.get("post_forms_disabled", 0) > 0:
                chosen.append(env); break
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("child")
    c.add_argument("--env", required=True); c.add_argument("--out", type=Path, required=True)
    c.add_argument("--url"); c.add_argument("--no-instrumentation", action="store_true")
    c.add_argument("--post-diagnostic", action="store_true")
    r = sub.add_parser("run")
    r.add_argument("--envs", default="all"); r.add_argument("--trials", type=int, default=3)
    r.add_argument("--base", type=Path); r.add_argument("--no-instrumentation", action="store_true")
    r.add_argument("--post-diagnostic", action="store_true",
                   help="supplementary Track S: allow_post_forms on in-process fixtures only (--envs auto = preregistered rule)")
    v = sub.add_parser("reset-verify")
    v.add_argument("--envs", required=True)
    s = sub.add_parser("summarize")
    s.add_argument("--base", type=Path); s.add_argument("--post-diagnostic", action="store_true")
    args = ap.parse_args()
    if args.cmd == "child":
        child(args.env, args.out, args.url, not args.no_instrumentation, args.post_diagnostic)
        return
    if args.cmd in {"run", "reset-verify"}:
        if not tree_clean(("agent1",)):
            raise SystemExit("agent1/ has uncommitted changes: the evaluated agent is not frozen")
        base = args.base if args.cmd == "run" and args.base else (
            BASE_POST if args.cmd == "run" and args.post_diagnostic else BASE)
        if args.cmd == "reset-verify":
            base = RESET_PROFILES.parent
        envs = list(ENVS) if args.envs == "all" else args.envs.split(",")
        if args.cmd == "run" and args.post_diagnostic:
            envs = select_post_diagnostic_envs(BASE) if args.envs == "auto" else envs
            if any(ENVS[e]["kind"] != "inproc" for e in envs):
                raise SystemExit("the POST diagnostic runs only on in-process development fixtures")
        base.mkdir(parents=True, exist_ok=True)
        logf = (base / "run_log.txt").open("a")

        def log(msg: str) -> None:
            line = f"{time.strftime('%H:%M:%S')} {msg}"
            print(line, flush=True); logf.write(line + "\n"); logf.flush()
        log(f"revision {git_revision()} {args.cmd}{' post-diagnostic' if getattr(args, 'post_diagnostic', False) else ''} envs {envs}")
        if args.cmd == "reset-verify":
            reset_verify(envs, log)
            return
        for env in envs:
            run_env(env, args.trials, base, not args.no_instrumentation, log, args.post_diagnostic)
        return
    from evaluation.comprehensive_summary import summarize
    summarize(args.base or (BASE_POST if args.post_diagnostic else BASE), post_diagnostic=args.post_diagnostic)


if __name__ == "__main__":
    main()
