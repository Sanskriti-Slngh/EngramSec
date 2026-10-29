# Crawlground ablations

## Protocol

All scored runs used official `zaproxy/crawlground` revision `ba52303a5fd43795f461a6df39da45e2fe886c6b`, started at `/`, used one headless Chromium worker, and received an isolated official tool bucket. The mapper never accessed marker expectations. FAST was 60 seconds, 30 transitions, and 140 actions. SERIOUS was at most 600 seconds, 250 transitions, and 600 actions. POST was enabled only because Crawlground is disposable and resettable.

The published ZAP Client Spider result of 45/59 is a reference, not a matched comparison. ZAP's current design combines the traditional spider with a client map, component-level crawling, adaptive waits, and DOM event streaming ([Client Spider](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/spider/), [July 2026 rationale](https://www.zaproxy.org/blog/2026-07-06-client-spider-now-recommended/), [changelog](https://www.zaproxy.org/docs/addons/client/changelog/)).

## Results

| Run | Budget | Markers | Replay | Actions | Root reloads | Observed transitions | Interpretation |
|---|---:|---:|---:|---:|---:|---:|---|
| Frozen `2b8aa18` FAST | FAST | 3/59 | 17/27 | 135 | 39 | 27 | Original small-budget baseline |
| Frozen `2b8aa18` SERIOUS | SERIOUS | 13/59 | 15/33 | 600 | 212 | 189 | Budget alone adds 10 markers but churn dominates |
| Iteration A: hybrid + extended alphabet, old scheduler | SERIOUS | not isolated | 18/44 | 598 | 203 | 186 | Artifact retained; marker bucket activation failed, so no score claim |
| Iteration B: initial multidimensional scheduler | SERIOUS | 1/59 | 8/46 | 598 | 51 | 250 | Negative result: whole-page event semantics trapped the crawler on results |
| Breadth-first baseline | FAST | 0/59 | 16/16 | 75 | 19 | 30 | Reliable shallow replay did not trigger useful interactions |
| Final multidimensional | FAST | 3/59 | 14/23 | 127 | 29 | 30 | No marker gain under the micro-budget |
| Final multidimensional | SERIOUS | **39/59** | **25/38** | 599 | 96 | 249 | +26 markers, 3.0× baseline score, and fewer reloads |

The final serious category counts were buttons 2/2, dynamic content 6/10, forms 8/12, frames 3/4, JavaScript events 10/14, links 4/7, navigation 6/9, and other 0/1. The frozen serious counts were respectively 1, 3, 4, 0, 2, 2, 1, and 0.

## What contributed

Hybrid observed-href navigation made the full category tree reachable without spending a click/restoration cycle for every ordinary link. The extended action alphabet exposed the strongest category gains: frames +3, JavaScript events +8, forms +4, and navigation +5 over the frozen serious run. Context-level popup handling and frame-aware extraction were directly exercised.

The corrected scheduler was necessary but not sufficient by itself. Its first version was dramatically worse (1/59) because global result descriptions caused 237 dynamic actions, 236 from `/results`. Local semantic gating, global-chrome deduplication, report-navigation penalties, scroll deduplication, and an eight-action local-state burst cap eliminated that trap. The final run suppressed 855 duplicate controls and reduced root reloads from 212 to 96.

Replay changes raised the serious success rate from 45.5% (15/33) to 65.8% (25/38). Exact-URL navigation checks avoid treating mutable result content as a wrong destination, while same-URL actions retain strict content/outcome checks. This is improvement, not completion: 13 attempts still failed and 211 observed paths were not replayed.

## What did not contribute or remains ambiguous

Increasing the budget alone improved the frozen mapper from 3 to 13 markers, so the 39 score cannot be attributed solely to code without reporting budget. Under identical FAST budgets, the final marker score remained 3; the architecture needs enough transitions to traverse categories before it pays off.

Iteration A cannot support a marker claim because the score-bucket activation request was blocked by the command network sandbox. Its Graph A and metrics remain preserved for action-cost analysis, but it is excluded from score comparisons.

No local ZAP run was attempted: ZAP was not installed, and installing the framework would have displaced the bounded implementation/evaluation work. The 39 versus published 45 figures use different budgets and environments and do not establish superiority.

## Independent transfer

After freezing the implementation, it ran once on official Google `security-crawl-maze` commit `2a0dd0a75e39925ded887bcd25016e8b3ce0f2b3`, using its local Flask mode (which omits bundled JS-framework cases). Under 180 seconds, 120 transitions, and 300 actions, Agent 1 observed 38 transitions, recorded 35 states and 54 action network events, and replayed 12/12 attempted paths. It consumed only 103 actions because passive-page readiness dominated wall time.

A post-freeze evaluator queried the testbed's public expected-results API for the five top-level categories. Of 91 applicable expected resource paths, 4 appeared in frozen Graph A URL/request/path evidence (4.4%). This is a clear transfer failure for resource-surface discovery even though path replay was reliable. The main missing class is non-anchor resource references and response-header/CSS/script-discovered URLs; the present “hybrid” crawler is still an anchor crawler plus browser interaction engine, not a comprehensive traditional web spider.

## Artifact map

Compact Graph diagrams, metrics, and reports are under `agent1/experiments/crawlground_breakthrough_*` and `agent1/experiments/crawlmaze_transfer_frozen`. Full run/checkpoint/trace/Graph JSON remains local and ignored because it is large and can contain browser state. Aggregate independent scores are in `agent1/experiments/crawlground_breakthrough_scores.json`.
