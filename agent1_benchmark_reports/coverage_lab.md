# coverage_lab

**Track A · reference: author surface truth (no recall number) · regime: comprehensive**

## Input — what the app is
A **multi-area server-rendered site** (several distinct functional areas) used to test broad area coverage
and restoration behavior.

## What Agent 1 produced
Graph A: **23 states, 74 action-evidences, 74 workflows, 28 features, 1974 edges, 1681 advertised-unexecuted,
2 record instances.** Capabilities observed: **16** (15 reproduced, 1 observed), unidentified 7. Efficiency:
373 actions, 182 s (full budget), **113 restoration actions, 109 root reloads, 47 redundant**, caps/min 5.3,
caps/100act 4.3; replays **34/34 validated**; **0 state-changing**.

## Accuracy
No recall % (surface reference). Reproducibility is perfect (34/34). The notable number is cost:
**~113 restoration + 109 root reloads of 373 actions (~60%)** — this fixture is the clearest illustration
of the restoration bottleneck Stage 2 targets, and its low caps/min (5.3) reflects that, not a reasoning
gap.

## Verdict
**Broad, reproducible area coverage; efficiency-bound by restoration.** Exactly the profile the eager-
expansion saver is designed to improve on GET-heavy multi-area sites.
