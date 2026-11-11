# phase2_lab

**Track A · reference: server-state diagnostic (no recall number) · regime: comprehensive**

## Input — what the app is
A **prerequisite-workflow** fixture with a **WebSocket** diagnostic: capabilities are gated behind
required earlier steps (you must do A before B is reachable), used to test that Agent 1 follows chains.

## What Agent 1 produced
Graph A: **23 states, 66 action-evidences, 66 workflows, 35 features, 1287 edges, 1000 advertised-unexecuted,
3 record instances.** Capabilities observed: **16** (13 reproduced, 3 observed), unidentified 7. Efficiency:
379 actions, 180.7 s (full budget), 132 restoration, 98 root reloads, 38 redundant; replays 31/31 validated;
1 state-changing request.

## Accuracy
No annotated recall (reference is server-state only). The signal here is **reproducibility and
prerequisite-following**: 66 workflows with **31/31 replays validated** means the prerequisite chains it
claims genuinely re-run. It consumed the full 180 s with heavy restoration (132 actions) — a restoration-
bound run, consistent with the Stage-2 diagnosis.

## Verdict
**Reproducible and chain-aware.** No accuracy % is claimable, but the evidence is clean (no replay
failures, prerequisite workflows reproduced). Restoration cost is the efficiency limiter.
