# Agent 1 run agent1-20261030T215319Z

- Code revision: `5710c01fbcd2b09fab0886cbc0eedf65b0b1510e+mapper-9b4b25920aaf`
- Policy: `hierarchical`
- Target: `http://127.0.0.1:50792/`
- Elapsed: 60.579 seconds
- Browser actions (including setup/replay): 89
- Replay-validated navigation categories: 5
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 24
- Replay navigation success: 10/10
- Replay failures / untested paths: 0/19
- Graph connections with complete evidence: 567/567
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_38abb14282d03e97` — News opens /shallow/b
- `feature_4e99c95dbd8a7ac6` — Load late reports leads to JavaScript Readiness Lab
- `feature_572196394a692cc5` — Overview opens /shallow/a
- `feature_9c45708a2b4eccc1` — Open workflow leads to JavaScript Readiness Lab
- `feature_c449436cb1de966e` — Continue setup leads to JavaScript Readiness Lab

## Functional path-instance outcomes

- `workflow_0d7b8be56ed18d3153` — Public alias area: `navigation_only` (path length 1)
- `workflow_ac548e6d7ac8839083` — Refresh status: `unresolved` (path length 1)
- `workflow_569e2611b74349e48f` — Open workflow: `unresolved` (path length 1)
- `workflow_5ec7a0573cc8a78e98` — Continue setup: `unresolved` (path length 2)
- `workflow_8f440a90c3f531a913` — Open workspace: `not_tested` (path length 3)
- `workflow_77a13479e3e4b09d60` — Load late reports: `unresolved` (path length 1)
- `workflow_e823785a7bd141776a` — Open reports: `navigation_only` (path length 2)
- `workflow_2c2ea6fedd1fe33a78` — Overview: `navigation_only` (path length 1)
- `workflow_da9516f19083b24f77` — News: `navigation_only` (path length 1)
- `workflow_e3eff11382e72962d7` — JS Lab: `navigation_only` (path length 1)
- `workflow_35e9aeb1cf437fdf8b` — Open workflow: `not_tested` (path length 2)
- `workflow_8f90781c8ede344cc0` — Load late reports: `not_tested` (path length 2)
- `workflow_80d79610067ce37467` — Continue setup: `not_tested` (path length 3)
- `workflow_4b651760f75ac152ea` — Public alias area: `not_tested` (path length 4)
- `workflow_c8b0faf1c5163d2963` — Open workflow: `unresolved` (path length 2)
- `workflow_26b8f6ea640a0ff3a7` — Public alias area: `not_tested` (path length 3)
- `workflow_0084b1efb0c226e16c` — Public alias area: `not_tested` (path length 2)
- `workflow_b076fd42c12f853532` — Public alias area: `not_tested` (path length 2)
- `workflow_03f3893bdd8160bdb6` — Refresh status: `not_tested` (path length 2)
- `workflow_7e17aa669b9538cea5` — Open workflow: `not_tested` (path length 3)
- `workflow_86419e003db170854e` — Load late reports: `not_tested` (path length 3)
- `workflow_f4c3057f18d4f64c01` — Open workspace: `not_tested` (path length 4)
- `workflow_654bb4bf2490ef93f7` — Refresh status: `not_tested` (path length 2)
- `workflow_47d0cc7974e6186251` — Open reports: `not_tested` (path length 3)
- `workflow_62ff4482d4496a636f` — Refresh status: `not_tested` (path length 3)
- `workflow_139351a16751bca875` — Refresh status: `not_tested` (path length 3)
- `workflow_b03ff566bbe37f7cbb` — Open workflow: `not_tested` (path length 3)
- `workflow_3e997692fdf21f0167` — Open reports: `not_tested` (path length 4)
- `workflow_d8edbdf4743b260b80` — Refresh status: `not_tested` (path length 4)

## Observed but not replay-validated

- `feature_3fdf7d4ac7486ad3` — Load late reports leads to JavaScript Readiness Lab
- `feature_57596745286f0170` — Continue setup leads to JavaScript Readiness Lab
- `feature_65aaa97a2117e3ad` — Open workspace opens /workspace
- `feature_6b4971396990b395` — Public alias area opens /alias-area
- `feature_a1b7f7dfecb37603` — Open reports opens /reports
- `feature_a90ee4fc4b1202df` — Load late reports leads to JavaScript Readiness Lab
- `feature_d321ac671fa5a6b9` — Open workflow leads to JavaScript Readiness Lab

## Failed or blocked transitions

- `tr_d5c41de218b71fb04031` — Public alias area: RuntimeError: saved return path restored 115d8d59c12421cb, expected 769f87095bc16b7e

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
