# Agent 1 reachable-surface coverage milestone

Date: 2026-10-28

Frozen development base: `6082c6d`

External API/model cost: **$0.00**; model calls: **0**

## What was proved

Agent 1 now finds generic semantic controls (`role=tab`, `<summary>`, enabled keyboard/data-action launchers), prioritizes globally novel observed control shapes, records request parameter *names* and body encoding without values, and separates browser contexts using cookie/storage marker names without values. These changes remain in the existing observation, frontier, checkpoint, replay, and Graph A pipeline.

An evaluator maintained separately from the mapper scored frozen Graph A files against independent application ground truth. Blocked and outside-origin surfaces were excluded from ordinary recall denominators and remained visible as separate categories.

## Development evaluation and ablations

All Coverage Lab runs used 30 transitions, 140 configured browser actions, one worker, the same reset/start conditions, and the same ground truth. The action counter can overshoot by the final multi-action path; observed totals are reported.

| Frozen configuration | Areas | Controls | Requests | Replayed area paths | Replay | Surfaces/action |
|---|---:|---:|---:|---:|---:|---:|
| `6082c6d` grouped baseline | 6/10 | 11/17 | 6/10 | 5/10 | 19/19 | 0.162 |
| Iteration 1: semantic controls, grouped | 6/10 | 15/17 | 4/10 | 6/10 | 21/21 | 0.175 |
| Iteration 2: + coverage frontier | 10/10 | 17/17 | 9/10 | 7/10 | 17/17 | 0.257 |
| Iteration 3 clean-revision repeat: + request/context evidence | 10/10 | 17/17 | 10/10 | 8/10 | 17/17 | 0.264 |

Iteration 1 recovered four invisible control classes but displaced request/deep-branch work under the fixed budget; its request regression is preserved rather than hidden. The coverage policy was the material exploration improvement: versus the original baseline, covered surfaces per action increased 62%. Iteration 3 did not claim new navigation; it closed the independently measured POST-parameter and member-context representation gaps.

Known record instances remained distinct (2/2), evaluator-known critical false merges were zero, graph connections missing referential evidence were zero, and all attempted independent navigation replays succeeded. The clean-revision repeat replayed 8/10 applicable area paths before the action cap, so structural discovery is still stronger than complete path validation.

Actual browser-run time for the four original development configurations was 45.1 seconds (configured ceilings totaled four minutes). A clean-revision Graph repeat took another 10.9 seconds. No exploit, paid provider, or benchmark target was used.

Focused regressions passed after every iteration, and the final full suite passed **36/36** in 38.13 seconds.

## Held-out transfer

After freezing the mapper, a separate local Northstar Shop application was evaluated without tuning:

| Policy | Areas | Controls | Requests | Replayed area paths | Replay | Surfaces/action |
|---|---:|---:|---:|---:|---:|---:|
| Grouped | 7/8 | 11/11 | 7/8 | 6/8 | 21/21 | 0.179 |
| Coverage, clean-revision repeat | 8/8 | 11/11 | 8/8 | 5/8 | 19/19 | 0.191 |

The coverage policy transferred, improving area and request recall to 100% and efficiency by 7.2%. This is evidence on one held-out controlled application, not proof of completeness on arbitrary applications. The first coverage run replayed 6/8 labeled area paths and the clean-revision repeat replayed 5/8, despite 19/19 attempted replays in both. This variance is preserved: transition-ID tie ordering and shallow-first replay selection change which paths remain untested at the cap. Deep-path replay scheduling is the measured bottleneck.

## Inspectable evidence

- Final development Graph A: `agent1/experiments/coverage_lab_iteration3_evidence/graph_a.json`
- Final held-out Graph A: `agent1/experiments/heldout_shop_coverage/graph_a.json`
- Compact evaluator results: each experiment directory's `coverage_evaluation.json`
- Readable graph: each directory's `graph_a.mmd`
- Raw local evidence/checkpoint: retained in the same directories and ignored where credential/browser-state risk or duplication warrants it

The Graph A action nodes attach method, sanitized URL, status, resource type, parameter-name set, encoding, action path, and result observation. State nodes include reversible raw observation membership, return-path length, configured context, and marker-name-only browser context. Advertised but unexecuted controls, blocked controls, failed actions, and untested paths remain visible. Evaluator-only `missed` labels are deliberately not fed into Graph A or the mapper.

Both final Graph A files record mapper revision `3012ce6d...+mapper-1cc5c02a0a12`; the final amended checkpoint changes reports/artifacts only, not mapper code.

## Reproduction

```bash
.venv/bin/python experiments/run_coverage_lab.py \
  --out agent1/experiments/coverage_lab_reproduction \
  --policy coverage --seconds 60 \
  --max-transitions 30 --max-browser-actions 140
```

Held-out comparison:

```bash
.venv/bin/python experiments/run_heldout_shop.py \
  --out agent1/experiments/heldout_shop_reproduction --policy coverage
```

## Benchmark isolation and protocol

No WebExploitBench evaluation was run. Its gated evaluation-only terms preclude using data, metadata, outputs, traces, or derived artifacts to improve Agent 1. Existing SiyuCMS results are development history, not held-out evidence.

For a later authorized evaluation: freeze the commit and configuration first; let CAGE discover/launch targets through its normal adapter; provide Agent 1 only the authorized target URL at l0 (no challenge metadata/hints); store benchmark outputs in a segregated evaluation directory; report only terms-permitted aggregate coverage/replay and CAGE scores; do not inspect per-vulnerability answers, `Location`, verifier logic, or feed misses/results back into development.

## Limitations and next question

- Replays are shortest-path ordered, so shallow duplicates consume the replay budget before some deep paths.
- Novelty is control-shape based; it does not yet use component- or request-novelty feedback during exploration.
- Cookie/storage names distinguish observed contexts but do not prove authorization semantics.
- Whole-page content identity remains conservative; full fragment abstraction was not justified by this experiment.
- Request structures record top-level JSON/form/multipart names, not nested schemas or WebSocket messages.
- The evaluator corpus is controlled and finite; 100% on it is not a completeness claim.

The single highest-value next experiment is a replay-aware frontier/archive policy that reserves validation budget by unique deep prerequisite path and charges actual restoration actions, measured on a larger independently authored app with overlays, hover menus, scrolling, and unstable session state.
