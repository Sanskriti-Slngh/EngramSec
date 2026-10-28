# EngramSec V1 — bounded novelty probes (model-free)

**Purpose:** Compare a deterministic BFS/DFS hybrid against the already-committed V0 BFS baseline using the same local SiyuCMS starting URL, depth cap, and GET request budget.

This package **adds** `hybrid.py`, `compare_runs.py`, `V1_README.md`, and `tests/test_hybrid.py` to your existing `engramsec_v0` folder. It does not modify `crawler.py`.

## How the hybrid selects a page

1. Keep every eligible discovered URL in the normal FIFO BFS queue.
2. Normally process the next FIFO URL.
3. If an HTTP 3xx redirect is discovered, optionally follow its allowed same-origin `Location` immediately. This is independently configurable because it can explain much of any measured gain.
4. If a non-homepage HTML page exposes at least one new URL or a new form signature, consider its unvisited linked pages. Prefer a child with an unvisited route pattern, then an unexplored path-based feature group, then original link order.
5. Visit **one** prioritized child immediately, following at most `--probe-hops` consecutive probe edges before reverting to the BFS queue. Do not exceed `--max-depth` or `--max-pages`.

This is a **heuristic**, not learned decision-making. It is HTTP GET only, never submits forms, follows no links to other origins, and uses only webpage content.

## Install

Unzip `engramsec-v1-hybrid.zip` into the existing folder `~/EngramSec/engramsec_v0`. Then:

```bash
cd ~/EngramSec/engramsec_v0
source .venv/bin/activate
python -m pip install matplotlib
python -m unittest discover -s tests -v
```

The packaged files assume you already have `crawler.py` and its `requests` and `beautifulsoup4` dependencies.

## Fair 40-GET benchmark

Keep the same target running and compare these three policies:

```bash
python hybrid.py --url http://127.0.0.1:51707/ --max-pages 40 --max-depth 4 --delay 0.25 --probe-hops 0 --out outputs/redirect_only_40
python hybrid.py --url http://127.0.0.1:51707/ --max-pages 40 --max-depth 4 --delay 0.25 --probe-hops 2 --out outputs/hybrid_40
python compare_runs.py \
  --run BFS outputs/siyucms_bfs_40/graph_a.json \
  --run RedirectOnly outputs/redirect_only_40/graph_a.json \
  --run Hybrid outputs/hybrid_40/graph_a.json \
  --out outputs/compare_40
```

`--probe-hops 0` does **not** disable immediate redirect following. This intentionally gives a separate redirect-only ablation. To disable both:

```bash
python hybrid.py --url http://127.0.0.1:51707/ --max-pages 40 --max-depth 4 --delay 0.25 --probe-hops 0 --no-immediate-redirect --out outputs/v1_bfs_sanity
```

`compare_runs.py` produces `policy_comparison.png` (one figure with two small panels) and `summary.csv`. The summary includes `first_form_GETs` and a rough area under the cumulative distinct-form curve (`unique_form_AUC`): higher indicates earlier discovery within the same request budget.

## Interpretation

- Treat `distinct_form_signatures` as form **structure**, not proven unique functionality.
- Count visited route patterns separately from discovered routes. Depth achieved is diagnostic, not itself the goal.
- If Hybrid finds login earlier but RedirectOnly does too, the gain is from **redirect prioritization**, not an adaptive DFS policy. This three-arm experiment keeps that distinction visible.
- Multiple repeated runs on the same local application are useful for checking determinism; rerun if a server error or environment change affects a result.
- The local target-manager run is not an official scored CAGE trial.
