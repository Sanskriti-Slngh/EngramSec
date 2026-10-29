# Independent generalization baseline and ablation

Date: 2026-10-29

## Frozen development testbed

`development_apps/js_heavy_lab.py` was frozen before Agent 1 changes. The mapper receives only its start URL. `evaluation_ground_truth/js_heavy_lab.json` is loaded only after Graph A is complete by `experiments/evaluate_generalization.py`.

The applicable denominator is 11 areas, 14 controls, 12 request surfaces, and two session contexts. Cases include 650 ms initialization, late hydration, a cosmetic clock, an explicit `127.0.0.1`/`localhost` alias, a five-action deep path, session-gated controls, repeated shallow navigation, an ineffective control, and initial/action Fetch traffic. One external destination is excluded from the reachable denominator but must be rejected.

All policies used one worker, a fresh server, 60-second/140-browser-action/30-transition caps, 35% replay reserve, identical form permission on this disposable fixture, and no models. P0 was run three times before `agent1/` changed. P1 and corrected P2 were each run three times. Browser actions include setup, restoration, exploration, and replay.

## Results

| Metric (three-repeat mean; range where variable) | P0 fresh/fixed wait | P1 fresh + readiness/origin | P2 P1 + persistent discovery |
|---|---:|---:|---:|
| Applicable area recall | 3/11 | 11/11 | 11/11 |
| Applicable control recall | 3/14 | 14/14 | 14/14 |
| Request-surface recall | 0/12 | 12/12 | 12/12 |
| Replay-complete area paths | 3/11 | mean 8.33/11 (7–9) | 11/11 |
| Replay reliability | 100% | 100% | 100% |
| Deepest verified path | 2 | 2 | 5 |
| Browser actions | 49 | 111.3 (110–112) | 127.3 (127–128) |
| Root reloads | 19 | 37.7 (37–38) | 30 |
| Exploration restoration actions | 6 | 23 | 0 |
| Known critical false merges | 0 | 0 | 0 |
| Sensitive-value leaks | 0 | 0 | 0 |

P0 exhausted its frontier after about 4–7 seconds; equal caps do not imply equal resource consumption. P1's extra cost is the cost of discovering and replaying surfaces that P0 never observed. P2 does not improve structural recall over P1, but it consistently converts the deepest structural-only areas into replay-complete paths. It uses about 14% more total actions than P1 because it discovers more transitions for replay, while reducing root reloads about 20% and eliminating exploration restoration actions.

The first readiness probe falsely stabilized before the late control; requiring three stable samples fixed it. The first two P2 probes were negative: 85% and 60% replay reliability. They exposed missing live-path provenance and session-context equivalence. Preserved directories `js_heavy_p1_probe`, `js_heavy_p2_probe`, and `js_heavy_p2_r1` document those failures. They are excluded from the corrected three-repeat result, not erased.

## Public independent transfer: ZAP Crawlground

The official public Crawlground repository was pinned at `ba52303a5fd43795f461a6df39da45e2fe886c6b` and run locally. Agent 1 started at `/category/dynamic-content`; global navigation exposed other categories, so the server's honest denominator is all 59 markers. Each policy received one matched 60-second/140-action/30-transition run. This was a transfer check, not a tuning loop.

| Policy | Independent markers | Replays | Root reloads | Restoration actions |
|---|---:|---:|---:|---:|
| P0 | 1/59 | 11/14 | 45 | 23 |
| P1 | 1/59 | 11/14 | 45 | 23 |
| P2 | 5/59 | 17/27; 10 failed, 3 untested | 37 | 4 |

P2 reached `details-toggle`, `template-element`, `localstorage`, `xhr-post`, and `window-open`. The final strict-budget run consumed 136/140 actions. It still missed delayed-only cases selected too late, scroll/intersection behavior, hover/focus/keyboard gestures, iframe/shadow-DOM content, and other unsupported events. Its 5/59 score is materially better than 1/59 but low absolute coverage, and its replay failures prohibit a broad robustness claim.

Compact server results are in `agent1/experiments/crawlground_score_summary.json`; per-run Graph A diagrams, metrics, and reports are in the adjacent experiment directories. Full graphs/checkpoints remain local under the repository's existing artifact-ignore policy.

## Reproduction

```bash
.venv/bin/python experiments/run_generalization_lab.py \
  --out agent1/experiments/repro-p2 --variant p2 \
  --seconds 60 --max-transitions 30 --max-browser-actions 140
```

Crawlground setup:

```bash
git clone --depth 1 https://github.com/zaproxy/crawlground.git /private/tmp/zap-crawlground
cd /private/tmp/zap-crawlground
npm ci --ignore-scripts
npm start
```

The evaluator never supplies expected paths or marker URLs to Agent 1.
