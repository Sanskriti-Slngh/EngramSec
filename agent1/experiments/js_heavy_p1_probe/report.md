# Agent 1 run agent1-20261028T235400Z

- Code revision: `1551947368901f25afa5879442c1680bbc9d511b+mapper-3469904df3c1`
- Policy: `coverage`
- Target: `http://127.0.0.1:63499/`
- Elapsed: 8.675 seconds
- Browser actions (including setup/replay): 8
- Replay-validated navigation categories: 0
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 0
- Replay navigation success: 0/0
- Replay failures / untested paths: 0/0
- Graph connections with complete evidence: 78/78
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- None.

## Functional path-instance outcomes

- None.

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- `tr_140c702890e411f23a11` — Enter member mode: RuntimeError: saved return path restored 953e7402e8bf6a1d, expected f4ce5d930a26a49d
- `tr_754ae76b8be1c94eb152` — Refresh status: RuntimeError: saved return path restored 953e7402e8bf6a1d, expected f4ce5d930a26a49d
- `tr_a497d59b29ab2d92a91d` — Open workflow: RuntimeError: saved return path restored 953e7402e8bf6a1d, expected f4ce5d930a26a49d
- `tr_ca96d2e68d1b4ef0d048` — Public alias area: RuntimeError: saved return path restored 953e7402e8bf6a1d, expected f4ce5d930a26a49d
- `tr_05ddbf69094e696a902a` — Overview: RuntimeError: saved return path restored 953e7402e8bf6a1d, expected f4ce5d930a26a49d
- `tr_43951274622e0e9addf2` — News: RuntimeError: saved return path restored 953e7402e8bf6a1d, expected f4ce5d930a26a49d
- `tr_54e8400f6f4e75390b63` — JS Lab: RuntimeError: saved return path restored 953e7402e8bf6a1d, expected f4ce5d930a26a49d

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
