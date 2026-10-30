# Architecture comparison: external discovery, hierarchical exploration, state reuse

**Bottom line.** None of the new architectures produced a material coverage gain at comparable cost on Crawl Maze. The best arm, the existing explorer plus ZAP Traditional Spider seeds (B), scored 27/91 vs 25/91 for the frozen baseline (A). It needed 71% more HTTP requests, and the gain is net of an equal-sized displacement of the baseline's own discoveries. Area-level hierarchical exploration (C) was worse than the baseline (23/91). Verified state reuse (H4) only matters when paired with the hierarchical scheduler. Together they cut discovery root reloads by 42% (53 → 31), which recovered the hierarchical loss but did not beat B. The JavaScript category stayed at 3/27 in every arm. A follow-up analysis shows why. Every run ended with ≈ 500 safe controls advertised but never executed (483 plain links, 20 clicks, including all the multi-step JS buttons), against a 300-action budget, and ≈ 40% of actions went to restoration. A passive event-instrumentation probe found no hidden listeners or JS-API URLs at page load. On this target, browser-action allocation is the first-order bottleneck, ahead of both scheduling and observation. The next experiment is in [HIERARCHICAL_EXPLORATION_REPORT.md §5](HIERARCHICAL_EXPLORATION_REPORT.md#5-next-hypothesis-channel-split-then-event-driven-instrumentation): split plain GET links onto the HTTP channel and reserve browser actions for real interactions, then add event-driven instrumentation.

## Setup

- Target: Google Security Crawl Maze (revision `2a0dd0a`, Flask, `127.0.0.1:3460`), the same server for all runs, run strictly one at a time. The target is stateless across runs.
- Budget per arm: 180 s wall clock, 300 browser actions, 120 transitions, one browser worker, 100 typed-resource GETs (70 document / 20 script / 10 stylesheet / 20 asset), shared HTTP cap 1,000. Adaptive readiness, persistent exploration, shallow replay, no models, $0.
- Every run hit the **300-action cap at 155–164 s**. Actions, not wall time or HTTP, were the binding constraint.
- Scoring: `experiments/summarize_architecture_comparison.py` uses the same `any_fetch` definition as `score_crawlmaze_posthoc.py`: a 2xx browser response or a 2xx typed-spider GET present in the run's own Graph A. Expected paths come from the documented evaluator endpoint only after a run stops. **Every number below is a live integrated result. No offline unions are scored.**
- ZAP evidence: the existing sanitized Traditional Spider history from [ZAP_DISCOVERY_COMPARISON.md](ZAP_DISCOVERY_COMPARISON.md) (ZAP `D-2026-10-29`, 1 thread, POST forms/robots/sitemap off, no active scan). It was imported at the start of each B/D/E run rather than re-crawled live, because the traditional spider is deterministic on this static target and ZAP was not reinstalled. Its cost is charged as **344** requests, the history-entry upper bound. 212 entries carried responses, so the true transport count lies in [212, 344]. ZAP's 2.0 s runtime is added to elapsed time for per-minute rates. Client Map YAML was not used.

## Arms

| Arm | Exploration policy | ZAP seeds | State reuse |
|---|---|---|---|
| A | existing multidimensional priority queue (frozen) | – | root reload + path |
| B | A | yes | root |
| C | hierarchical area tour (`agent1/hierarchical.py`) | – | root |
| D | C | yes | root |
| E | C | yes | verified live prefix + one-step history return |
| AH (H4 isolation) | A | – | as E |
| E-prefix-only (negative control) | C | yes | live prefix only (no history return) |

## Results (180 s, mean over repeats; runs were deterministic, min = max for every repeated arm)

| Arm | Runs | Markers /91 | Gained / lost vs A | Only via ZAP seed | Transitions | Replays validated | Untested | Discovery root reloads | Verification reloads | Restoration actions | HTTP total | Markers / min | Markers / 100 req |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 3 | **25** | – | 0 | 103 | 23 | 80 | 49 | 23 | 76 | 496 | 9.30 | **5.04** |
| B | 3 | **27** | +10 / −8 | 4 | 102 | 24 | 78 | 48 | 24 | 75 | 847 | **9.74** | 3.19 |
| C | 1 | 23 | +5 / −7 | 0 | 96 | 22 | 74 | 54 | 22 | 86 | 490 | 8.85 | 4.69 |
| D | 1 | 24 | +10 / −11 | 5 | 95 | 23 | 72 | 53 | 23 | 84 | 840 | 9.06 | 2.86 |
| E | 3 | 26 | +11 / −10 | 5 | 105 | 26 | 79 | **31** | 26 | 84 | 848 | 9.47 | 3.07 |
| AH | 1 | 25 | 0 / 0 | 0 | 103 | 24 | 79 | 48 | 24 | 76 | 498 | 9.34 | 5.02 |
| E-prefix-only | 1 | 24 | – | 5 | 96 | 22 | 74 | 54 | 22 | 86 | 839 | 9.14 | 2.86 |

All 13 runs: replay success 100% of attempted, 0 self-audited incorrect state merges, 0 missing Graph A evidence connections, 0 HTTP budget overruns, 0 external records promoted to replay, every external record with complete provenance. Every run reached the same 7 coarse functional areas (first URL segment of observed states). Distinct request structures: A 185, B 179, C 176, D 169, E 189. Restoration actions include E's 30 history steps. Root reloads are not counted as restoration actions.

HTTP by source (run 1): A = 310 browser + 95 redirect hops + 91 spider; B adds 344 ZAP and uses 97 spider GETs. The 95 redirect hops (Crawl Maze issues 308 trailing-slash redirects) were uncharged before this milestone's accounting fix.

Category breakdown: JavaScript stayed at **3/27 in every arm**. Headers 3→4/4 and CSS 0→1/1 with ZAP. HTML 16–19/57.

## Interpretation by hypothesis

- **H1, external discovery supplies useful nonduplicate candidates: supported, but not as a net coverage win at equal cost.** ZAP seeds produced 8 markers the baseline never reached (4 not referenced anywhere by Agent 1's own discovery). In the integrated system, all 8 of B's losses were markers A had reached only through its own typed spider. Seeds and Agent 1's references compete for the same 100-GET spider budget. The two sources are complementary (an offline union would be 35/91; reported only as a diagnostic, never as a result). The integrated design converts that complementarity into +2 for +344 requests.
- **H2, hierarchical exploration visits more functionality: refuted on this target.** The planner did what it was designed to do: 14 area switches vs 36 for the baseline. But staying in an area does not make the next action cheap. Crawl Maze is a tree of dead-end leaves. Without a way back up the tree, two siblings in the same area are as far apart as two leaves in different areas (root reload + full path). The planner also gave up the baseline's opportunistic live-state reuse (44 vs 58 live reuses), producing more root reloads (54 vs 49) and fewer transitions (96 vs 103).
- **H3, external + hierarchical is complementary: refuted.** D (24) < B (27); D < C + B's gain.
- **H4, reusing verified state reduces root restoration: supported mechanistically, coupled to H2.** The first implementation, reusing a live prefix and executing only the suffix, never fired (0 times; E-prefix-only). In single-session persistent exploration the live page is always the deepest state just reached, so no frontier item is ever its unvisited strict descendant. The verified one-step history return fired 30 times in E with 0 rejections. Discovery root reloads fell 53 → 31, transitions rose 95 → 105 and replays 23 → 26, for +2 markers over D. With the baseline scheduler (AH) it never triggered: the global priority queue never selects a sibling of the live page, so H4 depends on a locality-seeking scheduler. E still trails B by one marker.

## Decision

- **Keep** the ZAP Traditional Spider evidence adapter and its Graph A provenance (opt-in). It adds externally grounded candidates, and its cost is now fully accounted for.
- **Keep** the shared HTTP ledger with redirect-hop accounting (on whenever `--max-total-http-requests` is set).
- **Keep but do not default** the hierarchical policy and `--state-reuse prefix`. They are a coherent pair that cuts restoration cost but has not shown a coverage gain, and they regress both fixtures (JS lab −2 request structures; the shop's cart-POST → checkout chain was never executed). The default remains the frozen multidimensional explorer, which reproduced its historical fixture results.
- **Stop** tuning area keys, tour windows or switch limits. The data show the bottleneck is elsewhere (below and in the report).

## Open question worth one cheap experiment

Whether A, with its own typed spider allowed to spend the HTTP budget B spends on ZAP (≈ 100 + 344 GETs, for example on the 483 unexecuted safe links), matches or beats B. That is the true equal-cost test of H1, and the first half of the channel-split experiment. It was not run because the browser evaluation cap had been reached.

## Limitations

- One target (Crawl Maze) for the primary comparison; the JS-heavy lab and the shop fixture are regression checks only. C and D have one run each. Arms are deterministic, but a different server revision or timing environment could shift single markers.
- ZAP was replayed from one recorded run, not run live per arm. Its request charge is an upper bound and is not enforced in-flight (ZAP has no global request cap). Agent 1's browser and spider traffic was enforced in-flight.
- Redirect hops after the first in a chain cannot be refused by Playwright routing (it does not route redirects). They are charged exactly but enforced only at the first hop. 0 overruns and 0 unblockable out-of-scope hops occurred.
- Functional areas are the first URL path segment. On hash-routed SPAs this collapses to one area, so the planner degenerates to the local-cost ordering.
- Browser evaluation time used: ≈ 45 min (2 smoke runs, 13 Crawl Maze runs, 4 fixture regressions, 2 passive probe passes). That is over the 35 min cap: the Crawl Maze comparison itself used ≈ 37 min, and the mandatory fixture regressions and the probe came after. The 300-second serious run was not executed because there was no genuine win to confirm.

## Reproduction

```sh
experiments/run_architecture_comparison.sh agent1/experiments/architecture_comparison 180 A_r1 B_r1 C_r1 D_r1 E_r1 AH_r1
cd experiments && ../.venv/bin/python summarize_architecture_comparison.py \
  --root ../agent1/experiments/architecture_comparison \
  --category-graph ../agent1/experiments/hierarchy_tournament/adaptive_readiness_A_baseline/graph_a.json \
  --out ../agent1/experiments/architecture_comparison/comparison_summary.json
```

Committed: per-run `metrics.json`, `experiment_config.json`, `report.md`, `graph_a.mmd`, and the aggregate `comparison_summary.json` (counts only, no expected-path lists). Full Graph A, traces and checkpoints stay local (git-ignored).
