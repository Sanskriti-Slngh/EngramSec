# Coverage ablations

## Protocol

Google Security Crawl Maze was started only on loopback at `http://127.0.0.1:3460/`. All runs began at `/`. The post-run scorer derived the same five public root categories for each graph and fetched the official expected-path set only after a run ended. The mapper received only the root URL, generic policy/configuration, normal browser observations, and its own evidence. It never imported the scorer or the expected-path data.

The matched 180-second matrix used 300 browser actions, 120 transitions, 100 spider GETs, one browser worker, maximum resource depth 3, and the same class ceilings: 70 documents, 20 scripts, 10 stylesheets, 20 other assets. The fixed configurations used the same persistent exploration mode and extended interaction profile. Adaptive readiness was the sole readiness variable in its ablation. Three independent repeats were run for the leading adaptive configuration and for the fixed FIFO comparator. The 300-second run used 600 browser actions, 250 transitions, 200 GETs, and class ceilings 140/40/20/40; it is a scaling experiment, not a matched-budget comparison.

The old pre-change run took 181.543 seconds, used 285 browser actions, fetched 100 spider resources, and reached 16/91 paths. It did not record the newly added resource class policy. Therefore the historical cross-commit row is useful but cannot isolate any one new code component.

## Matched 180-second ablations

| Variant | Repeats | Any fetched | Referenced | Spider / browser | Replay attempts | Wall time | Readiness wait (passive + interactive) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Historical pre-change | 1 | 16/91 | 22/91 | 8 / 11 | 32/32 | 181.5 s | 141 s reported historically |
| FIFO, AST, shared queue, fixed readiness | 3 | 20–21/91 | 26–27/91 | 14–15 / 11 | 31–32/31–32 | 180.5–182.5 s | 140.9–143.6 s |
| Route-diverse resource frontier | 1 | 21/91 | 27/91 | 15 / 11 | 33/33 | 181.6 s | 142.2 s |
| Marginal reference-yield frontier | 1 | 21/91 | 27/91 | 15 / 11 | 32/32 | 180.6 s | 141.4 s |
| Seeded random resource frontier | 1 | 21/91 | 27/91 | 15 / 11 | 33/33 | 180.9 s | 139.9 s |
| AST extractor → legacy regex extractor | 1 | 21/91 both | 27/91 both | 15 / 15 | 32/32 vs 30/30 | 180.6–181.8 s | comparable |
| Adaptive readiness, fixed replay reserve | 3 | 25/91 each | 35/91 each | 17 / 14 | 24/24 | 162.4–164.0 s | 117.4–118.8 s |
| Adaptive readiness + adaptive replay reserve | 1 | 24/91 | 33/91 | 17 / 13 | 28/28 | 162.4 s | 117.6 s |
| Adaptive readiness + diverse replay | 2 | 25/91 each | 35/91 each | 17 / 14 | 23/23; 21/22 | 166.3–166.9 s | 120.6–121.6 s |
| Document quota raised 70→90 | 1 | 19/91 | 28/91 | 13 / 11 | 31/31 | 181.0 s | 141.3 s |
| No shared resource frontier | 1 | 22/91 | 26/91 | 16 / 11 | 33/33 | 181.5 s | 141.0 s |
| Recursive depth 3→6 | 1 | 17/91 | 21/91 | 12 / 11 | 32/32 | 181.0 s | 140.9 s |

Replay `N/M` is successful fresh-context path attempts, not the number of observed transitions; paths not attempted are separately shown in the Graph A metrics. The adaptive-budget row is not a repeated winner. Diverse replay is a destination-variety experiment; one of its two runs had one failure. The parser comparison shows no Crawl Maze recall gain from AST alone.

The adaptive readiness repeats produced 25/91 each, 35 expected paths referenced, 17 spider paths, 14 browser paths, 89 successful resource responses from 91 GET attempts, and zero missing Graph A evidence connections. The fixed FIFO repeats produced 20, 21, and 21. Adaptive readiness therefore improved marker yield by 4–5 paths in this corpus at the same nominal time/action budget, while increasing observed transitions and the number left untested.

The four resource selection policies (FIFO, route diversity, empirical marginal yield, random) all found the same 21/91 marker set. A selector-only investment is not supported by these results. Raising the document cap used more GETs but reduced score; increasing depth raised extracted-reference volume but reduced score. Both are retained as negative evidence.

## Fast and serious budgets

| Budget / policy | Any fetched | Referenced | Replay | Actual time/actions | Notes |
|---|---:|---:|---:|---:|---|
| 60 s, FIFO | 7/91 | 11/91 | 18/18 | 60.9 s / 109 actions | 44/44 resource GETs succeeded |
| 60 s, adaptive readiness | 7/91 | 11/91 | 21/21 | 60.2 s / 121 actions | Same marker set; more replay attempts |
| 180 s, adaptive readiness (3 repeats) | 25/91 | 35/91 | 24/24 | 162–164 s / 298–299 actions | Stable coverage result |
| 300 s, adaptive readiness | 37/91 | 52/91 | 54/54 | 301.7 s / 598 actions | Larger budget; not directly comparable to 180 s as a policy effect |

In the 300-second run, the post-run cumulative curve reached 6 markers by 30 seconds, 15 by 60, 25 by 120, 34 by 180, and 37 by 300. The run ended at about 302 seconds; 37 at 600 seconds in the scorer's time bucket means only that all markers from this run had arrived by then, not that a 600-second experiment was performed. Marginal coverage slowed after 180 seconds.

## Category and funnel detail at serious budget

| Category | Expected | Referenced | Spider fetched | Browser fetched | Any fetched |
|---|---:|---:|---:|---:|---:|
| CSS | 1 | 1 | 0 | 0 | 0 |
| Response headers | 4 | 3 | 3 | 1 | 3 |
| HTML | 57 | 34 | 24 | 19 | 31 |
| JavaScript | 27 | 14 | 0 | 3 | 3 |
| Miscellaneous | 2 | 0 | 0 | 0 | 0 |

The independent evaluator's serious-run funnel was 91 expected → 52 referenced → 36 admitted → 27 spider attempted/succeeded, with 23 successful browser requests and 2 paths represented as UI states. The union reached 37/91. No claim is made that browser requests, fetched resources, UI states, and replayed workflows are interchangeable.

## Reproducibility

Start the isolated testbed on loopback:

```sh
cd /private/tmp/security-crawl-maze
/private/tmp/crawlmaze-venv/bin/flask --app app run --host 127.0.0.1 --port 3460
```

Run the matched 180-second adaptive candidate:

```sh
cd /Users/sanskritisingh/EngramSec
PYTHONPATH=. .venv/bin/python experiments/run_resource_spider_ablation.py \
  --root agent1/experiments/reproduction \
  --variants adaptive_readiness --tag repeat \
  --seconds 180 --max-transitions 120 --max-browser-actions 300 \
  --max-resource-fetches 100 \
  --document-budget 70 --script-budget 20 --stylesheet-budget 10 --asset-budget 20
```

Score only after that command completes:

```sh
PYTHONPATH=. .venv/bin/python experiments/score_crawlmaze_posthoc.py \
  --root agent1/experiments/reproduction \
  --baseline-graph agent1/experiments/frontier_matrix/fifo_fixed_budget/graph_a.json \
  --out agent1/experiments/reproduction/posthoc.json
```

The post-run scorer contacts the local testbed's evaluation interface. Its response is not imported by `agent1/` and must not be supplied to future exploration runs.
