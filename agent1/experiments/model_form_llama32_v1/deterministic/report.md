# Agent 1 run agent1-20261028T132620Z

- Code revision: `778bbbda008081c489afdaee836c6397c4cff93a+mapper-b084653012f4`
- Policy: `grouped`
- Target: `http://127.0.0.1:61648/model-form`
- Elapsed: 3.108 seconds
- Browser actions (including setup/replay): 7
- Replay-validated navigation categories: 1
- Verified functional workflows: 0
- Reproduced validation failures: 1
- Functional outcomes unresolved/untested/failed: 0
- Replay navigation success: 1/1
- Replay failures / untested paths: 0/0
- Graph connections with complete evidence: 6/6
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_a6775ffd321523f4` — Activate demo leads to Demo access

## Functional path-instance outcomes

- `workflow_d887d0cd3b7b689079` — Activate demo: `validation_failure` (path length 1)

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
