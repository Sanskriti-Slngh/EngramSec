# Agent 1 run agent1-20261028T133428Z

- Code revision: `778bbbda008081c489afdaee836c6397c4cff93a+mapper-c159484a7625`
- Policy: `grouped`
- Target: `http://127.0.0.1:49653/search`
- Elapsed: 3.101 seconds
- Browser actions (including setup/replay): 7
- Replay-validated navigation categories: 0
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 1
- Replay navigation success: 0/1
- Replay failures / untested paths: 1/0
- Graph connections with complete evidence: 6/6
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- None.

## Functional path-instance outcomes

- `workflow_32ea59ee7870aaa4c8` — Search: `failed` (path length 1)

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
