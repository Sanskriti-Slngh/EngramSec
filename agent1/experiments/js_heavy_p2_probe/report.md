# Agent 1 run agent1-20261028T235547Z

- Code revision: `1551947368901f25afa5879442c1680bbc9d511b+mapper-25c4d63b2688`
- Policy: `coverage`
- Target: `http://127.0.0.1:64341/`
- Elapsed: 60.705 seconds
- Browser actions (including setup/replay): 142
- Replay-validated navigation categories: 3
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 19
- Replay navigation success: 17/20
- Replay failures / untested paths: 3/10
- Graph connections with complete evidence: 287/287
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_8381988dedc3fd61` — Member preferences opens /member/preferences
- `feature_8b4629bc4408a3c8` — Public alias area opens /alias-area
- `feature_def6c416df56cd51` — News opens /shallow/b

## Functional path-instance outcomes

- `workflow_640d52bcd56f1cf259` — Enter member mode: `unresolved` (path length 1)
- `workflow_273c125e1df1b2638b` — Member preferences: `navigation_only` (path length 2)
- `workflow_f90c82e63babab5217` — Load preferences: `unresolved` (path length 3)
- `workflow_d65ba714d7ced471e5` — Overview: `navigation_only` (path length 3)
- `workflow_c88d060a0507d6e525` — Overview: `navigation_only` (path length 4)
- `workflow_0b97b6bc6025a56356` — News: `navigation_only` (path length 4)
- `workflow_99e037795874b93968` — Overview: `navigation_only` (path length 5)
- `workflow_afe7066ca490dd926d` — JS Lab: `navigation_only` (path length 4)
- `workflow_e7d4b076e5e1fb3379` — Enter member mode: `unresolved` (path length 5)
- `workflow_db31040079eef87357` — Overview: `navigation_only` (path length 2)
- `workflow_f74c84960ccc0c1bb6` — Refresh status: `failed` (path length 1)
- `workflow_e8398aaa5d163481e1` — Refresh status: `unresolved` (path length 5)
- `workflow_e5d961cc00433cd064` — Open workflow: `unresolved` (path length 5)
- `workflow_d5ccffb6930dc63134` — Continue setup: `not_tested` (path length 6)
- `workflow_5341e9826684be5161` — Open workspace: `not_tested` (path length 7)
- `workflow_6f88f17ac67177de32` — Workspace detail: `not_tested` (path length 8)
- `workflow_1cbfd9176ca1c603cc` — Overview: `not_tested` (path length 9)
- `workflow_de821bb8e711fe370c` — Open workflow: `failed` (path length 1)
- `workflow_a064e35b1fd7986909` — Enter member mode: `not_tested` (path length 6)
- `workflow_1214547f4637bfc650` — News: `navigation_only` (path length 2)
- `workflow_696722afa8fae45536` — News: `navigation_only` (path length 5)
- `workflow_1add961f98a60327b6` — JS Lab: `not_tested` (path length 5)
- `workflow_16ca2f7f7c80d9d20c` — Load late reports: `unresolved` (path length 5)
- `workflow_65ab68f57f36f446ff` — Open reports: `not_tested` (path length 6)
- `workflow_5afca6e2466361e01a` — Overview: `not_tested` (path length 7)
- `workflow_f426d89819b728aa1c` — Load late reports: `failed` (path length 1)
- `workflow_34241fa570f7dc4530` — Enter member mode: `not_tested` (path length 6)
- `workflow_a9d5ede52647560620` — JS Lab: `navigation_only` (path length 2)
- `workflow_2c23b6c560b9c35757` — Public alias area: `navigation_only` (path length 5)
- `workflow_d861e417d3a5179743` — Load alias data: `not_tested` (path length 6)

## Observed but not replay-validated

- `feature_11100edb72c51360` — Enter member mode leads to Member
- `feature_5ce256c24795e4ad` — JS Lab opens /
- `feature_7a7a2fdb703743db` — Open reports opens /reports
- `feature_90f6f381c10d60e7` — Continue setup leads to JavaScript Readiness Lab
- `feature_a6fdfb0309a1ff7e` — Open workspace opens /workspace
- `feature_bd73efed812d78fb` — Workspace detail opens /workspace/detail
- `feature_ddfe02aac6ebb137` — Overview opens /shallow/a

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
