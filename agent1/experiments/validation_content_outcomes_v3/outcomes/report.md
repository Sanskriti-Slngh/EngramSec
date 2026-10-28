# Agent 1 run agent1-20261028T133450Z

- Code revision: `778bbbda008081c489afdaee836c6397c4cff93a+mapper-c159484a7625`
- Policy: `grouped`
- Target: `http://127.0.0.1:49653/outcomes`
- Elapsed: 3.883 seconds
- Browser actions (including setup/replay): 9
- Replay-validated navigation categories: 2
- Verified functional workflows: 1
- Reproduced validation failures: 1
- Functional outcomes unresolved/untested/failed: 0
- Replay navigation success: 2/2
- Replay failures / untested paths: 0/0
- Graph connections with complete evidence: 21/21
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_09e4b3368f3e49cc` — C verify success leads to Outcome examples
- `feature_60f20b42163cf955` — B show validation failure leads to Outcome examples

## Functional path-instance outcomes

- `workflow_df3e8e5e87f8e9122b` — C verify success: `functional_verified` (path length 1)
- `workflow_c514a362c0b7eedf18` — B show validation failure: `validation_failure` (path length 1)

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
