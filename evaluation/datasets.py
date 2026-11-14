"""Development datasets for the offline ACG (frozen in Phase 0).

Only development applications. Held-out (ComfyUI, PrestaShop) and validation
(SiyuCMS, held-out shop) archives are deliberately absent and must not be
added here. Raw archives stay local (git-ignored); only aggregates are
committed.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "agent1" / "experiments"

DATASETS: dict[str, dict[str, object]] = {
    "stateful_lab": {"annotation": "stateful_lab", "role": "primary",
                     "archives": ["stateful_fixture_example/graph_a.json"]},
    "replay_lab": {"annotation": "replay_lab", "role": "primary",
                   "archives": ["replay_lab_probe_20261031/structure/checkpoint.json"]},
    "js_heavy_lab": {"annotation": "js_heavy_lab", "role": "primary",
                     "archives": [f"js_heavy_p2_r{i}/run.json" for i in (1, 2, 3, 4)]},
    "whiteboard": {"annotation": "whiteboard", "role": "identity",
                   "archives": [f"state_aware_whiteboard_final_20261031/{arm}/adaptive_readiness/run.json"
                                for arm in ("A_baseline", "B_state", "C_state_record_1", "C_state_record_2",
                                            "C_state_record_3")]},
    "crawl_maze": {"annotation": None, "role": "diagnostic",
                   "archives": [f"replay_crawlmaze_3x3/adaptive_readiness_{arm}_s0/run.json"
                                for arm in ("R0", "R1", "R2")]
                   + ["state_aware_crawlmaze_20261031/adaptive_readiness_final/run.json"]},
}

FORBIDDEN_FRAGMENTS = ("webexploitbench", "comfyui", "prestashop", "siyucms", "heldout")


def archive_paths(name: str) -> list[Path]:
    paths = [EXP / rel for rel in DATASETS[name]["archives"]]  # type: ignore[index]
    for path in paths:
        if any(fragment in str(path).lower() for fragment in FORBIDDEN_FRAGMENTS):
            raise ValueError(f"non-development archive refused: {path}")
    return paths
