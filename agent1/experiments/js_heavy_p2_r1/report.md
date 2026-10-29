# Agent 1 run agent1-20261028T235730Z

- Code revision: `1551947368901f25afa5879442c1680bbc9d511b+mapper-fd8130253bbb`
- Policy: `coverage`
- Target: `http://127.0.0.1:65178/`
- Elapsed: 60.506 seconds
- Browser actions (including setup/replay): 129
- Replay-validated navigation categories: 3
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 20
- Replay navigation success: 15/25
- Replay failures / untested paths: 10/5
- Graph connections with complete evidence: 292/292
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_8381988dedc3fd61` — Member preferences opens /member/preferences
- `feature_8b4629bc4408a3c8` — Public alias area opens /alias-area
- `feature_def6c416df56cd51` — News opens /shallow/b

## Functional path-instance outcomes

- `workflow_c1f661966c2a2dbae0` — Enter member mode: `unresolved` (path length 1)
- `workflow_f49dbb4776b655666f` — Member preferences: `navigation_only` (path length 2)
- `workflow_e7f9d3c5b3e436000b` — Load preferences: `unresolved` (path length 3)
- `workflow_d7611f527207e370b2` — Overview: `navigation_only` (path length 3)
- `workflow_2378b05b487be63cdd` — Overview: `navigation_only` (path length 4)
- `workflow_4c63a236e1b02e244d` — News: `navigation_only` (path length 4)
- `workflow_f41f449f9d13ba1a7a` — Overview: `not_tested` (path length 5)
- `workflow_32ac7df3d3264312f1` — JS Lab: `not_tested` (path length 4)
- `workflow_2f197a31619bccc0fa` — Enter member mode: `not_tested` (path length 5)
- `workflow_40997ceab32b04bb7b` — Overview: `navigation_only` (path length 2)
- `workflow_ca121dd7aa07c1ce8d` — Refresh status: `failed` (path length 1)
- `workflow_548f08815736054c94` — Refresh status: `failed` (path length 1)
- `workflow_132ca77edb1839fc3b` — Open workflow: `failed` (path length 1)
- `workflow_baeb6a37bca83889b3` — Continue setup: `failed` (path length 2)
- `workflow_181294cc688f2e454b` — Open workspace: `failed` (path length 3)
- `workflow_16e18a068ee12440c0` — Workspace detail: `not_tested` (path length 4)
- `workflow_78bcd85f0f04c93bdd` — Overview: `not_tested` (path length 5)
- `workflow_5e98756f7d325ebce1` — Open workflow: `failed` (path length 1)
- `workflow_b25ca95384d7c4a0a0` — Enter member mode: `unresolved` (path length 2)
- `workflow_8dbc5aa79dc7aabed3` — News: `navigation_only` (path length 2)
- `workflow_6f17b36d4fba9d105d` — News: `navigation_only` (path length 3)
- `workflow_3e96f3d108feb6d15f` — JS Lab: `navigation_only` (path length 3)
- `workflow_7dd066ee67f3f60a8a` — Load late reports: `failed` (path length 1)
- `workflow_d7b03f8cd0a5a23f5b` — Open reports: `failed` (path length 2)
- `workflow_d52da2e2a56f299c1d` — Overview: `failed` (path length 3)
- `workflow_ce9b43ee953dcfc21b` — Load late reports: `failed` (path length 1)
- `workflow_007ca5a0081611294e` — Enter member mode: `unresolved` (path length 2)
- `workflow_8a733379a895886b21` — JS Lab: `navigation_only` (path length 2)
- `workflow_cbc2d26c9ecb448cae` — Public alias area: `navigation_only` (path length 1)
- `workflow_92047dfeabee24bc7a` — Load alias data: `unresolved` (path length 2)

## Observed but not replay-validated

- `feature_11100edb72c51360` — Enter member mode leads to Member
- `feature_5ce256c24795e4ad` — JS Lab opens /
- `feature_bd73efed812d78fb` — Workspace detail opens /workspace/detail

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- Restoration content signature differed, but the independently compared interaction shape remained usable for 87d8dd02ff25f3b0.
- Restoration content signature differed, but the independently compared interaction shape remained usable for f875540fdd9a5f87.
- Restoration content signature differed, but the independently compared interaction shape remained usable for 44e83c2bdc76a1b4.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
