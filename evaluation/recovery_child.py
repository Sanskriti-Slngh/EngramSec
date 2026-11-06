"""Standalone child for evaluation/recovery_transfer.py.

Imports `agent1` only from PYTHONPATH (the current checkout or a historical worktree),
builds RunConfig verbatim from --config, runs one exploration and writes its outputs.
"""
import argparse
import json
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--url", required=True)
ap.add_argument("--config", required=True)
ap.add_argument("--code-root", type=Path, required=True)
args = ap.parse_args()

from agent1.explorer import Explorer  # noqa: E402
from agent1.exporter import write_outputs  # noqa: E402
from agent1.schema import RunConfig  # noqa: E402

config = RunConfig(start_url=args.url, output_dir=args.out, **json.loads(args.config))
t0 = time.monotonic()
explorer = Explorer(config, args.code_root)
artifact = explorer.run()
write_outputs(artifact, args.out)
budget = getattr(explorer, "http_budget", None)
(args.out / "child_meta.json").write_text(json.dumps({
    "wall_seconds": round(time.monotonic() - t0, 2),
    "agent1_module": __import__("agent1").__file__,
    "http_scope": {"blocked_out_of_scope": getattr(budget, "blocked", None) if budget else None}}, default=str))
