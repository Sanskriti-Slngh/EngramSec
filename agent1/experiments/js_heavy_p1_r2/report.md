# Agent 1 run agent1-20261029T000037Z

- Code revision: `1551947368901f25afa5879442c1680bbc9d511b+mapper-8e56e6cfeb1e`
- Policy: `coverage`
- Target: `http://127.0.0.1:50322/`
- Elapsed: 61.670 seconds
- Browser actions (including setup/replay): 112
- Replay-validated navigation categories: 9
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 17
- Replay navigation success: 14/14
- Replay failures / untested paths: 0/9
- Graph connections with complete evidence: 401/401
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_0a795a520c814074` — Open workflow leads to JavaScript Readiness Lab
- `feature_1d1a69b7211fbfce` — Continue setup leads to JavaScript Readiness Lab
- `feature_6b85957677df1f8a` — Load late reports leads to JavaScript Readiness Lab
- `feature_7a7a2fdb703743db` — Open reports opens /reports
- `feature_8381988dedc3fd61` — Member preferences opens /member/preferences
- `feature_8b4629bc4408a3c8` — Public alias area opens /alias-area
- `feature_b10386b9bb2eb4c4` — Open workflow leads to JavaScript Readiness Lab
- `feature_ddfe02aac6ebb137` — Overview opens /shallow/a
- `feature_def6c416df56cd51` — News opens /shallow/b

## Functional path-instance outcomes

- `workflow_8abee2a85936eca1ed` — Enter member mode: `unresolved` (path length 1)
- `workflow_f097ab316b771202d1` — Refresh status: `unresolved` (path length 1)
- `workflow_bf24d565f45322cbc9` — Open workflow: `unresolved` (path length 1)
- `workflow_b41ea5aa02ad30c27a` — Load late reports: `unresolved` (path length 1)
- `workflow_313f43501006f96dca` — Continue setup: `unresolved` (path length 2)
- `workflow_0493b97ee5b54f4ddd` — Public alias area: `navigation_only` (path length 1)
- `workflow_cf48f375926b26706b` — Load alias data: `not_tested` (path length 2)
- `workflow_8319c1124815a54e1b` — Overview: `navigation_only` (path length 1)
- `workflow_4d83932e0be8abb245` — Member preferences: `navigation_only` (path length 2)
- `workflow_7df2b41d087ff4e429` — Load preferences: `not_tested` (path length 3)
- `workflow_3efdaee8c4dbe3e110` — News: `navigation_only` (path length 1)
- `workflow_68b17fb1ce7a66410d` — Open reports: `navigation_only` (path length 2)
- `workflow_c2728e2a0b8308a288` — JS Lab: `navigation_only` (path length 1)
- `workflow_2a56b7670a19fd0442` — Open workspace: `not_tested` (path length 3)
- `workflow_3c953750e15c22dab8` — Workspace detail: `not_tested` (path length 4)
- `workflow_fce1f0bbdce8561592` — Enter member mode: `not_tested` (path length 2)
- `workflow_62e1aa381ad7a2f802` — Enter member mode: `unresolved` (path length 2)
- `workflow_6d8617bbfb37454ff5` — Enter member mode: `not_tested` (path length 3)
- `workflow_aa787d088e16de290c` — Refresh status: `unresolved` (path length 2)
- `workflow_22775efa408273d95f` — Refresh status: `not_tested` (path length 2)
- `workflow_6d41110148bd4a0378` — Open workflow: `not_tested` (path length 2)
- `workflow_e8a5937aabb34d24a2` — Open workflow: `unresolved` (path length 2)
- `workflow_fc25c21188085b9b19` — Enter member mode: `not_tested` (path length 3)

## Observed but not replay-validated

- `feature_11100edb72c51360` — Enter member mode leads to Member
- `feature_a6fdfb0309a1ff7e` — Open workspace opens /workspace
- `feature_bd73efed812d78fb` — Workspace detail opens /workspace/detail

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
