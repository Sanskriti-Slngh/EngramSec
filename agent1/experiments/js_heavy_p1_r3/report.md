# Agent 1 run agent1-20261029T000144Z

- Code revision: `1551947368901f25afa5879442c1680bbc9d511b+mapper-8e56e6cfeb1e`
- Policy: `coverage`
- Target: `http://127.0.0.1:50889/`
- Elapsed: 60.794 seconds
- Browser actions (including setup/replay): 110
- Replay-validated navigation categories: 7
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 18
- Replay navigation success: 13/13
- Replay failures / untested paths: 0/10
- Graph connections with complete evidence: 400/400
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_0a795a520c814074` — Open workflow leads to JavaScript Readiness Lab
- `feature_6b85957677df1f8a` — Load late reports leads to JavaScript Readiness Lab
- `feature_8381988dedc3fd61` — Member preferences opens /member/preferences
- `feature_8b4629bc4408a3c8` — Public alias area opens /alias-area
- `feature_b10386b9bb2eb4c4` — Open workflow leads to JavaScript Readiness Lab
- `feature_ddfe02aac6ebb137` — Overview opens /shallow/a
- `feature_def6c416df56cd51` — News opens /shallow/b

## Functional path-instance outcomes

- `workflow_e9ef816ccef16d4acb` — Enter member mode: `unresolved` (path length 1)
- `workflow_b3e4639edcc65addb5` — Refresh status: `unresolved` (path length 1)
- `workflow_ab54ca633d1fc27da9` — Open workflow: `unresolved` (path length 1)
- `workflow_b2b215d91ea7b00e02` — Load late reports: `unresolved` (path length 1)
- `workflow_9d9e058ec8ed838845` — Continue setup: `not_tested` (path length 2)
- `workflow_d66249fb59805f3aba` — Public alias area: `navigation_only` (path length 1)
- `workflow_7fc15d029d316eae28` — Load alias data: `not_tested` (path length 2)
- `workflow_ac1bbe81064689964b` — Overview: `navigation_only` (path length 1)
- `workflow_b16b179a0135dda5dd` — Member preferences: `navigation_only` (path length 2)
- `workflow_3437d09f387aaa4e1c` — Load preferences: `not_tested` (path length 3)
- `workflow_15e3a44c03eaba941b` — News: `navigation_only` (path length 1)
- `workflow_227b5937edfde9984d` — Open reports: `not_tested` (path length 2)
- `workflow_4a8d1a47299bc387b7` — JS Lab: `navigation_only` (path length 1)
- `workflow_a6a7097889951cee22` — Open workspace: `not_tested` (path length 3)
- `workflow_7e769920209a44e764` — Workspace detail: `not_tested` (path length 4)
- `workflow_cc5fe4cafd908417a6` — Enter member mode: `unresolved` (path length 2)
- `workflow_1194b31fa27b991fdf` — Enter member mode: `unresolved` (path length 2)
- `workflow_11f6d9472ff2d1643d` — Enter member mode: `not_tested` (path length 3)
- `workflow_83c056e768fa72f5af` — Refresh status: `not_tested` (path length 2)
- `workflow_8b6f2d77428d450ea1` — Refresh status: `unresolved` (path length 2)
- `workflow_e95ca37667829c85f7` — Open workflow: `not_tested` (path length 2)
- `workflow_b074954b433ad028f8` — Open workflow: `unresolved` (path length 2)
- `workflow_27504cba3293f8dbe6` — Enter member mode: `not_tested` (path length 3)

## Observed but not replay-validated

- `feature_11100edb72c51360` — Enter member mode leads to Member
- `feature_1d1a69b7211fbfce` — Continue setup leads to JavaScript Readiness Lab
- `feature_7a7a2fdb703743db` — Open reports opens /reports
- `feature_a6fdfb0309a1ff7e` — Open workspace opens /workspace
- `feature_bd73efed812d78fb` — Workspace detail opens /workspace/detail

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
