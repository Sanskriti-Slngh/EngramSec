# Agent 1 run agent1-20261028T145510Z

- Code revision: `fbc9af897ac31f7b8314dea426da996ea1305b0c+mapper-31f946def075`
- Policy: `grouped`
- Target: `http://127.0.0.1:51707/`
- Elapsed: 13.673 seconds
- Browser actions (including setup/replay): 25
- Replay-validated navigation categories: 0
- Verified functional workflows: 1
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 1
- Replay navigation success: 3/3
- Replay failures / untested paths: 0/0
- Graph connections with complete evidence: 436/436
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 1
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- None.

## Functional path-instance outcomes

- `workflow_448f3bf5f383a914b4` — toggle search: `unresolved` (path length 1)
- `workflow_711eaabeb64fea7179` — unnamed button: `functional_verified` (path length 2)

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
