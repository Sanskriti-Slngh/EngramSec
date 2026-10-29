# Agent 1 run agent1-20261028T235427Z

- Code revision: `1551947368901f25afa5879442c1680bbc9d511b+mapper-25c4d63b2688`
- Policy: `coverage`
- Target: `http://127.0.0.1:63694/`
- Elapsed: 60.860 seconds
- Browser actions (including setup/replay): 112
- Replay-validated navigation categories: 8
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
- `feature_ddfe02aac6ebb137` — Overview opens /shallow/a
- `feature_def6c416df56cd51` — News opens /shallow/b

## Functional path-instance outcomes

- `workflow_33bfc992cc6661e57b` — Enter member mode: `unresolved` (path length 1)
- `workflow_3018d8103ccb9194ed` — Refresh status: `unresolved` (path length 1)
- `workflow_2b583c282640a8d2c2` — Open workflow: `unresolved` (path length 1)
- `workflow_5752bfb30de1e5e93f` — Load late reports: `unresolved` (path length 1)
- `workflow_a1bbb63d89306179c4` — Continue setup: `unresolved` (path length 2)
- `workflow_41c13956489441fe5e` — Public alias area: `navigation_only` (path length 1)
- `workflow_6e478b868cc74dcd65` — Load alias data: `not_tested` (path length 2)
- `workflow_b8b1a3c89913d561a3` — Overview: `navigation_only` (path length 1)
- `workflow_7e694a5302cf8b1e93` — Member preferences: `navigation_only` (path length 2)
- `workflow_1b4533cfdd8c546570` — Load preferences: `not_tested` (path length 3)
- `workflow_61ace0b1413ed8abf0` — News: `navigation_only` (path length 1)
- `workflow_55a7ecb213a3ed0779` — Open reports: `navigation_only` (path length 2)
- `workflow_744499838776dff9fa` — JS Lab: `navigation_only` (path length 1)
- `workflow_cd24b6befabfa86c43` — Open workspace: `not_tested` (path length 3)
- `workflow_9e4eda8234ff636ae8` — Workspace detail: `not_tested` (path length 4)
- `workflow_7dd017a987d4b1053f` — Enter member mode: `unresolved` (path length 2)
- `workflow_7a095932ec5ead193e` — Enter member mode: `not_tested` (path length 2)
- `workflow_223468c96f12722a52` — Enter member mode: `not_tested` (path length 3)
- `workflow_8270d5ba4f2179d9f2` — Refresh status: `not_tested` (path length 2)
- `workflow_813ec236e3a0a7f01c` — Refresh status: `unresolved` (path length 2)
- `workflow_b65350952d14fd3fcf` — Open workflow: `unresolved` (path length 2)
- `workflow_f8009e50baed0bc96c` — Open workflow: `not_tested` (path length 2)
- `workflow_4e3069d61264febf81` — Enter member mode: `not_tested` (path length 3)

## Observed but not replay-validated

- `feature_11100edb72c51360` — Enter member mode leads to Member
- `feature_a6fdfb0309a1ff7e` — Open workspace opens /workspace
- `feature_b10386b9bb2eb4c4` — Open workflow leads to JavaScript Readiness Lab
- `feature_bd73efed812d78fb` — Workspace detail opens /workspace/detail

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
