# Resource crawler ablations

## Setup and interpretation

One worker, identical local application reset/start conditions, no models, no API calls, 180 seconds for Crawl Maze and 60 seconds for the JS lab. The Crawl Maze primary endpoint began at `/`. Its expected URL list was retrieved through the independent public scoring interface only after runs, using categories linked from the observed root. A final server-log intersection independently confirmed the combined-shallow score. The mapper never imported expected results. Browser-fetched URLs, direct spider fetches, references, UI transitions, and independently scored marker paths are separate measurements.

### Crawl Maze, 180-second caps

| Policy | Expected paths hit | Transitions | Replay | Actions | Root reloads | Passive wait | Interactive wait |
|---|---:|---:|---:|---:|---:|---:|---:|
| P0 legacy settings | 3/91 | 36 | 12/12 | 101 | 30 | 154.6 s | 15.1 s |
| Spider only | 8/91 (7 spider + 3 browser, overlap) | 36 | 12/12 | 101 | 30 | 154.6 s | 15.1 s |
| Readiness only, repeat 1 | 11/91 | 85 | 32/32 | 285 | 71 | 80.9 s | 60.3 s |
| Readiness only, repeat 2 | 11/91 | 85 | 32/32 | 285 | — | — | — |
| Readiness only, repeat 3 | 11/91 | 85 | 31/31 | 281 | — | — | — |
| Replay diversity only | 3/91 | 36 | 11/11 | 102 | — | — | — |
| Combined diverse | 16/91 Graph union | 85 | 29/30 | 278 | — | — | — |
| Combined shallow final | **16/91 server-log verified** | **85** | **32/32** | **285** | **71** | **81.0 s** | **60.3 s** |

The legacy reading uses settings replicated in current code rather than a clean immutable source archive. A separate exact `decc0a2` archive re-run reached 2/91 and the older saved report said 4/91. This variation is retained; comparison to the final result is directional rather than a precise paired causal estimate. The current P0 run reached 3/91.

The final 16 expected paths break down: HTML 10/57, JS 3/27, headers 3/4, CSS 0/1, misc 0/2. References: 22/91. Spider direct fetch: 8/91. Browser fetch: 11/91. Their union: 16/91. Only one of these was associated with a UI-state route match. Final raw graph had 162 distinct typed references, 100 successful spider fetches, 392/392 browser events recorded, and 2,198/2,198 evidence-bearing connections. Replay left 53 paths untested.

### Controlled JS-heavy lab, 60-second caps

The independent evaluator ground truth had 11 areas, 14 controls, and 12 request structures. All variants found 9 areas, 12 controls, and 8 request structures. Replay results were P0 8/8, spider 7/7, readiness 10/10, replay-diverse 7/7, combined 9/9. Deepest verified path was 2, 1, 2, 3, and 4 respectively. The interaction testbed shows readiness/depth improvement but no area/control/request recall gain. This is evidence against claiming a universal coverage win from these changes.

### Transfer repeat

The separate shop evaluation scored 8/8 applicable areas, 11/11 controls, 8/8 request structures, 8/8 paths, two distinct record instances, and 18/18 replay attempts. It is not a fresh unseen holdout because the application had appeared in prior development. One unavailable admin area was excluded from the eligible denominator.

## Ablation decisions

1. **Retain fast resource-aware readiness.** Three Crawl Maze repetitions consistently yielded 11 expected marker hits, versus 3 in current P0, and more than doubled observed transitions/replay attempts within the same wall budget. It changes the time allocation rather than adding product-specific behavior.
2. **Retain typed resource discovery.** Spider-only reached seven expected URLs absent from the browser's three; combined reached 16 in the union. It is complementary, but does not itself prove navigation or UI reachability.
3. **Keep shallow replay as default.** The diversity scheduler did not improve score or reliability in this test; the optional policy remains available for further development experiments.
4. **Do not claim overall coverage solved.** The combined run reached 17.6% of Crawl Maze's marker URLs and the controlled lab's recall stayed flat. Dynamic/computed references, deeper script behavior, and exploration cost are unresolved.

## Cost

No paid providers or models were used. External API cost was $0. The bounded browser experiments consumed approximately 34.7 minutes cumulatively; no further application crawls were run after the final transfer evaluation. Test suite runtime is reported separately in the completion note.
