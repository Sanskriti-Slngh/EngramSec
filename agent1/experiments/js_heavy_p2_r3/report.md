# Agent 1 run agent1-20261029T000249Z

- Code revision: `1551947368901f25afa5879442c1680bbc9d511b+mapper-8e56e6cfeb1e`
- Policy: `coverage`
- Target: `http://127.0.0.1:51447/`
- Elapsed: 60.778 seconds
- Browser actions (including setup/replay): 127
- Replay-validated navigation categories: 8
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 13
- Replay navigation success: 24/24
- Replay failures / untested paths: 0/6
- Graph connections with complete evidence: 279/279
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 1
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_0a795a520c814074` — Open workflow leads to JavaScript Readiness Lab
- `feature_1d1a69b7211fbfce` — Continue setup leads to JavaScript Readiness Lab
- `feature_6b85957677df1f8a` — Load late reports leads to JavaScript Readiness Lab
- `feature_7a7a2fdb703743db` — Open reports opens /reports
- `feature_8381988dedc3fd61` — Member preferences opens /member/preferences
- `feature_8b4629bc4408a3c8` — Public alias area opens /alias-area
- `feature_a6fdfb0309a1ff7e` — Open workspace opens /workspace
- `feature_bd73efed812d78fb` — Workspace detail opens /workspace/detail

## Functional path-instance outcomes

- `workflow_9602de9d5c48fb842b` — Enter member mode: `unresolved` (path length 1)
- `workflow_021ae2a17a050b4747` — Member preferences: `navigation_only` (path length 2)
- `workflow_1a422040ddf7b2fd21` — Load preferences: `unresolved` (path length 3)
- `workflow_1f998f304290efb4de` — Overview: `navigation_only` (path length 3)
- `workflow_7d629ce56ef6281706` — Overview: `navigation_only` (path length 4)
- `workflow_24bfbb56ad8bcd2609` — News: `navigation_only` (path length 4)
- `workflow_e564c4ac0ae3a327dc` — Overview: `navigation_only` (path length 5)
- `workflow_b3c734232aa5ac68f3` — JS Lab: `navigation_only` (path length 4)
- `workflow_b20a1a11ef2bf8e314` — Enter member mode: `not_tested` (path length 5)
- `workflow_cb9f11c209892d04e2` — Overview: `navigation_only` (path length 2)
- `workflow_001d8cf779824edb95` — Refresh status: `unresolved` (path length 1)
- `workflow_9f3a599efce1b600f4` — Open workflow: `unresolved` (path length 1)
- `workflow_fd9d8c3156c2361d6c` — Continue setup: `unresolved` (path length 2)
- `workflow_12620b2f36166b843c` — Open workspace: `navigation_only` (path length 3)
- `workflow_596927dbfff1357d8e` — Workspace detail: `navigation_only` (path length 4)
- `workflow_efcc4c7f4c7bf76e17` — Overview: `not_tested` (path length 5)
- `workflow_86f480ab1e1bd01769` — Overview: `not_tested` (path length 6)
- `workflow_0d42b13bbe4a3fa5f0` — News: `not_tested` (path length 6)
- `workflow_fd9ff22c1e149f12af` — Overview: `not_tested` (path length 7)
- `workflow_0ad5e759c660f34bc1` — JS Lab: `not_tested` (path length 6)
- `workflow_9fe5f9abe4b8c57400` — Load late reports: `unresolved` (path length 1)
- `workflow_0f1363e3bb3ad9a7ab` — Open reports: `navigation_only` (path length 2)
- `workflow_923291638781301bb6` — Overview: `navigation_only` (path length 3)
- `workflow_66e8a34f70609218ed` — Public alias area: `navigation_only` (path length 1)
- `workflow_1a352c60043cd24891` — Load alias data: `unresolved` (path length 2)
- `workflow_38b04b80528c405b09` — Overview: `navigation_only` (path length 2)
- `workflow_784df5cec6215558cd` — Overview: `navigation_only` (path length 1)
- `workflow_db84700d0d545d5e99` — News: `navigation_only` (path length 1)
- `workflow_dfa78155275a83521f` — News: `navigation_only` (path length 2)
- `workflow_57f5557fabaad491ef` — JS Lab: `navigation_only` (path length 2)

## Observed but not replay-validated

- `feature_11100edb72c51360` — Enter member mode leads to Member
- `feature_5ce256c24795e4ad` — JS Lab opens /
- `feature_ddfe02aac6ebb137` — Overview opens /shallow/a
- `feature_def6c416df56cd51` — News opens /shallow/b

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
