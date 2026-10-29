# Agent 1 run agent1-20261028T235916Z

- Code revision: `1551947368901f25afa5879442c1680bbc9d511b+mapper-8e56e6cfeb1e`
- Policy: `coverage`
- Target: `http://127.0.0.1:49640/`
- Elapsed: 61.221 seconds
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

- `workflow_bb2d54840075122f42` — Enter member mode: `unresolved` (path length 1)
- `workflow_656846c99d306f4388` — Member preferences: `navigation_only` (path length 2)
- `workflow_452e833b5603009bb6` — Load preferences: `unresolved` (path length 3)
- `workflow_90a125a1acb2a77ff9` — Overview: `navigation_only` (path length 3)
- `workflow_3c51e6af8dbf080f66` — Overview: `navigation_only` (path length 4)
- `workflow_658199ceb6a1714087` — News: `navigation_only` (path length 4)
- `workflow_4ca0c741d68e63ea43` — Overview: `navigation_only` (path length 5)
- `workflow_1df2b1588a1ec1a508` — JS Lab: `navigation_only` (path length 4)
- `workflow_45784bd90a2c104a67` — Enter member mode: `not_tested` (path length 5)
- `workflow_cc48c36f26c0055ab6` — Overview: `navigation_only` (path length 2)
- `workflow_d8330d01f1a83e1a5c` — Refresh status: `unresolved` (path length 1)
- `workflow_e862b53d19f2b98593` — Open workflow: `unresolved` (path length 1)
- `workflow_3af30424ef3d1a1557` — Continue setup: `unresolved` (path length 2)
- `workflow_2489c559c21d4a7930` — Open workspace: `navigation_only` (path length 3)
- `workflow_da10b766fe724f8e92` — Workspace detail: `navigation_only` (path length 4)
- `workflow_c99170ba645960f722` — Overview: `not_tested` (path length 5)
- `workflow_2005e7acde88918801` — Overview: `not_tested` (path length 6)
- `workflow_706aff15dfbbe23d60` — News: `not_tested` (path length 6)
- `workflow_bf4198cdf1dabb42f9` — Overview: `not_tested` (path length 7)
- `workflow_7bbef2281790ebf6d3` — JS Lab: `not_tested` (path length 6)
- `workflow_9e1665f6d9b23d2731` — Load late reports: `unresolved` (path length 1)
- `workflow_4dc24fe9e475993acb` — Open reports: `navigation_only` (path length 2)
- `workflow_25954006e6c11ef73d` — Overview: `navigation_only` (path length 3)
- `workflow_3ff52c72f00e7332e7` — Public alias area: `navigation_only` (path length 1)
- `workflow_8e2faa6b8d263d33fe` — Load alias data: `unresolved` (path length 2)
- `workflow_48612ce4c2b3eab752` — Overview: `navigation_only` (path length 2)
- `workflow_2b874a924777e37f5a` — Overview: `navigation_only` (path length 1)
- `workflow_343bf5e16965b0b683` — News: `navigation_only` (path length 1)
- `workflow_64460d8b9f72e5c5ef` — News: `navigation_only` (path length 2)
- `workflow_1504ac55276078fb96` — JS Lab: `navigation_only` (path length 2)

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
