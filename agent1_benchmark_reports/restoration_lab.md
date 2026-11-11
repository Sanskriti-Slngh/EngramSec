# restoration_lab

**Track A · reference: none (contract fixture) · regime: comprehensive**

## Input — what the app is
A **restoration-contract** fixture: states that are hard to re-reach, designed to stress the restoration
ladder and the "never replay a write" contract.

## What Agent 1 produced
Graph A: **12 states, 78 action-evidences, 63 workflows, 30 features, 1211 edges, 933 advertised-unexecuted.**
Capabilities observed: **19** (14 reproduced, 5 observed), unidentified 11. Efficiency: 335 actions, 164 s,
**117 restoration, 101 root reloads, 46 redundant, 15 failed actions**; replays 22/22 validated; 2 state-
changing; **19 dangerous controls skipped**.

## Accuracy
No reference. The meaningful readings: **22/22 replays validated** and **19 dangerous controls skipped with
0 destructive fired** — the restoration contract and safety hold even under a fixture built to break them.
The **15 failed actions** are the highest among Track-A fixtures and show where restoration genuinely could
not re-reach a state (the ladder failed closed, i.e. safely).

## Verdict
**Restoration/safety contract holds under stress.** Failures are safe (fail-closed), replays validate.
This fixture is a safety/robustness check rather than a coverage benchmark.
