# Agent 1 run agent1-20261028T133434Z

- Code revision: `778bbbda008081c489afdaee836c6397c4cff93a+mapper-c159484a7625`
- Policy: `grouped`
- Target: `http://127.0.0.1:49653/multi`
- Elapsed: 11.660 seconds
- Browser actions (including setup/replay): 29
- Replay-validated navigation categories: 2
- Verified functional workflows: 1
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 3
- Replay navigation success: 4/4
- Replay failures / untested paths: 0/0
- Graph connections with complete evidence: 26/26
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_701879651405ba2e` — Prepare workspace leads to Workspace setup
- `feature_ddc313664cc69a0b` — Complete setup leads to Workspace setup

## Functional path-instance outcomes

- `workflow_1ae176c104f1045463` — Prepare workspace: `unresolved` (path length 1)
- `workflow_25646d157175e4aeb3` — Complete setup: `functional_verified` (path length 2)
- `workflow_85fc11f49904de79a5` — Prepare workspace: `unresolved` (path length 2)
- `workflow_389c803aad86784125` — Prepare workspace: `unresolved` (path length 3)

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
