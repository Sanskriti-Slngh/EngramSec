# Agent 1 run agent1-20261028T235136Z

- Code revision: `1551947368901f25afa5879442c1680bbc9d511b+mapper-971fd21aead9`
- Policy: `coverage`
- Target: `http://127.0.0.1:62519/`
- Elapsed: 3.919 seconds
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

- `workflow_e8684d2d3646242511` — Overview: `navigation_only` (path length 1)
- `workflow_8c4f288d13e90a7a54` — News: `navigation_only` (path length 1)
- `workflow_86024ca887c5f53a26` — JS Lab: `navigation_only` (path length 1)
- `workflow_b6c34b8575b2dca918` — Overview: `navigation_only` (path length 2)
- `workflow_3e8ef272d2b9e8d431` — Overview: `navigation_only` (path length 2)
- `workflow_180352950553b9da2e` — News: `navigation_only` (path length 2)
- `workflow_80533478b24a62b1f0` — News: `navigation_only` (path length 2)
- `workflow_e212429c7922569c86` — JS Lab: `navigation_only` (path length 2)
- `workflow_c92a6fb51374984549` — JS Lab: `navigation_only` (path length 2)

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
