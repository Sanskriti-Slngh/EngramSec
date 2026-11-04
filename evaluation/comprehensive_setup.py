"""Track B setup verification for the comprehensive evaluation (no mapping).

Sequentially, one target at a time: optional `targetctl build` (timed), then a fresh
`targetctl up` through the evaluation harness (loopback check, HTTP readiness), memory
sample after readiness and 30 s later, then `targetctl down`. Only aggregate setup facts
are written (evaluation/results/comprehensive_setup.json). Resource limits are not raised:
a target that cannot start within the harness limits is recorded as a setup failure.

  .venv/bin/python -m evaluation.comprehensive_setup siyucms prestashop comfyui jetlinks white-jotter
"""
from __future__ import annotations

import json
import subprocess
import sys
import time

from evaluation.comprehensive_eval import BENCH, RESULTS, External

BUILD_TIMEOUT_S = 3600


def disk_free_gb() -> float:
    import shutil
    return round(shutil.disk_usage(str(BENCH)).free / 1e9, 1)


def main() -> None:
    path = RESULTS / "comprehensive_setup.json"
    results = json.loads(path.read_text()) if path.exists() else {}
    for target in sys.argv[1:]:
        prior = results.get(target, {})
        row: dict = {"disk_free_gb_before": disk_free_gb()}
        if prior.get("build_exit") == 0:          # keep the first (uncached) build measurement
            row.update({k: prior[k] for k in ("build_seconds", "build_exit", "new_images", "disk_free_gb_after_build")
                        if k in prior})
            row["setup_attempts_before"] = prior.get("setup_attempts_before", 0) + 1
            row["previous_status"] = prior.get("status")
        if row["disk_free_gb_before"] < 50:
            row["status"] = "setup_failure: disk below 50 GB"
            results[target] = row; continue
        if target in {"jetlinks", "white-jotter"} and row.get("build_exit") != 0:
            before = set(subprocess.run(["docker", "images", "-q"], capture_output=True, text=True).stdout.split())
            t0 = time.monotonic()
            try:
                r = subprocess.run([str(BENCH / "scripts/targetctl"), "build", target], cwd=BENCH, capture_output=True,
                                   text=True, timeout=BUILD_TIMEOUT_S)
                row["build_seconds"] = round(time.monotonic() - t0, 1)
                row["build_exit"] = r.returncode
                if r.returncode:
                    row["build_error_tail"] = (r.stderr or r.stdout).strip().splitlines()[-5:]
            except subprocess.TimeoutExpired:
                row["build_seconds"] = BUILD_TIMEOUT_S; row["build_exit"] = "timeout"
            after = subprocess.run(["docker", "images", "--format", "{{.ID}}\t{{.Size}}"], capture_output=True,
                                   text=True).stdout.splitlines()
            row["new_images"] = [line.split("\t")[1] for line in after if line.split("\t")[0] not in before]
            row["disk_free_gb_after_build"] = disk_free_gb()
            if row["build_exit"] != 0:
                row["status"] = "setup_failure: build"
                results[target] = row
                path.write_text(json.dumps(results, indent=1)); print(target, row, flush=True)
                continue
        ext = External(target)
        t0 = time.monotonic()
        try:
            ext.setup()
            row["up_to_ready_seconds"] = round(time.monotonic() - t0, 1)
            row["containers"] = len(ext.names)
            row["mem_mb_at_ready"] = ext.mem_mb()
            time.sleep(30)
            row["mem_mb_ready_plus_30s"] = ext.mem_mb()
            row["loopback_only_verified"] = True
            row["status"] = "ok"
        except Exception as exc:
            row["up_seconds"] = round(time.monotonic() - t0, 1)
            row["status"] = "setup_failure: " + str(exc)[:300]
        finally:
            t1 = time.monotonic()
            ext.teardown()
            row["down_seconds"] = round(time.monotonic() - t1, 1)
        results[target] = row
        path.write_text(json.dumps(results, indent=1))
        print(target, row, flush=True)


if __name__ == "__main__":
    main()
