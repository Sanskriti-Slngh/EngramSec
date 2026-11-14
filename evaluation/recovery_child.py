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
try:
    # Security-oriented capability evidence, derived post-run from the ACG export (never a verdict).
    from agent1.model.importer import import_run_artifact
    from agent1.model.materialize import materialize
    from agent1.security_evidence import capability_evidence
    run = artifact.model_dump(mode="json")
    export = materialize(import_run_artifact(run, "run.json", None)).model_dump(mode="json")
    (args.out / "capability_evidence.json").write_text(
        json.dumps(capability_evidence(export, run), indent=1, ensure_ascii=False) + "\n")
except Exception as exc:  # evidence-only; older agent code has no view
    (args.out / "capability_evidence.error.txt").write_text(f"{type(exc).__name__}: {exc}\n")
budget = getattr(explorer, "http_budget", None)
(args.out / "child_meta.json").write_text(json.dumps({
    "wall_seconds": round(time.monotonic() - t0, 2),
    "agent1_module": __import__("agent1").__file__,
    "http_scope": {"blocked_out_of_scope": getattr(budget, "blocked", None) if budget else None}}, default=str))
