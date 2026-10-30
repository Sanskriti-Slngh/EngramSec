# Crawler breakthrough evidence package

This directory holds compact, post-run scoring outputs and diagrams for the 2026-10-30 Agent 1 iteration. The scorer output contains aggregate/category counts and no expected URL list. Full Graph A JSON, traces, and checkpoints remain in sibling ignored local run directories, where they can be inspected without bloating the committed artifacts.

## Main Graph A diagrams

- `graph_a_adaptive_180s.mmd` — representative repeated adaptive-readiness run (25/91 union paths; 24/24 replay attempts).
- `graph_a_serious_300s.mmd` — highest-coverage run (37/91; 54/54 replay attempts; 98 transitions untested).
- `serious_experiment_config.json` — effective target/configuration, source revision, and budgets for the 300-second run.

The source Graph A JSON files are retained locally at:

- `agent1/experiments/readiness_ablation/adaptive_readiness_ast_fifo_caps/graph_a.json`
- `agent1/experiments/serious_budget/adaptive_readiness_adaptive_ast_fifo_300s/graph_a.json`

Those files are ignored by Git along with raw checkpoints and traces. The public/local app contains no account credentials; all captured input and request-value redaction rules remain active.

## Scoring files

- `score_frontier_matrix.json` — FIFO, route diversity, marginal-yield, and seeded-random matched runs.
- `score_fifo_repeats.json` and `score_readiness_repeats.json` — three fixed and three adaptive 180-second repeats.
- `score_fast.json` — 60-second fixed/adaptive pair.
- `score_serious_300s.json` — 300-second, 600-action, 200-GET run.
- `score_document_quota.json`, `score_depth6.json`, `score_no_shared_frontier.json`, `score_legacy_regex.json`, and `score_adaptive_budget.json` — negative or mixed ablations.
- `score_diverse_replay1.json` and `score_diverse_replay2.json` — replay-destination diversity pair.
- `score_shop_transfer.json` and `score_js_lab_transfer.json` — independent fixture evaluation outputs.

Full methodology, budgets, and caveats: [`COVERAGE_ABLATIONS.md`](../../../COVERAGE_ABLATIONS.md) and [`GENERAL_PURPOSE_CRAWLER_BREAKTHROUGH.md`](../../../GENERAL_PURPOSE_CRAWLER_BREAKTHROUGH.md).
