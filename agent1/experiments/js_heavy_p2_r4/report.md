# Agent 1 run agent1-20261029T000357Z

- Code revision: `1551947368901f25afa5879442c1680bbc9d511b+mapper-8e56e6cfeb1e`
- Policy: `coverage`
- Target: `http://127.0.0.1:52046/`
- Elapsed: 61.124 seconds
- Browser actions (including setup/replay): 128
- Replay-validated navigation categories: 9
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 14
- Replay navigation success: 24/24
- Replay failures / untested paths: 0/6
- Graph connections with complete evidence: 279/279
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 1
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_0a795a520c814074` — Open workflow leads to JavaScript Readiness Lab
- `feature_11100edb72c51360` — Enter member mode leads to Member
- `feature_1d1a69b7211fbfce` — Continue setup leads to JavaScript Readiness Lab
- `feature_6b85957677df1f8a` — Load late reports leads to JavaScript Readiness Lab
- `feature_7a7a2fdb703743db` — Open reports opens /reports
- `feature_8381988dedc3fd61` — Member preferences opens /member/preferences
- `feature_8b4629bc4408a3c8` — Public alias area opens /alias-area
- `feature_a6fdfb0309a1ff7e` — Open workspace opens /workspace
- `feature_bd73efed812d78fb` — Workspace detail opens /workspace/detail

## Functional path-instance outcomes

- `workflow_2def84b468e203275a` — Enter member mode: `unresolved` (path length 1)
- `workflow_ccf8afea39909cb8b7` — Member preferences: `navigation_only` (path length 2)
- `workflow_1b0da9e399addee8c7` — Load preferences: `unresolved` (path length 3)
- `workflow_59d3e1d56f56aa03b4` — Overview: `navigation_only` (path length 3)
- `workflow_57695a85450c40c8a6` — Overview: `navigation_only` (path length 4)
- `workflow_d7416f5e345c0d2154` — News: `navigation_only` (path length 4)
- `workflow_6876fc5383347fda07` — Overview: `not_tested` (path length 5)
- `workflow_661573475b7a89c97f` — JS Lab: `navigation_only` (path length 4)
- `workflow_5c59c9a9b01e697ae4` — Enter member mode: `unresolved` (path length 5)
- `workflow_ac3f0f7573be16afc7` — Overview: `navigation_only` (path length 2)
- `workflow_0cee536b660536de9c` — Refresh status: `unresolved` (path length 1)
- `workflow_25eb6024c1762779e9` — Open workflow: `unresolved` (path length 1)
- `workflow_6d63f47b231f4e551f` — Continue setup: `unresolved` (path length 2)
- `workflow_f2a9b6cd06a4a38d18` — Open workspace: `navigation_only` (path length 3)
- `workflow_ef53a1d54d33e82bfb` — Workspace detail: `navigation_only` (path length 4)
- `workflow_28b8ff6a5d55190f56` — Overview: `not_tested` (path length 5)
- `workflow_38fd1a153114de195d` — Overview: `not_tested` (path length 6)
- `workflow_8d7cc74f0be699f400` — News: `not_tested` (path length 6)
- `workflow_c0a8edd9449b98acf6` — Overview: `not_tested` (path length 7)
- `workflow_2a919335c25503fb2e` — JS Lab: `not_tested` (path length 6)
- `workflow_0932d79fb3894ac5bc` — Load late reports: `unresolved` (path length 1)
- `workflow_959085f7b974e627a5` — Open reports: `navigation_only` (path length 2)
- `workflow_f331ef497a53dd4db2` — Overview: `navigation_only` (path length 3)
- `workflow_ad129b5295b265171b` — Public alias area: `navigation_only` (path length 1)
- `workflow_4dca5aaf8e6f8914fe` — Load alias data: `unresolved` (path length 2)
- `workflow_60fed1d615749ce4d3` — Overview: `navigation_only` (path length 2)
- `workflow_17e402a6cc0c782bfe` — Overview: `navigation_only` (path length 1)
- `workflow_0e64d54623d497454c` — News: `navigation_only` (path length 1)
- `workflow_1fc350dc9cb5dca420` — News: `navigation_only` (path length 2)
- `workflow_50e74f40bcd1077c7d` — JS Lab: `navigation_only` (path length 2)

## Observed but not replay-validated

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
