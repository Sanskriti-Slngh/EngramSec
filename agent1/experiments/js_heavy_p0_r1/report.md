# Agent 1 run agent1-20261028T235109Z

- Code revision: `1551947368901f25afa5879442c1680bbc9d511b+mapper-4401416db992`
- Policy: `coverage`
- Target: `http://127.0.0.1:62255/`
- Elapsed: 6.937 seconds
- Browser actions (including setup/replay): 49
- Replay-validated navigation categories: 3
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 0
- Replay navigation success: 9/9
- Replay failures / untested paths: 0/0
- Graph connections with complete evidence: 98/98
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_5ce256c24795e4ad` — JS Lab opens /
- `feature_ddfe02aac6ebb137` — Overview opens /shallow/a
- `feature_def6c416df56cd51` — News opens /shallow/b

## Functional path-instance outcomes

- `workflow_f81a87ea80556a30dc` — Overview: `navigation_only` (path length 1)
- `workflow_09f5c922baf4bbfaf2` — News: `navigation_only` (path length 1)
- `workflow_766005c7a3826119d6` — JS Lab: `navigation_only` (path length 1)
- `workflow_8f80e128faed224744` — Overview: `navigation_only` (path length 2)
- `workflow_cff0a4076133c07ed2` — Overview: `navigation_only` (path length 2)
- `workflow_6c462b4542643c36ad` — News: `navigation_only` (path length 2)
- `workflow_408e1156b4851c7bf0` — News: `navigation_only` (path length 2)
- `workflow_3798931b81d20e781f` — JS Lab: `navigation_only` (path length 2)
- `workflow_1c62e1765931ad534d` — JS Lab: `navigation_only` (path length 2)

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
