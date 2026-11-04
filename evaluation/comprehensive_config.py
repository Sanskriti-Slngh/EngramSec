"""Frozen configuration for the comprehensive Agent 1 benchmark evaluation.

See AGENT1_COMPREHENSIVE_EVALUATION_PREREGISTRATION.md. The evaluated agent is the
production `agent1.cli map` path with the same settings as the 2026-10-28 frozen
WebExploitBench protocol (WEBEXPLOITBENCH_EVALUATION.md): CLI defaults plus
`--policy coverage --seconds 180 --max-transitions 100 --max-browser-actions 500`.
Only the start URL, output directory and a descriptive context label vary.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Exactly the RunConfig fields the CLI sets for that command line (everything else = RunConfig default).
FROZEN = dict(
    policy="coverage",
    max_seconds=180.0,
    max_transitions=100,
    max_browser_actions=500,
    model_provider="none",
    allow_post_forms=False,
    state_aware_exploration=True,
    record_aware_graph=True,
    exploration_mode="fresh",
    replay_policy="shallow",
)

# Opt-in, evidence-only instrumentation. Enabled in scored runs only if the preflight
# (evaluation/comprehensive_preflight.py) shows it does not change legacy behavior.
INSTRUMENTATION = dict(acg_evidence=True, action_ledger=True)


def git_revision() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def tree_clean(paths: tuple[str, ...] = ("agent1",)) -> bool:
    out = subprocess.run(["git", "status", "--porcelain", "--", *paths], cwd=ROOT, capture_output=True, text=True)
    return out.stdout.strip() == ""
